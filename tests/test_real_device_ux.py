from __future__ import annotations

import json

import aibenchie_local
from aibenchie.real_device_ux import validate_real_device_ux_proof


def write_proof(path, overrides=None):
    payload = {
        "schema": "aibenchie.real-device-ux-proof.v1",
        "template": False,
        "proof_id": "android-physical-smoke-001",
        "platform": "android",
        "device": {
            "manufacturer": "Samsung",
            "model": "SM-A176U",
            "os_version": "Android 16",
            "device_id_hash": "0123456789abcdef0123456789abcdef",
        },
        "app": {
            "package": "com.nullxoid.android",
            "version": "1.0.0",
            "build_type": "release",
        },
        "environment": {
            "base_url": "https://api.echolabs.diy/nullxoid",
            "network": "cellular",
        },
        "workflows": [
            {
                "id": "signin",
                "name": "Native passkey sign-in",
                "status": "pass",
                "evidence": [{"kind": "manual_observation", "summary": "Signed in with Credential Manager."}],
            },
            {
                "id": "chat",
                "name": "NullXoid chat response",
                "status": "pass",
                "evidence": [{"kind": "manual_observation", "summary": "Chat returned a visible response."}],
            },
        ],
        "artifacts": [{"kind": "screenshot", "name": "chat", "sha256": "a" * 64}],
    }
    if overrides:
        payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_real_device_ux_accepts_public_safe_android_proof(tmp_path):
    proof = write_proof(tmp_path / "proof.json")

    result = validate_real_device_ux_proof(proof).as_dict()

    assert result["ok"] is True
    assert result["platform"] == "android"
    assert result["workflows"] == ["signin", "chat"]


def test_real_device_ux_rejects_template_default():
    result = validate_real_device_ux_proof("configs/aibenchie_real_device_ux.example.json").as_dict()
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is False
    assert checks["not_template"]["failure"] == "template_proof_not_release_evidence"


def test_real_device_ux_rejects_raw_device_ids_and_secret_material(tmp_path):
    proof = write_proof(
        tmp_path / "proof.json",
        overrides={
            "device": {
                "manufacturer": "Samsung",
                "model": "SM-A176U",
                "os_version": "Android 16",
                "device_id_hash": "0123456789abcdef0123456789abcdef",
                "serial": "R5GYC1KBN7T",
            },
            "session_token": "eyJnotAllowed",
        },
    )

    result = validate_real_device_ux_proof(proof).as_dict()
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is False
    assert "serial" in checks["raw_device_identifiers_absent"]["failure"]
    assert "secret_key_not_allowed" in checks["secret_boundary"]["failure"]


def test_real_device_ux_requires_android_signin_and_chat(tmp_path):
    proof = write_proof(tmp_path / "proof.json", overrides={"workflows": [{"id": "signin", "status": "pass", "evidence": [{"kind": "manual"}]}]})

    result = validate_real_device_ux_proof(proof).as_dict()
    checks = {check["name"]: check for check in result["checks"]}

    assert result["ok"] is False
    assert checks["android_required_workflows"]["failure"] == "workflow_missing:chat"


def test_real_device_ux_cli(capsys, tmp_path):
    proof = write_proof(tmp_path / "proof.json")

    exit_code = aibenchie_local.main(["--real-device-ux-proof", str(proof), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["proof_id"] == "android-physical-smoke-001"
