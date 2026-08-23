from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from aibenchie import release


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _repo_commits(build_id: str) -> dict:
    return {
        "schema": "aibenchie.repo-commits.v1",
        "schema_version": release.SCHEMA_VERSION,
        "build_id": build_id,
        "generated_at": "2026-05-21T12:00:00Z",
        "repos": [
            {"name": "AIBenchie", "branch": "main", "commit": "abc123", "dirty": False, "pushed": True},
            {"name": "NullXoidAndroid", "branch": "main", "commit": "def456", "dirty": False, "pushed": True},
            {"name": "NullBridge", "branch": "main", "commit": "fed321", "dirty": False, "pushed": True},
            {"name": "Lv7", "branch": "main", "commit": "789abc", "dirty": False, "pushed": True},
        ],
    }


def _failed_rehearsal(build_id: str) -> dict:
    payload = {
        "schema_version": release.SCHEMA_VERSION,
        "build_id": build_id,
        "result": "pass",
        "generated_at": "2026-05-21T12:00:00Z",
        "latest_passing_changed": False,
    }
    for field in release.FAILED_CANDIDATE_REQUIRED_BLOCKS:
        payload[field] = True
    return payload


def _valid_suite_evidence(evidence_root: Path, build_id: str) -> Path:
    root = evidence_root / build_id
    common = {
        "schema_version": release.SCHEMA_VERSION,
        "build_id": build_id,
        "suite_version": release.DEFAULT_SUITE_VERSION,
        "generated_at": "2026-05-21T12:00:00Z",
        "result": "pass",
        "aibenchie_verdict": "pass",
    }
    _write_json(root / "repo-commits.json", _repo_commits(build_id))
    _write_json(root / "suite-status.json", {**common, "status": "prerelease-candidate"})
    _write_json(
        root / "android-release-status.json",
        {
            **common,
            "status": "gated",
            "apk_hashes_present": "pass",
            "signing_continuity": "pass",
            "s23_fe_proof": "pass",
            "a17_proof": "pass",
            "update_notes_present": "pass",
            "publish_state": "gated",
            "apk_publish_occurred": False,
            "latest_debug_moved": False,
        },
    )
    _write_json(root / "store-capability-stages.json", {**common, "status": "pass"})
    _write_json(root / "workflow-matrix-verdict.json", {**common, "verdict": "pass", "ok": True})
    _write_json(
        root / "public-safe-scan.json",
        {**common, "public_safe": True, "private_markers_found": 0, "scanned_files": 9},
    )
    _write_json(
        root / "release-rehearsal.json",
        {
            **common,
            "clean_worktree_rehearsal": True,
            "uncommitted_source_required": False,
            "promotion_status": "not_promoted",
        },
    )
    _write_json(root / "failed-candidate-rehearsal.json", _failed_rehearsal(build_id))
    _write_json(
        root / "status-agreement.json",
        {
            **common,
            "surfaces": {
                "aibenchie": {"build_id": build_id, "verdict": "pass"},
                "website": {"build_id": build_id, "verdict": "pass"},
                "home": {"build_id": build_id, "verdict": "pass"},
                "android": {"build_id": build_id, "verdict": "pass"},
                "store": {"build_id": build_id, "verdict": "pass"},
                "release_notes": {"build_id": build_id, "verdict": "pass"},
            },
        },
    )
    _write_json(
        root / "website-export" / "summary.json",
        {**common, "npm_export_public": "pass", "npm_build": "pass", "npm_verify_public": "pass", "website_deploy_occurred": False},
    )
    _write_json(
        root / "home-export" / "summary.json",
        {**common, "nullbridge_status_export": "pass", "suite_status_export": "pass", "topology_verification": "pass", "home_deploy_occurred": False},
    )
    _write_json(
        root / "nullbridge-proof" / "nullbridge-prerelease-verdict.json",
        {
            "schema_version": release.SCHEMA_VERSION,
            "build_id": "ms4-nullbridge-postcommit",
            "aibenchie_verdict": "pass",
            "verdict": "pass",
            "ok": True,
        },
    )
    _write_json(
        root / "lv7-proof" / "lv7-operator-loop-verdict.json",
        {
            "schema_version": release.SCHEMA_VERSION,
            "build_id": "ms5-lv7-local",
            "aibenchie_verdict": "pass",
            "verdict": "pass",
            "ok": True,
        },
    )
    _write_json(
        root / "store-proof" / "store-addons-verdict.json",
        {
            "schema_version": release.SCHEMA_VERSION,
            "build_id": "ms6-store-20260521-0001",
            "aibenchie_verdict": "pass",
            "verdict": "pass",
            "ok": True,
        },
    )
    (root / "release-notes.md").write_text(f"# Elabs MS7 Candidate\n\nBuild: {build_id}\n", encoding="utf-8")
    (root / "notes.md").write_text(f"MS7 local candidate evidence for {build_id}.\n", encoding="utf-8")
    return root


def test_suite_candidate_validator_accepts_valid_evidence(tmp_path):
    build_id = "ms7-candidate-test"
    root = _valid_suite_evidence(tmp_path, build_id)

    result = release.validate_suite_candidate(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 21, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is True
    assert result["schema"] == release.SUITE_CANDIDATE_VERDICT_SCHEMA
    assert result["verdict"] == "pass"
    assert result["suite_version"] == release.DEFAULT_SUITE_VERSION
    assert result["source_commits"]["AIBenchie"] == "abc123"
    assert result["promotion_status"] == "not_promoted"
    assert (root / "suite-verdict.json").exists()
    assert (root / "aibenchie-verdict.json").exists()
    release_payload = json.loads((root / "aibenchie-verdict.json").read_text(encoding="utf-8"))
    assert release_payload["suite_version"] == release.DEFAULT_SUITE_VERSION
    assert release_payload["source_commits"]["AIBenchie"] == "abc123"


def test_suite_candidate_validator_blocks_missing_release_notes(tmp_path):
    build_id = "ms7-missing-notes"
    root = _valid_suite_evidence(tmp_path, build_id)
    (root / "release-notes.md").unlink()

    result = release.validate_suite_candidate(evidence_root=tmp_path, build_id=build_id)

    assert result["ok"] is False
    assert "release-notes.md:missing" in result["failures"]


def test_suite_candidate_validator_blocks_public_unsafe_output(tmp_path):
    build_id = "ms7-unsafe"
    root = _valid_suite_evidence(tmp_path, build_id)
    payload = json.loads((root / "public-safe-scan.json").read_text(encoding="utf-8"))
    payload["unsafe"] = "C:" + "\\Users" + "\\Example\\candidate.txt"
    _write_json(root / "public-safe-scan.json", payload)

    result = release.validate_suite_candidate(evidence_root=tmp_path, build_id=build_id)

    assert result["ok"] is False
    assert any(failure.endswith(":public_safety_marker") for failure in result["failures"])


def test_suite_candidate_validator_blocks_status_mismatch(tmp_path):
    build_id = "ms7-status-mismatch"
    root = _valid_suite_evidence(tmp_path, build_id)
    payload = json.loads((root / "status-agreement.json").read_text(encoding="utf-8"))
    payload["surfaces"]["website"]["build_id"] = "other-build"
    _write_json(root / "status-agreement.json", payload)

    result = release.validate_suite_candidate(evidence_root=tmp_path, build_id=build_id)

    assert result["ok"] is False
    assert "status-agreement.json:website:build_id:mismatch" in result["failures"]


def test_suite_candidate_validator_blocks_release_movement(tmp_path):
    build_id = "ms7-release-movement"
    root = _valid_suite_evidence(tmp_path, build_id)
    payload = json.loads((root / "release-rehearsal.json").read_text(encoding="utf-8"))
    payload["latest_passing_promoted"] = True
    _write_json(root / "release-rehearsal.json", payload)

    result = release.validate_suite_candidate(evidence_root=tmp_path, build_id=build_id)

    assert result["ok"] is False
    assert "release-rehearsal.json:latest_passing_promoted:not_allowed" in result["failures"]


def test_release_module_cli_validates_suite_candidate(tmp_path, capsys):
    build_id = "ms7-cli"
    _valid_suite_evidence(tmp_path, build_id)

    code = release.main(
        [
            "validate-suite",
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


def test_assemble_suite_candidate_accepts_fresh_subgate_builds(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence"
    build_id = "ms7-fresh-candidate"
    workflow_build_id = "ms3-live-20260622-190145"

    monkeypatch.setattr(
        release,
        "collect_repo_commit_evidence",
        lambda: (
            _repo_commits(build_id),
            {
                "AIBenchie": "abc123",
                "NullXoidAndroid": "def456",
                "NullBridge": "fed321",
                "Lv7": "789abc",
            },
        ),
    )

    _write_json(
        evidence / workflow_build_id / "workflow-matrix-verdict.json",
        {
            "schema": release.WORKFLOW_MATRIX_VERDICT_SCHEMA,
            "schema_version": release.SCHEMA_VERSION,
            "build_id": workflow_build_id,
            "generated_at": "2026-06-22T23:24:43Z",
            "ok": True,
            "aibenchie_verdict": "pass",
            "failures": [],
            "workflow_count": 14,
            "prerelease_count": 7,
            "frozen_prerelease_workflows": ["standard-prompt-image"],
            "validated_prerelease_workflows": ["standard-prompt-image"],
        },
    )
    _write_json(
        tmp_path / "android-status.json",
        {
            "schema": "nullxoid.android-release-status.v1",
            "aibenchie_verdict": "pass",
            "app_id": "nullxoid_android",
            "package_name": "com.nullxoid.android",
            "app_version": "0.2.0-alpha.1",
            "version_code": "98",
            "publish_state": "ready_to_publish",
            "signing_status": "pass",
            "signing_fingerprint_match": True,
            "apk": {"present": True, "sha256": "abc"},
            "update_notes": {"present": True},
            "proof": {
                "primary": {"present": True},
                "secondary": {"present": True},
            },
        },
    )
    for subgate_build_id, relative_path, schema in (
        ("ms4-nullbridge-refresh", "nullbridge-proof/nullbridge-prerelease-verdict.json", release.NULLBRIDGE_PRERELEASE_VERDICT_SCHEMA),
        ("ms5-lv7-refresh", "lv7-proof/lv7-operator-loop-verdict.json", release.LV7_OPERATOR_LOOP_VERDICT_SCHEMA),
        ("ms6-store-refresh", "store-proof/store-addons-verdict.json", release.STORE_ADDONS_VERDICT_SCHEMA),
    ):
        _write_json(
            evidence / subgate_build_id / relative_path,
            {
                "schema": schema,
                "schema_version": release.SCHEMA_VERSION,
                "build_id": subgate_build_id,
                "generated_at": "2026-06-22T23:24:43Z",
                "ok": True,
                "aibenchie_verdict": "pass",
                "verdict": "pass",
            },
        )

    result = release.assemble_suite_candidate(
        build_id=build_id,
        workflow_build_id=workflow_build_id,
        evidence_root=evidence,
        android_status=tmp_path / "android-status.json",
        nullbridge_build_id="ms4-nullbridge-refresh",
        lv7_build_id="ms5-lv7-refresh",
        store_build_id="ms6-store-refresh",
        now=datetime(2026, 6, 22, 23, 30, tzinfo=timezone.utc),
    )

    assert result["ok"] is True
    workflow = json.loads((evidence / build_id / "workflow-matrix-verdict.json").read_text(encoding="utf-8"))
    assert workflow["build_id"] == build_id
    assert workflow["source_build_id"] == workflow_build_id
    validation = release.validate_suite_candidate(
        evidence_root=evidence,
        build_id=build_id,
        now=datetime(2026, 6, 22, 23, 31, tzinfo=timezone.utc),
    )
    assert validation["ok"] is True
