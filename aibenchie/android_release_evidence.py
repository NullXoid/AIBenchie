"""Validate operator-owned Android acceptance evidence, not merely file presence.

These are local operator attestations with checked artifact bindings, not signatures
or an independent assertion that a test was actually performed.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

DEVICE_PROOF_SCHEMA = "aibenchie.android-release-device-proof.v2"
EVIDENCE_POLICY = "android-physical-https-v2"
PUBLISH_REQUIRED_CHECKS = frozenset({
    "release_mode", "release_https", "backend_revision", "apk_signer_verified",
    "apk_metadata_verified", "repo_exists", "app_id", "package_name", "app_version",
    "version_code", "base_url", "update_notes_file", "update_notes_latest_entry",
    "update_notes_required_sections", "apk_artifact", "signing_fingerprint",
    "expected_signing_fingerprint", "signing_fingerprint_match", "primary_device_proof",
    "secondary_device_proof", "distinct_physical_devices", "publish_action",
})
MAX_PROOF_BYTES = 131072
MAX_ATTACHMENT_BYTES = 4 * 1024 * 1024
MAX_AGE_SECONDS = 86400
COMMON_CHECKS = (
    "normal_app_login", "save_reopen", "offline_retry", "reconnect",
    "no_adb_transport", "relay_ciphertext_only", "tamper_rejected",
    "wrong_recipient_rejected", "recovery_verified", "snapshot_rollback_rejected",
)
REQUIRED_CHECKS = {
    "nullbridge_android": COMMON_CHECKS + (
        "agent_enrollment", "phone_to_agent", "agent_to_phone", "agent_to_agent",
        "revocation_enforced", "delivery_status",
    ),
    "nullxoid_android": COMMON_CHECKS + (
        "encrypted_titles", "competing_edits", "downgrade_rejected",
    ),
}


def strict_json(data: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("invalid_json_constant")

    return json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def read_bounded(path: Path, limit: int) -> bytes:
    if (not path.is_file() or any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                                for p in [path, *path.parents])):
        raise ValueError("regular_file_required")
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if not data or len(data) > limit:
        raise ValueError("file_size_invalid")
    return data


def fresh_timestamp(value, now: datetime) -> bool:
    try:
        if not isinstance(value, str):
            return False
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.utcoffset() is not None and -60 <= (now - parsed).total_seconds() <= MAX_AGE_SECONDS
    except (ValueError, TypeError, OverflowError):
        return False


def valid_https_url(value: str) -> bool:
    try:
        if not isinstance(value, str) or any(ord(c) < 33 or ord(c) == 127 for c in value):
            return False
        url = urlsplit(value)
        return bool(
            url.scheme == "https" and url.hostname and url.port != 0
            and not url.username and not url.password and not url.query and not url.fragment
            and "\\" not in value and "%" not in value
            and not any(part in {".", ".."} for part in url.path.split("/"))
        )
    except ValueError:
        return False


def validate_device_proof(path: Path, expected: dict, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    result = {"present": path.exists(), "valid": False, "errors": []}
    errors = result["errors"]
    try:
        raw = read_bounded(path, MAX_PROOF_BYTES)
        payload = strict_json(raw)
        result["sha256"] = hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError, RecursionError):
        errors.append("proof_missing_or_invalid_json")
        return result
    if not isinstance(payload, dict) or payload.get("schema") != DEVICE_PROOF_SCHEMA:
        errors.append("proof_schema")
        return result
    if not fresh_timestamp(payload.get("generated_at"), now):
        errors.append("proof_expired_or_invalid_time")
    for key in ("app_id", "package_name", "app_version", "version_code", "apk_sha256",
                "signing_fingerprint_sha256", "base_url", "backend_revision"):
        if not expected.get(key) or payload.get(key) != expected[key]:
            errors.append("proof_binding_" + key)
    for key in ("apk_sha256", "serial_hash"):
        if not isinstance(payload.get(key), str) or not re.fullmatch(r"[a-f0-9]{64}", payload[key]):
            errors.append("proof_invalid_" + key)
    if not isinstance(payload.get("backend_revision"), str) or not re.fullmatch(r"[a-f0-9]{40}", payload["backend_revision"]):
        errors.append("proof_invalid_backend_revision")
    if not valid_https_url(payload.get("base_url")):
        errors.append("proof_https_required")
    if (payload.get("physical") is not True or payload.get("adb_forwarding") is not False
            or payload.get("transport") != "normal-app-https"
            or payload.get("install_state") != "installed"):
        errors.append("proof_normal_physical_app_required")
    if not isinstance(payload.get("model"), str) or not payload["model"].strip() or len(payload["model"]) > 120:
        errors.append("proof_device_model")
    if payload.get("verdict") != "pass":
        errors.append("proof_not_passed")
    attachments = payload.get("evidence")
    valid_attachments = set()
    if not isinstance(attachments, dict) or not 1 <= len(attachments) <= 32:
        errors.append("proof_evidence_required")
    else:
        for name, attachment in attachments.items():
            try:
                if not re.fullmatch(r"[a-z0-9_-]{1,64}", name) or not isinstance(attachment, dict):
                    raise ValueError("attachment_schema")
                relative = attachment.get("path")
                if not isinstance(relative, str) or not re.fullmatch(r"[A-Za-z0-9_./-]{1,240}", relative):
                    raise ValueError("attachment_path")
                parts = PurePosixPath(relative)
                if parts.is_absolute() or any(part in {".", ".."} for part in relative.split("/")):
                    raise ValueError("attachment_path")
                target = path.parent / relative
                if not target.resolve().is_relative_to(path.parent.resolve()):
                    raise ValueError("attachment_path")
                if any(parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction())
                       for parent in [target, *target.parents]):
                    raise ValueError("attachment_symlink")
                data = read_bounded(target, MAX_ATTACHMENT_BYTES)
                if hashlib.sha256(data).hexdigest() != attachment.get("sha256"):
                    raise ValueError("attachment_hash")
                valid_attachments.add(name)
            except (OSError, ValueError):
                errors.append("proof_evidence_invalid")
    checks = payload.get("checks")
    required = REQUIRED_CHECKS.get(expected.get("app_id"), ())
    if not required or not isinstance(checks, dict) or set(checks) != set(required):
        errors.append("proof_check_set")
    else:
        for name in required:
            item = checks[name]
            if (not isinstance(item, dict) or item.get("status") != "pass"
                    or not isinstance(item.get("evidence"), list) or not item["evidence"]
                    or any(not isinstance(ref, str) or ref not in valid_attachments for ref in item["evidence"])):
                errors.append("proof_check_" + name)
    serial = payload.get("serial_hash")
    result.update(valid=not errors, schema=DEVICE_PROOF_SCHEMA,
                  serial_hash=serial if isinstance(serial, str) and re.fullmatch(r"[a-f0-9]{64}", serial) else None,
                  generated_at=payload.get("generated_at") if fresh_timestamp(payload.get("generated_at"), now) else None)
    return result


def validate_publish_verdict(verdict_path: Path, proofs: tuple[Path, Path], expected: dict,
                             *, now: datetime | None = None) -> list[str]:
    """Recheck receipts and referenced bytes at publication, not just at gate time."""
    now = now or datetime.now(timezone.utc)
    try:
        verdict = strict_json(read_bounded(verdict_path, 512 * 1024))
        if not isinstance(verdict, dict):
            raise ValueError("invalid_verdict")
        android = verdict["android"]
        if not isinstance(android, dict):
            raise ValueError("invalid_android")
        checks = verdict["checks"]
        if not isinstance(checks, list) or not checks or any(not isinstance(c, dict) for c in checks):
            raise ValueError("invalid_checks")
    except (OSError, ValueError, KeyError, RecursionError):
        return ["release_verdict_invalid"]
    errors = []
    if (verdict.get("schema") != "aibenchie.android-release-verdict.v1"
            or android.get("evidence_policy") != EVIDENCE_POLICY
            or android.get("publish_action") not in {"publish", "latest-debug", "ready_to_publish"}
            or verdict.get("ok") is not True or verdict.get("verdict") != "pass"):
        errors.append("strict_release_verdict_required")
    if not fresh_timestamp(verdict.get("generated_at"), now):
        errors.append("release_verdict_expired")
    for field in ("app_id", "app_version", "version_code", "base_url", "backend_revision"):
        if not expected.get(field) or android.get(field) != expected[field]:
            errors.append("release_binding_" + field)
    if android.get("package") != expected.get("package_name"):
        errors.append("release_binding_package_name")
    signing = android.get("signing", {})
    if (not isinstance(signing, dict) or signing.get("match") is not True
            or signing.get("fingerprint_sha256") != expected.get("signing_fingerprint_sha256")):
        errors.append("release_binding_signer")
    artifacts = verdict.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 1 or not isinstance(artifacts[0], dict):
        errors.append("release_artifact_invalid")
    elif artifacts[0].get("kind") != "android_apk" or artifacts[0].get("sha256") != expected.get("apk_sha256"):
        errors.append("release_binding_apk_sha256")
    notes = verdict.get("notes")
    if not isinstance(notes, dict) or not expected.get("notes_sha256") or notes.get("sha256") != expected["notes_sha256"]:
        errors.append("release_binding_notes")
    names = [c.get("name") for c in checks]
    required = PUBLISH_REQUIRED_CHECKS
    if (any(not isinstance(n, str) for n in names) or len(set(names)) != len(names)
            or not required.issubset(names)):
        errors.append("release_check_set")
    for item in checks:
        if not isinstance(item.get("name"), str):
            errors.append("release_check_set")
            continue
        if (item.get("status") not in {"pass", "skip"}
                or item.get("ok") is not True
                or (item.get("required") is True or item.get("name") in required)
                and (item.get("status") != "pass" or item.get("required") is not True)):
            errors.append("release_check_not_passed")
    summary = verdict.get("summary")
    counts = {
        "checks_total": len(checks),
        "passed": sum(c.get("status") == "pass" for c in checks),
        "skipped": sum(c.get("status") == "skip" for c in checks),
        "required_failures": 0,
        "warnings": 0,
    }
    if not isinstance(summary, dict) or any(
        type(summary.get(key)) is not int or summary[key] != count
        for key, count in counts.items()
    ):
        errors.append("release_summary_mismatch")
    summaries = [validate_device_proof(path, expected, now=now) for path in proofs]
    recorded = android.get("device_proofs", {})
    for role, summary in zip(("primary", "secondary"), summaries):
        record = recorded.get(role) if isinstance(recorded, dict) else None
        if not summary["valid"]:
            errors.append(role + "_device_proof_invalid")
        if not isinstance(record, dict) or record.get("valid") is not True or record.get("sha256") != summary.get("sha256"):
            errors.append(role + "_device_proof_changed")
    if not all(s["valid"] for s in summaries) or summaries[0].get("serial_hash") == summaries[1].get("serial_hash"):
        errors.append("distinct_physical_devices_required")
    return sorted(set(errors))
