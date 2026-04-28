from __future__ import annotations

import json

import pytest

import aibenchie_local
from aibenchie.e2ee_readiness import (
    REQUIRED_DEVICE_LIFECYCLE_CHECKS,
    REQUIRED_TARGET_CHECKS,
    run_e2ee_readiness_check,
)
from aibenchie import suite_security


TARGETS = ["saved_chats", "private_artifacts"]


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def policy(targets=TARGETS):
    return {
        "version": 1,
        "levels": {
            "5": {
                "name": "Local Sovereign",
                "required_controls": ["e2ee_storage"],
                "forbidden_controls": ["unapproved_remote_inference"],
            }
        },
        "e2ee_storage_targets": list(targets),
    }


def target_evidence(target: str, **overrides):
    payload = {
        "target": target,
        "status": "implemented",
        "encryption_boundary": "client_or_device",
        "key_management": "os_secure_storage_or_user_wrapped_key",
        "plaintext_storage": "forbidden",
        "tests": list(REQUIRED_TARGET_CHECKS),
        "evidence": [f"tests/e2ee/{target}.json"],
    }
    payload.update(overrides)
    return payload


def evidence(targets=TARGETS, **overrides):
    payload = {
        "version": 1,
        "status": "complete",
        "device_lifecycle": device_lifecycle_evidence(),
        "targets": [target_evidence(target) for target in targets],
    }
    payload.update(overrides)
    return payload


def device_lifecycle_evidence(**overrides):
    payload = {
        "status": "implemented",
        "encryption_boundary": "device_to_device_zero_knowledge",
        "key_management": "user held recovery secret and non server readable device enrollment envelopes",
        "backend_key_material": "forbidden",
        "tests": list(REQUIRED_DEVICE_LIFECYCLE_CHECKS),
        "evidence": [
            "EchoLabs/.NullXoid:frontend/src/lib/e2eeDeviceLifecycle.js",
            "EchoLabs/.NullXoid:frontend/src/lib/e2eeDeviceSetupState.js",
            "EchoLabs/.NullXoid:frontend/scripts/test-e2ee-device-lifecycle.mjs",
            "EchoLabs/.NullXoid:frontend/scripts/test-e2ee-device-setup-state.mjs",
            "EchoLabs/AIBenchie:aibenchie/zero_knowledge_devices.py",
        ],
    }
    payload.update(overrides)
    return payload


def env_for(policy_path, evidence_path):
    return {
        "AIBENCHIE_E2EE_POLICY": str(policy_path),
        "AIBENCHIE_E2EE_EVIDENCE": str(evidence_path),
    }


def test_e2ee_readiness_passes_only_with_complete_target_evidence(tmp_path):
    policy_path = tmp_path / "privacy-levels.json"
    evidence_path = tmp_path / "e2ee-readiness.json"
    write_json(policy_path, policy())
    write_json(evidence_path, evidence())

    result = run_e2ee_readiness_check(root=tmp_path, env=env_for(policy_path, evidence_path))

    assert result.ok is True
    assert result.proof["ok"] is True
    assert result.device_lifecycle["ok"] is True
    assert {target.target for target in result.targets} == set(TARGETS)


def test_e2ee_readiness_fails_when_evidence_manifest_is_missing(tmp_path):
    policy_path = tmp_path / "privacy-levels.json"
    evidence_path = tmp_path / "missing-e2ee-readiness.json"
    write_json(policy_path, policy())

    result = run_e2ee_readiness_check(root=tmp_path, env=env_for(policy_path, evidence_path))

    assert result.ok is False
    assert "e2ee_evidence_manifest_missing" in result.failures
    assert "device_lifecycle_evidence_missing" in result.failures
    assert "evidence_target_missing:saved_chats" in result.failures


def test_e2ee_readiness_fails_for_incomplete_target_claims(tmp_path):
    policy_path = tmp_path / "privacy-levels.json"
    evidence_path = tmp_path / "e2ee-readiness.json"
    write_json(policy_path, policy())
    write_json(
        evidence_path,
        {
            "version": 1,
            "status": "incomplete",
            "device_lifecycle": device_lifecycle_evidence(),
            "storage_targets": [
                target_evidence(
                    "saved_chats",
                    status="planned",
                    encryption_boundary="tls_only",
                    key_management="committed_repo_secret",
                    plaintext_storage="allowed",
                    tests=["roundtrip"],
                    evidence=[],
                )
            ],
        },
    )

    result = run_e2ee_readiness_check(root=tmp_path, env=env_for(policy_path, evidence_path))

    assert result.ok is False
    assert "saved_chats:status_not_implemented" in result.failures
    assert "saved_chats:encryption_boundary_invalid" in result.failures
    assert "saved_chats:key_management_invalid" in result.failures
    assert "saved_chats:plaintext_storage_not_forbidden" in result.failures
    assert "saved_chats:test_missing:wrong_key_rejected" in result.failures
    assert "saved_chats:evidence_missing" in result.failures
    assert "evidence_target_missing:private_artifacts" in result.failures


def test_e2ee_readiness_fails_for_incomplete_device_lifecycle_claims(tmp_path):
    policy_path = tmp_path / "privacy-levels.json"
    evidence_path = tmp_path / "e2ee-readiness.json"
    write_json(policy_path, policy())
    write_json(
        evidence_path,
        evidence(
            device_lifecycle=device_lifecycle_evidence(
                status="planned",
                encryption_boundary="server_only",
                key_management="committed repo recovery secret",
                backend_key_material="plaintext",
                tests=["device_enrollment"],
                evidence=[],
            )
        ),
    )

    result = run_e2ee_readiness_check(root=tmp_path, env=env_for(policy_path, evidence_path))

    assert result.ok is False
    assert "device_lifecycle:status_not_implemented" in result.failures
    assert "device_lifecycle:encryption_boundary_invalid" in result.failures
    assert "device_lifecycle:key_management_invalid" in result.failures
    assert "device_lifecycle:backend_key_material_not_absent" in result.failures
    assert "device_lifecycle:test_missing:recovery_secret_restores_key" in result.failures
    assert "device_lifecycle:test_missing:guided_setup_ui_contract" in result.failures
    assert "device_lifecycle:evidence_missing" in result.failures


def test_e2ee_readiness_rejects_raw_localstorage_key_claims(tmp_path):
    policy_path = tmp_path / "privacy-levels.json"
    evidence_path = tmp_path / "e2ee-readiness.json"
    write_json(policy_path, policy(targets=["saved_chats"]))
    write_json(
        evidence_path,
        {
            "version": 1,
            "status": "complete",
            "device_lifecycle": device_lifecycle_evidence(),
            "targets": [
                target_evidence("saved_chats", key_management="raw localStorage key kept in browser storage")
            ],
        },
    )

    result = run_e2ee_readiness_check(root=tmp_path, env=env_for(policy_path, evidence_path))

    assert result.ok is False
    assert "saved_chats:key_management_invalid" in result.failures


def test_e2ee_readiness_cli_returns_failure_until_product_evidence_exists(tmp_path, monkeypatch, capsys):
    policy_path = tmp_path / "privacy-levels.json"
    evidence_path = tmp_path / "missing-e2ee-readiness.json"
    write_json(policy_path, policy())
    monkeypatch.setenv("AIBENCHIE_E2EE_POLICY", str(policy_path))
    monkeypatch.setenv("AIBENCHIE_E2EE_EVIDENCE", str(evidence_path))

    assert aibenchie_local.main(["--e2ee-readiness", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "e2ee_evidence_manifest_missing" in payload["failures"]


def test_suite_security_can_make_e2ee_readiness_release_blocking(monkeypatch, tmp_path):
    monkeypatch.setattr(suite_security, "run_hosted_nullxoid_stack_check", lambda **kwargs: type("Stack", (), {"ok": True, "routes": [], "as_dict": lambda self: {"ok": True}})())
    monkeypatch.setattr(suite_security, "scan_public_files_for_secrets", lambda root: type("Scan", (), {"ok": True, "as_dict": lambda self: {"ok": True}})())
    monkeypatch.setattr(suite_security, "run_generated_output_policy_check", lambda env: type("Generated", (), {"ok": True, "budgets": [], "forbidden_files": [], "dirty_tracked_files": [], "as_dict": lambda self: {"ok": True}})())
    monkeypatch.setattr(suite_security, "verify_release_artifacts_manifest", lambda *args, **kwargs: type("Release", (), {"ok": True, "failures": [], "as_dict": lambda self: {"ok": True}})())
    monkeypatch.setattr(suite_security, "run_e2ee_readiness_check", lambda **kwargs: type("E2EE", (), {"ok": False, "failures": ["e2ee_evidence_manifest_missing"], "as_dict": lambda self: {"ok": False}})())

    result = suite_security.run_suite_security_check(
        {
            "AIBENCHIE_SUITE_SECURITY_ROOT": str(tmp_path),
            "AIBENCHIE_SUITE_SECURITY_E2EE": "1",
        }
    )

    checks = {check.name: check for check in result.checks}
    assert result.ok is False
    assert checks["nullprivacy_e2ee_readiness"].status == "fail"
    assert checks["nullprivacy_e2ee_readiness"].severity == "critical"


@pytest.mark.parametrize("target", TARGETS)
def test_e2ee_readiness_requires_each_target_in_policy_and_evidence(tmp_path, target):
    policy_path = tmp_path / "privacy-levels.json"
    evidence_path = tmp_path / "e2ee-readiness.json"
    remaining = [item for item in TARGETS if item != target]
    write_json(policy_path, policy(targets=remaining))
    write_json(evidence_path, evidence(targets=remaining))

    result = run_e2ee_readiness_check(
        root=tmp_path,
        env={**env_for(policy_path, evidence_path), "AIBENCHIE_E2EE_REQUIRED_TARGETS": ",".join(TARGETS)},
    )

    assert result.ok is False
    assert f"policy_target_missing:{target}" in result.failures
    assert f"evidence_target_missing:{target}" in result.failures
