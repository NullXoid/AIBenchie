from __future__ import annotations

from aibenchie.zero_knowledge_devices import run_zero_knowledge_device_lifecycle_proof


def test_zero_knowledge_device_lifecycle_proof_covers_enrollment_recovery_and_revocation():
    result = run_zero_knowledge_device_lifecycle_proof()

    assert result.ok is True
    assert result.device_enrollment_ok is True
    assert result.recovery_secret_restores_key is True
    assert result.wrong_recovery_secret_rejected is True
    assert result.revoked_device_rejected_after_rotation is True
    assert result.plaintext_absent_from_envelopes is True
    assert result.backend_plaintext_key_absent is True
    assert result.audit_redacted is True
    assert result.failures == []


def test_zero_knowledge_device_lifecycle_proof_is_json_safe():
    payload = run_zero_knowledge_device_lifecycle_proof().as_dict()

    assert payload["ok"] is True
    assert "recovery_secret" not in payload
    assert "account_key" not in payload
    assert "private_payload" not in payload
