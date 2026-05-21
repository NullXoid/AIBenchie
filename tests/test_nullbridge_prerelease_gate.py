from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aibenchie import release


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _proof(
    build_id: str,
    proof_type: str,
    *,
    status: str = "pass",
    aibenchie_verdict: str = "pass",
    extra: dict | None = None,
) -> dict:
    payload = {
        "schema_version": release.SCHEMA_VERSION,
        "build_id": build_id,
        "component": "NullBridge",
        "proof_type": proof_type,
        "status": status,
        "generated_at": "2026-05-20T12:00:00Z",
        "source_commit": "abc123",
        "public_safe": True,
        "raw_evidence_local_only": True,
        "aibenchie_verdict": aibenchie_verdict,
        "blocked_reason": None,
        "checks": [{"name": "required_check", "status": "pass"}],
    }
    if extra:
        payload.update(extra)
    return payload


def _ms4_nullbridge_evidence(evidence_root: Path, build_id: str, *, expires_at: str = "2099-05-20T12:10:00Z") -> Path:
    proof_root = evidence_root / build_id / "nullbridge-proof"
    for filename, proof_type in release.NULLBRIDGE_REQUIRED_PROOFS.items():
        _write_json(proof_root / filename, _proof(build_id, proof_type))
    _write_json(
        proof_root / "nullbridge-status.json",
        {
            "schema_version": release.SCHEMA_VERSION,
            "build_id": build_id,
            "generated_at": "2026-05-20T12:00:00Z",
            "expires_at": expires_at,
            "source_commit": "abc123",
            "status": "pass",
            "verdict": "pass",
            "aibenchie_verdict": "pass",
            "freshness": "fresh",
            "required_for_prerelease": True,
            "checks": {
                "pairing": "pass",
                "approval": "pass",
                "denial": "pass",
                "route_safety": "pass",
                "leases": "pass",
                "artifact_response": "pass",
                "signed_envelopes": "pass",
                "audit_redaction": "pass",
                "status_offline_unavailable": "pass",
                "android_failure_messaging": "pass",
            },
            "counts": {"proof_pass": 10, "proof_fail": 0},
            "public_safe_message": "NullBridge prerelease gate passed.",
            "blocked_reason": None,
        },
    )
    _write_json(
        proof_root / "nullbridge-prerelease-verdict.json",
        {
            "schema_version": release.SCHEMA_VERSION,
            "build_id": build_id,
            "suite": "echolabs",
            "component": "NullBridge",
            "verdict": "pass",
            "generated_at": "2026-05-20T12:00:00Z",
            "expires_at": expires_at,
            "blocked_reason": None,
        },
    )
    (proof_root / "notes.md").write_text("NullBridge MS4 gate passed.\n", encoding="utf-8")
    return proof_root


def test_nullbridge_prerelease_validator_accepts_valid_evidence(tmp_path):
    build_id = "ms4-nullbridge-test"
    proof_root = _ms4_nullbridge_evidence(tmp_path, build_id)

    result = release.validate_nullbridge_prerelease(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is True
    assert result["schema"] == release.NULLBRIDGE_PRERELEASE_VERDICT_SCHEMA
    assert result["verdict"] == "pass"
    assert result["route_safety"] == "pass"
    assert result["android_failure_messaging"] == "pass"
    written = json.loads((proof_root / "nullbridge-prerelease-verdict.json").read_text(encoding="utf-8"))
    assert written["schema"] == release.NULLBRIDGE_PRERELEASE_VERDICT_SCHEMA
    assert written["aibenchie_verdict"] == "pass"


def test_nullbridge_prerelease_validator_blocks_missing_proof(tmp_path):
    build_id = "ms4-nullbridge-missing"
    proof_root = _ms4_nullbridge_evidence(tmp_path, build_id)
    (proof_root / "lease-proof.json").unlink()

    result = release.validate_nullbridge_prerelease(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is False
    assert result["verdict"] == "blocked"
    assert "lease-proof.json:missing" in result["failures"]


def test_nullbridge_prerelease_validator_blocks_stale_status(tmp_path):
    build_id = "ms4-nullbridge-stale"
    stale = (datetime(2026, 5, 20, 11, 59, tzinfo=timezone.utc)).isoformat().replace("+00:00", "Z")
    _ms4_nullbridge_evidence(tmp_path, build_id, expires_at=stale)

    result = release.validate_nullbridge_prerelease(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is False
    assert "nullbridge-status.json:expires_at:stale" in result["failures"]


def test_nullbridge_prerelease_validator_blocks_private_markers(tmp_path):
    build_id = "ms4-nullbridge-private"
    proof_root = _ms4_nullbridge_evidence(tmp_path, build_id)
    proof_path = proof_root / "artifact-response-proof.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["unsafe"] = "C:" + "\\Users" + "\\Example\\private.txt"
    _write_json(proof_path, proof)

    result = release.validate_nullbridge_prerelease(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is False
    assert any(failure.endswith(":public_safety_marker") for failure in result["failures"])


def test_release_module_cli_validates_nullbridge_evidence(tmp_path, capsys):
    build_id = "ms4-nullbridge-cli"
    _ms4_nullbridge_evidence(tmp_path, build_id)

    code = release.main(
        [
            "validate-nullbridge",
            "--evidence-root",
            str(tmp_path),
            "--build-id",
            build_id,
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["aibenchie_verdict"] == "pass"
