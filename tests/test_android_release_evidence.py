from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest

from aibenchie.android_release_evidence import (
    DEVICE_PROOF_SCHEMA, PUBLISH_REQUIRED_CHECKS, REQUIRED_CHECKS,
    validate_device_proof, validate_publish_verdict,
)
from aibenchie.android_release_gate import run_android_release_gate
from tests.test_android_release_gate import VALID_FINGERPRINT, write_update_notes


@pytest.fixture
def acceptance(tmp_path, monkeypatch):
    apk = tmp_path / "candidate.apk"
    apk.write_bytes(b"synthetic signed candidate")
    notes = tmp_path / "UPDATE_NOTES.md"
    write_update_notes(notes)
    expected = dict(app_id="nullbridge_android", package_name="com.nullxoid.nullbridge",
                    app_version="0.3.0", version_code="104", base_url="https://stage.example.test/nullbridge/",
                    backend_revision="b" * 40, apk_sha256=sha256(apk.read_bytes()).hexdigest(),
                    signing_fingerprint_sha256=VALID_FINGERPRINT,
                    notes_sha256=sha256(notes.read_text(encoding="utf-8").encode("utf-8")).hexdigest())
    evidence = tmp_path / "synthetic-test-result.txt"
    evidence.write_text("Isolated unit-test evidence, not a physical test or release approval.\n")
    payload = dict(schema=DEVICE_PROOF_SCHEMA, generated_at=datetime.now(timezone.utc).isoformat(),
                   **{key: value for key, value in expected.items() if key != "notes_sha256"},
                   serial_hash="1" * 64, model="synthetic physical fixture", physical=True,
                   adb_forwarding=False, transport="normal-app-https", install_state="installed", verdict="pass",
                   evidence={"result": {"path": evidence.name, "sha256": sha256(evidence.read_bytes()).hexdigest()}},
                   checks={name: {"status": "pass", "evidence": ["result"]} for name in REQUIRED_CHECKS[expected["app_id"]]})
    primary, secondary = tmp_path / "primary.json", tmp_path / "secondary.json"
    primary.write_text(json.dumps(payload))
    secondary.write_text(json.dumps(payload | {"serial_hash": "2" * 64}))
    monkeypatch.setattr("aibenchie.android_release_gate._extract_apk_signing_fingerprint", lambda _: VALID_FINGERPRINT)
    monkeypatch.setattr("aibenchie.android_release_gate._extract_apk_metadata", lambda _: {
        key: expected[key] for key in ("package_name", "version_code", "app_version")})
    args = dict(repo=tmp_path, apk=apk, update_notes=notes, app_id=expected["app_id"],
                package_name=expected["package_name"], app_version=expected["app_version"],
                version_code=expected["version_code"], base_url=expected["base_url"],
                backend_revision=expected["backend_revision"], expected_signing_fingerprint=VALID_FINGERPRINT,
                expected_signing_fingerprint_source="synthetic fixture", primary_device_proof=primary,
                secondary_device_proof=secondary, publish_action="publish", output=tmp_path / "verdict.json")
    return args, expected, payload


@pytest.mark.parametrize("mode", ["publish", "latest-debug", "ready_to_publish"])
def test_complete_bound_acceptance_passes(acceptance, mode):
    args, expected, _ = acceptance
    verdict = run_android_release_gate(**(args | {"publish_action": mode}))
    assert verdict["ok"] is True
    assert verdict["android"]["publish_action"] == mode
    assert validate_publish_verdict(args["output"], (args["primary_device_proof"], args["secondary_device_proof"]), expected) == []


@pytest.mark.parametrize("value", ["not JSON", "[]", "null", "true", "{}", '{"schema":"old"}', '{"x":1,"x":2}', '{"x":NaN}'])
def test_invalid_proofs_are_not_present_equals_pass(acceptance, value):
    args, _, _ = acceptance
    args["primary_device_proof"].write_text(value)
    result = run_android_release_gate(**args)
    assert result["ok"] is False
    assert result["android"]["device_proofs"]["primary"]["valid"] is False


@pytest.mark.parametrize("field,value", [
    ("app_id", "nullxoid_android"), ("package_name", "com.wrong"), ("app_version", "old"),
    ("version_code", 104), ("apk_sha256", "a" * 64), ("signing_fingerprint_sha256", "AB:" * 32),
    ("base_url", "https://other.example.test/"), ("backend_revision", "c" * 40),
    ("physical", False), ("physical", 1), ("adb_forwarding", True), ("adb_forwarding", 0),
    ("transport", "adb-reverse"), ("install_state", "missing"), ("verdict", "pending"),
    ("serial_hash", ""), ("model", ""), ("generated_at", "2026-01-01"),
])
def test_mismatch_or_unqualified_context_rejected(acceptance, field, value):
    args, expected, payload = acceptance
    args["primary_device_proof"].write_text(json.dumps(payload | {field: value}))
    assert not validate_device_proof(args["primary_device_proof"], expected)["valid"]


@pytest.mark.parametrize("delta", [-86401, 61])
def test_stale_and_future_proofs_rejected(acceptance, delta):
    args, expected, payload = acceptance
    now = datetime.now(timezone.utc)
    payload["generated_at"] = (now + timedelta(seconds=delta)).isoformat()
    args["primary_device_proof"].write_text(json.dumps(payload))
    assert not validate_device_proof(args["primary_device_proof"], expected, now=now)["valid"]


@pytest.mark.parametrize("state", ["skip", "pending", "fail", True, None])
def test_every_required_scenario_must_pass(acceptance, state):
    args, expected, payload = acceptance
    payload["checks"]["recovery_verified"]["status"] = state
    args["primary_device_proof"].write_text(json.dumps(payload))
    assert not validate_device_proof(args["primary_device_proof"], expected)["valid"]


def test_duplicate_device_does_not_satisfy_two_phone_requirement(acceptance):
    args, _, payload = acceptance
    args["secondary_device_proof"].write_text(json.dumps(payload))
    assert not run_android_release_gate(**args)["ok"]


@pytest.mark.parametrize("path", ["../outside.txt", "/absolute.txt", "C:/outside.txt", "sub/../result.txt", "file:stream", "missing.txt"])
def test_bad_attachment_path_rejected(acceptance, path):
    args, expected, payload = acceptance
    payload["evidence"]["result"]["path"] = path
    args["primary_device_proof"].write_text(json.dumps(payload))
    assert not validate_device_proof(args["primary_device_proof"], expected)["valid"]


def test_missing_checks_and_missing_attachment_reference_rejected(acceptance):
    args, expected, payload = acceptance
    payload["checks"].pop("no_adb_transport")
    args["primary_device_proof"].write_text(json.dumps(payload))
    assert not validate_device_proof(args["primary_device_proof"], expected)["valid"]
    payload["checks"]["no_adb_transport"] = {"status": "pass", "evidence": ["nonexistent"]}
    args["primary_device_proof"].write_text(json.dumps(payload))
    assert not validate_device_proof(args["primary_device_proof"], expected)["valid"]


def test_attachment_change_after_gate_is_rechecked(acceptance):
    args, expected, _ = acceptance
    assert run_android_release_gate(**args)["ok"]
    (args["repo"] / "synthetic-test-result.txt").write_text("changed")
    assert "primary_device_proof_invalid" in validate_publish_verdict(
        args["output"], (args["primary_device_proof"], args["secondary_device_proof"]), expected)


def test_proof_change_after_gate_is_rechecked(acceptance):
    args, expected, payload = acceptance
    assert run_android_release_gate(**args)["ok"]
    args["primary_device_proof"].write_text(json.dumps(payload | {"model": "different phone"}))
    assert "primary_device_proof_changed" in validate_publish_verdict(
        args["output"], (args["primary_device_proof"], args["secondary_device_proof"]), expected)


def test_diagnostic_cannot_be_promoted(acceptance):
    args, expected, _ = acceptance
    assert run_android_release_gate(**(args | {"publish_action": "diagnostic"}))["ok"]
    assert "strict_release_verdict_required" in validate_publish_verdict(
        args["output"], (args["primary_device_proof"], args["secondary_device_proof"]), expected)


@pytest.mark.parametrize("mode", ["pubish", "READY", "false"])
def test_unknown_mode_never_becomes_diagnostic(acceptance, mode):
    args, _, _ = acceptance
    assert not run_android_release_gate(**(args | {"publish_action": mode}))["ok"]


def test_argument_cannot_substitute_for_real_signer_verification(acceptance, monkeypatch):
    args, _, _ = acceptance
    monkeypatch.setattr("aibenchie.android_release_gate._extract_apk_signing_fingerprint", lambda _: "")
    assert not run_android_release_gate(**(args | {"signing_fingerprint_sha256": VALID_FINGERPRINT}))["ok"]


@pytest.mark.parametrize("url", ["http://localhost.evil.test/", "https://user:password@example.test/", "https://example.test/#secret", "https://example.test/%2e%2e/admin"])
def test_ambiguous_or_credential_urls_rejected(acceptance, url):
    args, _, _ = acceptance
    assert not run_android_release_gate(**(args | {"base_url": url}))["ok"]


def test_oversized_and_nonfile_proofs_fail_closed(acceptance):
    args, expected, _ = acceptance
    args["primary_device_proof"].write_bytes(b"x" * 131073)
    assert not validate_device_proof(args["primary_device_proof"], expected)["valid"]
    assert not validate_device_proof(args["repo"], expected)["valid"]


@pytest.mark.parametrize("mutation", ["stale", "required_skip", "missing_check", "duplicate_check", "invalid_check_name", "notes", "backend", "invalid_json"])
def test_publish_consumer_rejects_altered_verdicts(acceptance, mutation):
    args, expected, _ = acceptance
    result = run_android_release_gate(**args)
    assert result["ok"]
    if mutation == "stale":
        result["generated_at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    elif mutation == "required_skip":
        next(c for c in result["checks"] if c["name"] == "primary_device_proof")["status"] = "skip"
    elif mutation == "missing_check":
        result["checks"] = [c for c in result["checks"] if c["name"] != "primary_device_proof"]
    elif mutation == "duplicate_check":
        result["checks"].append(result["checks"][0])
    elif mutation == "invalid_check_name":
        result["checks"][0]["name"] = {}
    elif mutation == "notes":
        result["notes"]["sha256"] = "0" * 64
    elif mutation == "backend":
        result["android"]["backend_revision"] = "d" * 40
    args["output"].write_text("[]" if mutation == "invalid_json" else json.dumps(result))
    assert validate_publish_verdict(args["output"], (args["primary_device_proof"], args["secondary_device_proof"]), expected)


def test_apk_manifest_must_match_claimed_version(acceptance, monkeypatch):
    args, _, _ = acceptance
    monkeypatch.setattr("aibenchie.android_release_gate._extract_apk_metadata", lambda _: {
        "package_name": "com.nullxoid.nullbridge", "version_code": "1", "app_version": "old"})
    assert not run_android_release_gate(**args)["ok"]


def test_valid_nullxoid_acceptance_contract(acceptance):
    args, expected, payload = acceptance
    expected.update(app_id="nullxoid_android", package_name="com.nullxoid.android")
    payload.update(app_id=expected["app_id"], package_name=expected["package_name"])
    payload["checks"] = {n: {"status": "pass", "evidence": ["result"]} for n in REQUIRED_CHECKS[expected["app_id"]]}
    args["primary_device_proof"].write_text(json.dumps(payload))
    args["secondary_device_proof"].write_text(json.dumps(payload | {"serial_hash": "2" * 64}))
    assert run_android_release_gate(**(args | {"app_id": expected["app_id"], "package_name": expected["package_name"]}))["ok"]


@pytest.mark.parametrize("missing", sorted(PUBLISH_REQUIRED_CHECKS))
def test_publish_requires_every_mandatory_gate_check(acceptance, missing):
    args, expected, _ = acceptance
    result = run_android_release_gate(**args)
    assert result["ok"]
    result["checks"] = [c for c in result["checks"] if c["name"] != missing]
    args["output"].write_text(json.dumps(result))
    assert "release_check_set" in validate_publish_verdict(
        args["output"], (args["primary_device_proof"], args["secondary_device_proof"]), expected)


@pytest.mark.parametrize("field", ["checks_total", "passed", "skipped", "required_failures", "warnings"])
def test_publish_summary_must_match_recorded_checks(acceptance, field):
    args, expected, _ = acceptance
    result = run_android_release_gate(**args)
    result["summary"][field] += 1
    args["output"].write_text(json.dumps(result))
    assert "release_summary_mismatch" in validate_publish_verdict(
        args["output"], (args["primary_device_proof"], args["secondary_device_proof"]), expected)


@pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
def test_proofs_require_utf8(acceptance, encoding):
    args, expected, payload = acceptance
    args["primary_device_proof"].write_bytes(json.dumps(payload).encode(encoding))
    assert not validate_device_proof(args["primary_device_proof"], expected)["valid"]
