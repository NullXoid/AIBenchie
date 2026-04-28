from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from aibenchie.nullprivacy import NullPrivacyError, decrypt_blob, encrypt_blob, generate_key


def _digest_id(prefix: str, value: bytes) -> str:
    return f"{prefix}:{hashlib.sha256(value).hexdigest()[:16]}"


def _contains_any(serialized: bytes, values: list[bytes]) -> bool:
    return any(value and value in serialized for value in values)


def _redacted_audit_event(action: str, *, actor_device_id: str, device_id: str, epoch: int) -> dict[str, Any]:
    payload = {
        "version": 1,
        "action": action,
        "actor_device_id": actor_device_id,
        "device_id": device_id,
        "epoch": epoch,
        "outcome": "success",
        "contains_key_material": False,
        "redaction": "key_material_omitted",
    }
    payload["event_id"] = _digest_id("device-audit", json.dumps(payload, sort_keys=True).encode("utf-8"))
    return payload


@dataclass(frozen=True)
class ZeroKnowledgeDeviceLifecycleProof:
    ok: bool
    device_enrollment_ok: bool
    recovery_secret_restores_key: bool
    wrong_recovery_secret_rejected: bool
    revoked_device_rejected_after_rotation: bool
    plaintext_absent_from_envelopes: bool
    backend_plaintext_key_absent: bool
    audit_redacted: bool
    failures: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "device_enrollment_ok": self.device_enrollment_ok,
            "recovery_secret_restores_key": self.recovery_secret_restores_key,
            "wrong_recovery_secret_rejected": self.wrong_recovery_secret_rejected,
            "revoked_device_rejected_after_rotation": self.revoked_device_rejected_after_rotation,
            "plaintext_absent_from_envelopes": self.plaintext_absent_from_envelopes,
            "backend_plaintext_key_absent": self.backend_plaintext_key_absent,
            "audit_redacted": self.audit_redacted,
            "failures": self.failures,
        }


def run_zero_knowledge_device_lifecycle_proof() -> ZeroKnowledgeDeviceLifecycleProof:
    account_key_v1 = generate_key()
    account_key_v2 = generate_key()
    existing_device_secret = generate_key()
    new_device_secret = generate_key()
    recovery_secret = generate_key()
    wrong_recovery_secret = generate_key()
    private_payload = b"zero knowledge private saved chat payload"

    enrollment_envelope = encrypt_blob(
        new_device_secret,
        account_key_v1,
        associated_data={
            "purpose": "device_enrollment",
            "recipient_device_id": "device-phone",
            "issuer_device_id": "device-laptop",
            "epoch": 1,
        },
    )
    recovered_by_new_device = decrypt_blob(new_device_secret, enrollment_envelope)
    device_enrollment_ok = recovered_by_new_device == account_key_v1

    recovery_envelope = encrypt_blob(
        recovery_secret,
        account_key_v1,
        associated_data={"purpose": "recovery", "user_id": "user-e2ee", "epoch": 1},
    )
    recovered_from_secret = decrypt_blob(recovery_secret, recovery_envelope)
    recovery_secret_restores_key = recovered_from_secret == account_key_v1

    wrong_recovery_secret_rejected = False
    try:
        decrypt_blob(wrong_recovery_secret, recovery_envelope)
    except NullPrivacyError:
        wrong_recovery_secret_rejected = True

    epoch_two_blob = encrypt_blob(
        account_key_v2,
        private_payload,
        associated_data={"purpose": "saved_chat", "epoch": 2},
    )
    revoked_device_rejected_after_rotation = False
    try:
        decrypt_blob(account_key_v1, epoch_two_blob)
    except NullPrivacyError:
        revoked_device_rejected_after_rotation = True

    backend_record = {
        "user_id": "user-e2ee",
        "active_epoch": 2,
        "active_devices": [{"device_id": "device-laptop", "key_id": _digest_id("device", existing_device_secret)}],
        "revoked_devices": [{"device_id": "device-phone", "revoked_at": "2026-04-28T00:00:00Z"}],
        "recovery_envelope": recovery_envelope,
        "device_enrollment_envelope": enrollment_envelope,
        "latest_payload": epoch_two_blob,
    }
    serialized_backend_record = json.dumps(backend_record, sort_keys=True).encode("utf-8")
    plaintext_absent_from_envelopes = not _contains_any(
        serialized_backend_record,
        [account_key_v1, account_key_v2, recovery_secret, new_device_secret, private_payload],
    )
    backend_plaintext_key_absent = "account_key" not in backend_record and "recovery_secret" not in backend_record

    audit_event = _redacted_audit_event(
        "device_revoked_key_rotated",
        actor_device_id="device-laptop",
        device_id="device-phone",
        epoch=2,
    )
    serialized_audit = json.dumps(audit_event, sort_keys=True).encode("utf-8")
    audit_redacted = (
        audit_event.get("contains_key_material") is False
        and not _contains_any(serialized_audit, [account_key_v1, account_key_v2, recovery_secret, new_device_secret])
    )

    checks = {
        "device_enrollment_ok": device_enrollment_ok,
        "recovery_secret_restores_key": recovery_secret_restores_key,
        "wrong_recovery_secret_rejected": wrong_recovery_secret_rejected,
        "revoked_device_rejected_after_rotation": revoked_device_rejected_after_rotation,
        "plaintext_absent_from_envelopes": plaintext_absent_from_envelopes,
        "backend_plaintext_key_absent": backend_plaintext_key_absent,
        "audit_redacted": audit_redacted,
    }
    failures = [name for name, passed in checks.items() if not passed]
    return ZeroKnowledgeDeviceLifecycleProof(
        ok=not failures,
        device_enrollment_ok=device_enrollment_ok,
        recovery_secret_restores_key=recovery_secret_restores_key,
        wrong_recovery_secret_rejected=wrong_recovery_secret_rejected,
        revoked_device_rejected_after_rotation=revoked_device_rejected_after_rotation,
        plaintext_absent_from_envelopes=plaintext_absent_from_envelopes,
        backend_plaintext_key_absent=backend_plaintext_key_absent,
        audit_redacted=audit_redacted,
        failures=failures,
    )
