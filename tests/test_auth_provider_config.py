from __future__ import annotations

import json
from pathlib import Path

import aibenchie_local
from aibenchie.auth_provider_config import validate_auth_provider_config


VALID_REAL_CONFIG = {
    "schema": "echolabs.auth-provider-config.v1",
    "template": False,
    "passkey": {
        "rp_id": "api.echolabs.diy",
        "origin": "https://api.echolabs.diy",
        "assetlinks_url": "https://api.echolabs.diy/.well-known/assetlinks.json",
        "android_package": "com.nullxoid.android",
        "relations": ["delegate_permission/common.get_login_creds"],
        "android_sha256_fingerprints": [
            "00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF"
        ],
    },
    "oidc": {
        "issuer": "https://id.echolabs.diy",
        "client_id": "nullxoid-android",
        "redirect_uri": "nullxoid://auth/oidc/callback",
        "flow": "authorization_code_pkce",
        "pkce_required": True,
        "client_secret_allowed": False,
        "scopes": ["openid", "profile", "email"],
    },
    "deployment_setup": {
        "env_names": [
            "NULLXOID_AUTH_PASSKEY_RP_ID",
            "NULLXOID_AUTH_PASSKEY_ORIGIN",
            "NULLXOID_AUTH_OIDC_ISSUER",
            "NULLXOID_AUTH_OIDC_CLIENT_ID",
        ]
    },
}


def write_config(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_template_auth_provider_config_passes_contract():
    result = validate_auth_provider_config()

    assert result.ok is True
    assert result.template is True
    assert result.require_real is False


def test_template_fails_when_real_config_required():
    result = validate_auth_provider_config(require_real=True)

    assert result.ok is False
    failures = {check.name: check.failure for check in result.checks if not check.ok}
    assert failures["template"] == "template_config_not_allowed_when_real_required"
    assert failures["passkey.android_sha256_fingerprints"] == "real_release_fingerprint_required"


def test_real_auth_provider_config_passes(tmp_path):
    path = write_config(tmp_path / "auth-provider.json", VALID_REAL_CONFIG)

    result = validate_auth_provider_config(path, require_real=True)

    assert result.ok is True
    assert result.template is False


def test_real_auth_provider_config_rejects_client_secret(tmp_path):
    payload = dict(VALID_REAL_CONFIG)
    payload["oidc"] = dict(VALID_REAL_CONFIG["oidc"])
    payload["oidc"]["client_secret"] = "do-not-store-this"
    path = write_config(tmp_path / "auth-provider.json", payload)

    result = validate_auth_provider_config(path, require_real=True)

    assert result.ok is False
    failures = {check.name: check.failure for check in result.checks if not check.ok}
    assert failures["secret_keys_absent"] == "forbidden_secret_keys_present"


def test_auth_provider_config_cli_outputs_json(monkeypatch, capsys):
    class FakeResult:
        ok = True

        def as_dict(self):
            return {
                "ok": True,
                "config_path": "configs/echolabs_auth_provider_config.example.json",
                "template": True,
                "require_real": False,
                "checks": [],
                "next_steps": [],
            }

    monkeypatch.setattr(aibenchie_local, "run_auth_provider_config_from_env", lambda: FakeResult())

    code = aibenchie_local.main(["--auth-provider-config", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["template"] is True
