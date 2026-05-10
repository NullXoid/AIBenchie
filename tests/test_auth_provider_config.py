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

VALID_DEVICE_PROOF = {
    "schema": "echolabs.auth-provider-device-proof.v1",
    "template": False,
    "product": "EchoLabs Suite",
    "device": {
        "platform": "android",
        "package": "com.nullxoid.android",
        "model": "Pixel test device",
        "os_version": "Android 15",
        "release_sha256_fingerprint": VALID_REAL_CONFIG["passkey"]["android_sha256_fingerprints"][0],
    },
    "enrollment": {
        "tested_at": "2026-05-10T00:00:00Z",
        "rp_id": "api.echolabs.diy",
        "credential_manager_used": True,
        "passkey_created": True,
        "assetlinks_verified": True,
        "provider_metadata_live": True,
        "evidence": ["_validation/android-passkey-proof.png"],
    },
    "token_storage": "android_keystore",
    "leak_checks": {
        "urls_clean": True,
        "logs_clean": True,
        "frontend_storage_clean": True,
        "nullbridge_service_credentials_absent": True,
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
    assert result.readiness_stage == "template_contract_ready"
    assert "replace_template_provider_values" in result.missing_requirements
    assert result.public_assetlinks_statement == [
        {
            "relation": ["delegate_permission/common.get_login_creds"],
            "target": {
                "namespace": "android_app",
                "package_name": "com.nullxoid.android",
                "sha256_cert_fingerprints": [],
            },
        }
    ]


def test_template_fails_when_real_config_required():
    result = validate_auth_provider_config(require_real=True)

    assert result.ok is False
    failures = {check.name: check.failure for check in result.checks if not check.ok}
    assert failures["template"] == "template_config_not_allowed_when_real_required"
    assert failures["passkey.android_sha256_fingerprints"] == "real_release_fingerprint_required"
    assert result.readiness_stage == "blocked"
    assert "template:template_config_not_allowed_when_real_required" in result.missing_requirements


def test_real_auth_provider_config_passes(tmp_path):
    path = write_config(tmp_path / "auth-provider.json", VALID_REAL_CONFIG)

    result = validate_auth_provider_config(path, require_real=True)

    assert result.ok is True
    assert result.template is False
    assert result.readiness_stage == "provider_values_ready"
    assert "record_physical_android_credential_manager_proof" in result.missing_requirements
    assert result.public_assetlinks_statement[0]["target"]["sha256_cert_fingerprints"] == (
        VALID_REAL_CONFIG["passkey"]["android_sha256_fingerprints"]
    )


def test_passkey_origin_can_be_rp_id_subdomain(tmp_path):
    payload = json.loads(json.dumps(VALID_REAL_CONFIG))
    payload["passkey"]["rp_id"] = "echolabs.diy"
    payload["passkey"]["origin"] = "https://www.echolabs.diy"
    payload["passkey"]["assetlinks_url"] = "https://www.echolabs.diy/.well-known/assetlinks.json"
    path = write_config(tmp_path / "auth-provider.json", payload)

    result = validate_auth_provider_config(path, require_real=True)

    assert result.ok is True
    assert result.readiness_stage == "provider_values_ready"


def test_real_auth_provider_config_with_device_proof_passes(tmp_path):
    config_path = write_config(tmp_path / "auth-provider.json", VALID_REAL_CONFIG)
    proof_path = write_config(tmp_path / "device-proof.json", VALID_DEVICE_PROOF)

    result = validate_auth_provider_config(
        config_path,
        require_real=True,
        device_proof_path=proof_path,
        require_device_proof=True,
    )

    assert result.ok is True
    assert result.require_device_proof is True
    assert result.readiness_stage == "production_ready"
    assert result.missing_requirements == []


def test_auth_provider_config_requires_device_proof_file(tmp_path):
    config_path = write_config(tmp_path / "auth-provider.json", VALID_REAL_CONFIG)

    result = validate_auth_provider_config(config_path, require_real=True, require_device_proof=True)

    assert result.ok is False
    failures = {check.name: check.failure for check in result.checks if not check.ok}
    assert failures["device_proof_file"] == "missing_device_proof_path"


def test_auth_provider_device_proof_rejects_token_storage_and_fingerprint_mismatch(tmp_path):
    config_path = write_config(tmp_path / "auth-provider.json", VALID_REAL_CONFIG)
    proof = dict(VALID_DEVICE_PROOF)
    proof["device"] = dict(VALID_DEVICE_PROOF["device"])
    proof["device"]["release_sha256_fingerprint"] = "AA:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF"
    proof["token_storage"] = "shared_preferences"
    proof_path = write_config(tmp_path / "device-proof.json", proof)

    result = validate_auth_provider_config(
        config_path,
        require_real=True,
        device_proof_path=proof_path,
        require_device_proof=True,
    )

    assert result.ok is False
    failures = {check.name: check.failure for check in result.checks if not check.ok}
    assert failures["device_proof.device.release_sha256_fingerprint"] == "fingerprint_not_in_provider_config"
    assert failures["device_proof.token_storage"] == "token_storage_must_be_android_keystore"


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
                "device_proof_path": "configs/echolabs_auth_provider_device_proof.example.json",
                "require_device_proof": False,
                "checks": [],
                "next_steps": [],
            }

    monkeypatch.setattr(aibenchie_local, "run_auth_provider_config_from_env", lambda: FakeResult())

    code = aibenchie_local.main(["--auth-provider-config", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["template"] is True


def test_auth_provider_config_cli_accepts_device_proof(monkeypatch, capsys):
    class FakeResult:
        ok = True

        def as_dict(self):
            return {
                "ok": True,
                "config_path": "ignored-auth-provider-config.json",
                "device_proof_path": "ignored-device-proof.json",
                "template": False,
                "require_real": True,
                "require_device_proof": True,
                "checks": [],
                "next_steps": [],
            }

    monkeypatch.setattr(aibenchie_local, "run_auth_provider_config_from_env", lambda: FakeResult())

    code = aibenchie_local.main(
        [
            "--auth-provider-config",
            "--auth-provider-config-require-real",
            "--auth-provider-config-device-proof",
            "ignored-device-proof.json",
            "--auth-provider-config-require-device-proof",
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["require_device_proof"] is True
