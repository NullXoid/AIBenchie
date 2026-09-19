"""Approval sign-in policy checks, owned and invoked only by AIBenchie."""
from contextlib import closing
from datetime import timedelta
import os
from pathlib import Path
import secrets
import subprocess
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("AIBENCHIE_CANVAS_ACCOUNT_ROOT"), reason="Explicit account candidate required")


@pytest.fixture
def account(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(os.environ["AIBENCHIE_CANVAS_ACCOUNT_ROOT"]).resolve()))
    from backend import account_approvals, account_links, auth, auth_store
    from starlette.requests import Request
    monkeypatch.setattr(auth_store, "DB_PATH", tmp_path / "account.db")
    monkeypatch.setattr(auth_store, "ADMIN_BOOTSTRAPPED", False)
    monkeypatch.delenv("NX_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    auth_store.init_db()
    uid = auth_store.create_user("test-master", secrets.token_urlsafe(32), "user")
    policy = dict(issuer="https://accounts.example.test", masterUserIds=[uid], tenantId="default")
    monkeypatch.setattr(account_links.authority, "policy", lambda: policy)
    client = SimpleNamespace(issuer=policy["issuer"], _token=secrets.token_hex(32))
    def session(method="password"):
        credential = secrets.token_urlsafe(32) if method == "passkey" else ""
        if credential:
            auth_store.create_passkey_credential(user_id=uid, credential_id=credential,
                public_key_jwk={"aibenchie_fixture": True}, rp_id="localhost")
        sid = auth_store.create_session(uid, auth.hash_token(secrets.token_urlsafe(32)), "test", "127.0.0.1",
            auth.hash_token(secrets.token_urlsafe(32)), auth_method=method, auth_credential_id=credential)
        request = Request({"type": "http", "headers": []})
        request.state.auth_type, request.state.session_id = "session", sid
        return request, auth_store.get_user_by_id(uid)
    return SimpleNamespace(links=account_links, approvals=account_approvals, store=auth_store, auth=auth,
        client=client, session=session, uid=uid, policy=policy)


def test_password_requires_operator_policy_and_does_not_grant_master(account):
    from fastapi import HTTPException
    a = account
    actor = a.session()
    strict = a.links.AccountLinks(a.client)
    with pytest.raises(HTTPException, match="passkey_verification_required"):
        strict._actor(*actor, fresh=True)
    permitted = a.links.AccountLinks(a.client, authentication_policy="account-session")
    assert permitted._actor(*actor, fresh=True)[0]["id"] == a.uid
    approvals = a.approvals.AccountApprovals(permitted, validation_token=secrets.token_hex(32))
    a.policy["masterUserIds"] = []
    with pytest.raises(HTTPException, match="master_required"):
        approvals._snapshot(*actor, "not-a-link", fresh=True)


@pytest.mark.parametrize("method", ["legacy", "oidc"])
def test_unqualified_authentication_does_not_become_approval(account, method):
    from fastapi import HTTPException
    links = account.links.AccountLinks(account.client, authentication_policy="account-session")
    with pytest.raises(HTTPException, match="sign_in_required"):
        links._actor(*account.session(method), fresh=True)


@pytest.mark.parametrize("failure", ["logout", "disabled", "expired"])
def test_password_policy_still_checks_current_account_session(account, failure):
    from fastapi import HTTPException
    a = account
    actor = a.session()
    sid = actor[0].state.session_id
    if failure == "logout":
        a.store.revoke_session(sid)
    elif failure == "disabled":
        a.store.set_user_disabled(a.uid)
    else:
        with closing(a.store._connect()) as db, db:
            db.execute("UPDATE sessions SET last_seen_at=? WHERE id=?", ((a.auth._utc_now() - timedelta(days=365)).isoformat(), sid))
    links = a.links.AccountLinks(a.client, authentication_policy="account-session")
    with pytest.raises(HTTPException, match="account_session_required"):
        links._actor(*actor, fresh=True)


def test_original_session_revocation_and_policy_change_invalidate_link(account):
    from fastapi import HTTPException
    a = account
    actor = a.session()
    sid = actor[0].state.session_id
    links = a.links.AccountLinks(a.client, authentication_policy="account-session")
    row = dict(revoked_at=None, expires_at=links._now() + 900, issuer=a.policy["issuer"], account_session=sid)
    links._live_link(row, actor[1], a.policy)
    strict = a.links.AccountLinks(a.client)
    with pytest.raises(HTTPException, match="sign_in_policy_changed"):
        strict._live_link(row, actor[1], a.policy)
    a.store.revoke_session(sid)
    with pytest.raises(HTTPException, match="sign_in_revoked_or_expired"):
        links._live_link(row, actor[1], a.policy)


def test_passkey_revocation_is_enforced_under_both_policies(account):
    from fastapi import HTTPException
    a = account
    actor = a.session("passkey")
    session = a.store.get_session_by_id(actor[0].state.session_id)
    for policy in ("recent-passkey", "account-session"):
        assert a.links.AccountLinks(a.client, authentication_policy=policy).authentication_ready(session)
    a.store.revoke_passkey_credential(session["auth_credential_id"])
    for policy in ("recent-passkey", "account-session"):
        with pytest.raises(HTTPException):
            a.links.AccountLinks(a.client, authentication_policy=policy)._actor(*actor, fresh=True)


@pytest.mark.parametrize("policy", ["disabled", "", None, [], True])
def test_unknown_authentication_policy_is_rejected(account, policy):
    with pytest.raises(ValueError, match="invalid_account_link_authentication_policy"):
        account.links.AccountLinks(account.client, authentication_policy=policy)


def test_web_approval_readiness_uses_configured_policy():
    subprocess.run(["node", str(Path(__file__).with_name("bridge_approval_authentication.mjs"))], check=True, timeout=15)
