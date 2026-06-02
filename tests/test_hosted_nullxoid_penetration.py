from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import aibenchie_local
from aibenchie import hosted_nullxoid_penetration as penetration


class _FakeOpener:
    def __init__(self, jar, index: int):
        self.jar = jar
        self.index = index


def _install_fake_host(monkeypatch, *, accept_wrong_csrf: bool = False):
    openers: list[_FakeOpener] = []
    revoked_sessions: set[str] = set()

    def fake_build_opener(processor):
        opener = _FakeOpener(processor.cookiejar, len(openers) + 1)
        openers.append(opener)
        return opener

    def set_cookie(opener: _FakeOpener, name: str, value: str):
        opener.jar.set_cookie(penetration._make_cookie(name, value, "https://api.example.test"))

    def fake_request_json(
        opener,
        origin,
        base_path,
        path,
        *,
        method="GET",
        payload=None,
        headers=None,
        origin_header=None,
        timeout=15,
    ):
        if path == "/auth/login":
            set_cookie(opener, "nx_session", f"session-{opener.index}")
            set_cookie(opener, "nx_csrf", f"csrf-{opener.index}")
            return 200, {"ok": True}
        if path == "/auth/me":
            session = penetration._cookie_value(opener.jar, "nx_session")
            csrf = penetration._cookie_value(opener.jar, "nx_csrf")
            return 200, {"authenticated": bool(session), "csrf_token": csrf}
        if path == "/auth/logout":
            revoked_sessions.add(penetration._cookie_value(opener.jar, "nx_session"))
            return 200, {"ok": True}
        if method == "POST" and path.endswith("/revoke"):
            if origin_header == "https://evil.example.invalid":
                return 403, {"detail": "Origin not allowed"}
            session = penetration._cookie_value(opener.jar, "nx_session")
            csrf = penetration._cookie_value(opener.jar, "nx_csrf")
            header = (headers or {}).get("x-csrf-token", "")
            if not session or session in revoked_sessions:
                return 403, {"detail": "No active session"}
            if not header:
                return 403, {"detail": "CSRF token missing"}
            if accept_wrong_csrf and header == "wrong-csrf-token":
                return 200, {"ok": True}
            if header != csrf:
                return 403, {"detail": "CSRF token invalid"}
            return 200, {"ok": True, "revoked": False}
        return 500, {"detail": f"Unhandled path: {path}"}

    monkeypatch.setattr(penetration.urllib.request, "build_opener", fake_build_opener)
    monkeypatch.setattr(penetration, "_request_json", fake_request_json)


def test_hosted_nullxoid_penetration_probes_csrf_and_session_replay(monkeypatch):
    _install_fake_host(monkeypatch)

    result = penetration.run_hosted_nullxoid_penetration_check(
        origin="https://api.example.test",
        base_path="/nullxoid/",
        username="admin",
        password="runtime-secret",
    )

    payload = result.as_dict()

    assert result.ok is True
    assert result.base_path == "/nullxoid"
    assert {probe["name"] for probe in payload["probes"]} == {
        "anonymous_csrf_header_cannot_mutate",
        "credentialed_login_prerequisite",
        "session_cookie_without_csrf_cannot_mutate",
        "wrong_csrf_cannot_mutate",
        "forged_origin_rejected_before_mutation",
        "second_login_prerequisite",
        "csrf_from_other_session_cannot_mutate",
        "logout_probe_session_revoked",
        "revoked_session_cannot_mutate",
    }
    assert "runtime-secret" not in json.dumps(payload)


def test_hosted_nullxoid_penetration_fails_when_wrong_csrf_is_accepted(monkeypatch):
    _install_fake_host(monkeypatch, accept_wrong_csrf=True)

    result = penetration.run_hosted_nullxoid_penetration_check(
        origin="https://api.example.test",
        username="admin",
        password="runtime-secret",
    )

    wrong_csrf = next(probe for probe in result.probes if probe.name == "wrong_csrf_cannot_mutate")
    assert result.ok is False
    assert wrong_csrf.status == 200
    assert wrong_csrf.failure == "unexpected_http_200"


def test_hosted_nullxoid_penetration_cli_json(monkeypatch, capsys):
    result = penetration.HostedNullXoidPenetrationResult(
        ok=True,
        origin="https://api.example.test",
        base_path="/nullxoid",
        probes=[
            penetration.PenetrationProbe(
                name="anonymous_csrf_header_cannot_mutate",
                ok=True,
                status=403,
                expected=[401, 403],
            )
        ],
    )
    monkeypatch.setattr(aibenchie_local, "run_hosted_nullxoid_penetration_from_env", lambda: result)

    exit_code = aibenchie_local.main(["--hosted-nullxoid-penetration", "--json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "anonymous_csrf_header_cannot_mutate" in output
    assert "password" not in output.lower()
