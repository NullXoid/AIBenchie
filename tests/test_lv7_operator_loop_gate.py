from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from aibenchie import release


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _proof(build_id: str, proof_type: str, *, extra: dict | None = None) -> dict:
    payload = {
        "schema_version": release.SCHEMA_VERSION,
        "build_id": build_id,
        "component": "Lv-7",
        "proof_type": proof_type,
        "status": "pass",
        "generated_at": "2026-05-20T12:00:00Z",
        "source_commit": "abc123",
        "public_safe": True,
        "raw_evidence_local_only": True,
        "aibenchie_verdict": "pass",
        "blocked_reason": None,
        "checks": [{"name": "required_check", "status": "pass"}],
    }
    if extra:
        payload.update(extra)
    return payload


def _valid_lv7_evidence(evidence_root: Path, build_id: str, *, expires_at: str = "2099-05-20T12:10:00Z") -> Path:
    proof_root = evidence_root / build_id / "lv7-proof"
    for filename, proof_type in release.LV7_REQUIRED_PROOFS.items():
        extra: dict = {}
        if proof_type in {"approval-result-history", "android-visible-history"}:
            extra = {"states": sorted(release.LV7_REQUIRED_HISTORY_STATES), "android_visible": True, "messages_public_safe": True}
        if proof_type == "repair-preflight":
            extra = {
                "dry_run_required": True,
                "exact_operations_required": True,
                "hidden_mutation_blocked": True,
                "operations": [
                    {
                        "operation_id": "op-1",
                        "target": "diagnostics",
                        "reason": "test",
                        "risk": "low",
                        "required_approval": True,
                        "expected_result": "test result",
                        "rollback_or_undo_note": "no mutation",
                        "resource_requirements": {"uses_existing_resource_manager": True},
                        "policy_gate_result": "ask",
                        "preflight_result": "pass",
                    }
                ],
            }
        if proof_type == "repair-approval-boundary":
            extra = {
                "execution_without_approval_blocked": True,
                "hidden_mutation_blocked": True,
                "fail_closed": {"denied": True, "expired": True, "missing": True, "revoked": True},
            }
        if proof_type == "artifact-package":
            extra = {
                "export_mode": "local",
                "public_safe_manifest": True,
                "checksums_present": True,
                "nextcloud": {"required": False, "status": "skipped_optional", "reason": "not configured"},
            }
        if proof_type == "sanitized-status":
            extra = {"private_markers_rejected": True, "stale_not_healthy": True}
        if proof_type == "policy-resource-memory":
            extra = {
                "uses_existing_resource_manager": True,
                "does_not_create_second_lease_system": True,
                "model_intent_policy_gated": True,
                "model_intent_resource_aware": True,
                "memory_sanitized_summary_only": True,
            }
        if proof_type == "gcli":
            extra = {"compact_readable": True, "normal_output_public_safe": True}
        _write_json(proof_root / filename, _proof(build_id, proof_type, extra=extra))
    _write_json(
        proof_root / "lv7-operator-status.json",
        {
            "schema_version": release.SCHEMA_VERSION,
            "build_id": build_id,
            "generated_at": "2026-05-20T12:00:00Z",
            "expires_at": expires_at,
            "status": "pass",
            "freshness": "fresh",
            "component": "Lv-7",
            "repair_preflight": {"hidden_mutation_blocked": True},
        },
    )
    _write_json(
        proof_root / "lv7-operator-loop-verdict.json",
        {
            "schema_version": release.SCHEMA_VERSION,
            "build_id": build_id,
            "component": "Lv-7",
            "verdict": "pass",
            "generated_at": "2026-05-20T12:00:00Z",
            "expires_at": expires_at,
            "blocked_reason": None,
        },
    )
    _write_json(
        proof_root / "local-package-manifest.json",
        {
            "schema_version": release.SCHEMA_VERSION,
            "package_id": "pkg-1",
            "build_id": build_id,
            "created_at": "2026-05-20T12:00:00Z",
            "export_mode": "local",
            "artifact_count": 1,
            "artifacts": [{"artifact_id": "summary", "name": "summary.txt", "sha256": "abc"}],
            "checksums": {"summary.txt": "abc"},
            "public_safe": True,
            "retention": {"cleanup_supported": True},
            "nextcloud": {"required": False, "status": "skipped_optional", "reason": "not configured"},
        },
    )
    _write_json(
        proof_root / "local-package-checksums.json",
        {
            "schema_version": release.SCHEMA_VERSION,
            "package_id": "pkg-1",
            "build_id": build_id,
            "created_at": "2026-05-20T12:00:00Z",
            "checksums": {"summary.txt": "abc"},
            "public_safe": True,
        },
    )
    (proof_root / "notes.md").write_text("Lv-7 MS5 gate passed.\n", encoding="utf-8")
    return proof_root


def test_lv7_operator_loop_validator_accepts_valid_evidence(tmp_path):
    build_id = "ms5-lv7-test"
    _valid_lv7_evidence(tmp_path, build_id)

    result = release.validate_lv7_operator_loop(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is True
    assert result["schema"] == release.LV7_OPERATOR_LOOP_VERDICT_SCHEMA
    assert result["verdict"] == "pass"
    assert result["repair_preflight"] == "pass"
    assert result["artifact_package_export"] == "pass"


def test_lv7_operator_loop_validator_blocks_missing_proof(tmp_path):
    build_id = "ms5-lv7-missing"
    proof_root = _valid_lv7_evidence(tmp_path, build_id)
    (proof_root / "repair-preflight-proof.json").unlink()

    result = release.validate_lv7_operator_loop(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is False
    assert "repair-preflight-proof.json:missing" in result["failures"]


def test_lv7_operator_loop_validator_blocks_hidden_mutation(tmp_path):
    build_id = "ms5-lv7-hidden-mutation"
    proof_root = _valid_lv7_evidence(tmp_path, build_id)
    proof_path = proof_root / "repair-preflight-proof.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["hidden_mutation_blocked"] = False
    _write_json(proof_path, proof)

    result = release.validate_lv7_operator_loop(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is False
    assert "repair-preflight-proof.json:hidden_mutation_blocked:not_true" in result["failures"]


def test_lv7_operator_loop_validator_blocks_nextcloud_required_by_default(tmp_path):
    build_id = "ms5-lv7-nextcloud-required"
    proof_root = _valid_lv7_evidence(tmp_path, build_id)
    manifest_path = proof_root / "local-package-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["nextcloud"]["required"] = True
    _write_json(manifest_path, manifest)

    result = release.validate_lv7_operator_loop(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is False
    assert "local-package-manifest.json:nextcloud:required_by_default" in result["failures"]


def test_lv7_operator_loop_validator_blocks_private_markers(tmp_path):
    build_id = "ms5-lv7-private"
    proof_root = _valid_lv7_evidence(tmp_path, build_id)
    proof_path = proof_root / "artifact-package-proof.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["unsafe"] = "C:" + "\\Users" + "\\Example\\private.txt"
    _write_json(proof_path, proof)

    result = release.validate_lv7_operator_loop(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is False
    assert any(failure.endswith(":public_safety_marker") for failure in result["failures"])


def test_release_module_cli_validates_lv7_evidence(tmp_path, capsys):
    build_id = "ms5-lv7-cli"
    _valid_lv7_evidence(tmp_path, build_id)

    code = release.main(
        [
            "validate-lv7",
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
