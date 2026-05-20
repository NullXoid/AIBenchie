from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aibenchie_local
from aibenchie import release


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _matrix(path: Path, *, blocked_prerelease: bool = False) -> Path:
    payload = {
        "schema": release.WORKFLOW_MATRIX_SCHEMA,
        "schema_version": release.SCHEMA_VERSION,
        "suite": "echolabs",
        "workflows": [
            {
                "workflow_id": "text-to-video",
                "display_name": "Text to Video",
                "release_stage": "prerelease",
                "state": "blocked" if blocked_prerelease else "prerelease",
                "proof_path": "workflow-proofs/text-to-video",
                "blocked_reason": "not ready" if blocked_prerelease else None,
            }
        ],
    }
    _write_json(path, payload)
    return path


def _store(path: Path, *, include_mapping: bool = True) -> Path:
    payload = {
        "schema": release.STORE_CAPABILITIES_SCHEMA,
        "schema_version": release.SCHEMA_VERSION,
        "suite": "echolabs",
        "capabilities": [],
    }
    if include_mapping:
        payload["capabilities"].append(
            {
                "capability_id": "text-to-video",
                "display_name": "Text to Video",
                "release_stage": "prerelease",
                "state": "installable",
                "requires_nullbridge": True,
                "requires_backend": True,
                "requires_approval": False,
                "workflow_id": "text-to-video",
                "proof_path": "workflow-proofs/text-to-video",
                "blocked_reason": None,
            }
        )
    _write_json(path, payload)
    return path


def _proof(evidence_root: Path, build_id: str, *, expires_at: str | None = None) -> Path:
    proof_dir = evidence_root / build_id / "workflow-proofs" / "text-to-video"
    proof_dir.mkdir(parents=True, exist_ok=True)
    for filename in release.REQUIRED_WORKFLOW_PROOF_FILES:
        target = proof_dir / filename
        if filename.endswith(".json"):
            target.write_text("{}", encoding="utf-8")
        else:
            target.write_text("proof", encoding="utf-8")
    proof = {
        "schema_version": release.SCHEMA_VERSION,
        "workflow_id": "text-to-video",
        "release_stage": "prerelease",
        "android_submit_proof": True,
        "job_status_proof": True,
        "gallery_artifact_proof": True,
        "failure_message_proof": True,
        "aibenchie_verdict": "pass",
        "primary_device": "S23 FE",
        "secondary_device": "A17",
        "blocked_reason": None,
        "generated_at": "2026-05-20T00:00:00Z",
        "build_id": build_id,
    }
    if expires_at:
        proof["expires_at"] = expires_at
    _write_json(proof_dir / "workflow-proof.json", proof)
    _write_json(proof_dir / "aibenchie-verdict.json", {"ok": True, "verdict": "pass"})
    return proof_dir


def test_release_spine_verify_writes_latest_and_repo_commit_evidence(tmp_path):
    result = release.verify_release_spine(
        evidence_root=tmp_path,
        build_id="build-001",
        suite_version="0.9.0-prerelease.1",
    )

    assert result["ok"] is True
    assert result["build_id"] == "build-001"
    assert (tmp_path / "latest-build.json").exists()
    assert (tmp_path / "latest-verdict.json").exists()
    assert (tmp_path / "build-001" / "aibenchie-verdict.json").exists()
    repo_commits = json.loads((tmp_path / "build-001" / "repo-commits.json").read_text(encoding="utf-8"))
    assert repo_commits["schema"] == "aibenchie.repo-commits.v1"
    assert "AIBenchie" in {repo["name"] for repo in repo_commits["repos"]}


def test_failed_release_does_not_update_latest_passing(tmp_path):
    release.verify_release_spine(evidence_root=tmp_path, build_id="failed-001", verdict="fail")

    result = release.promote_passing_candidate(evidence_root=tmp_path, build_id="failed-001")

    assert result["ok"] is False
    assert "build_not_passing:fail" in result["failures"]
    assert not (tmp_path / "latest-passing.json").exists()


def test_promote_passing_rejects_missing_build(tmp_path):
    result = release.promote_passing_candidate(evidence_root=tmp_path, build_id="missing")

    assert result["ok"] is False
    assert "build_verdict_missing" in result["failures"]


def test_promote_passing_accepts_valid_passing_build(tmp_path):
    release.verify_release_spine(evidence_root=tmp_path, build_id="pass-001", verdict="pass")

    result = release.promote_passing_candidate(evidence_root=tmp_path, build_id="pass-001")
    latest = json.loads((tmp_path / "latest-passing.json").read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert latest["build_id"] == "pass-001"
    assert latest["status"] == "passing"


def test_generated_status_validation_rejects_missing_identity_fields():
    result = release.validate_status_payload({"status": "passing"})

    assert result["ok"] is False
    assert "missing_required_field:build_id" in result["failures"]
    assert "missing_required_field:expires_at" in result["failures"]


def test_expired_status_becomes_stale_not_healthy():
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)
    payload = {
        "schema_version": release.SCHEMA_VERSION,
        "build_id": "old",
        "suite_version": "0.9.0-prerelease.1",
        "generated_at": "2026-05-01T00:00:00Z",
        "expires_at": "2026-05-02T00:00:00Z",
        "status": "passing",
        "aibenchie_verdict": "pass",
        "source_commits": {},
    }

    result = release.validate_status_payload(payload, now=now)

    assert result["ok"] is False
    assert result["effective_status"] == "stale"
    assert "status_stale" in result["failures"]


def test_workflow_matrix_rejects_missing_proof_folder(tmp_path):
    result = release.validate_workflow_matrix(
        matrix=_matrix(tmp_path / "matrix.json"),
        store_capabilities=_store(tmp_path / "store.json"),
        evidence_root=tmp_path / "evidence",
        build_id="build-001",
    )

    assert result["ok"] is False
    assert any("text-to-video:missing_proof_file:workflow-proof.json" == item for item in result["failures"])


def test_workflow_matrix_rejects_blocked_workflow_marked_prerelease(tmp_path):
    _proof(tmp_path / "evidence", "build-001")

    result = release.validate_workflow_matrix(
        matrix=_matrix(tmp_path / "matrix.json", blocked_prerelease=True),
        store_capabilities=_store(tmp_path / "store.json"),
        evidence_root=tmp_path / "evidence",
        build_id="build-001",
    )

    assert result["ok"] is False
    assert "text-to-video:blocked_workflow_marked_prerelease" in result["failures"]


def test_workflow_matrix_rejects_missing_store_mapping(tmp_path):
    _proof(tmp_path / "evidence", "build-001")

    result = release.validate_workflow_matrix(
        matrix=_matrix(tmp_path / "matrix.json"),
        store_capabilities=_store(tmp_path / "store.json", include_mapping=False),
        evidence_root=tmp_path / "evidence",
        build_id="build-001",
    )

    assert result["ok"] is False
    assert "text-to-video:missing_store_capability_mapping" in result["failures"]


def test_workflow_matrix_rejects_stale_proof(tmp_path):
    _proof(
        tmp_path / "evidence",
        "build-001",
        expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
    )

    result = release.validate_workflow_matrix(
        matrix=_matrix(tmp_path / "matrix.json"),
        store_capabilities=_store(tmp_path / "store.json"),
        evidence_root=tmp_path / "evidence",
        build_id="build-001",
    )

    assert result["ok"] is False
    assert "text-to-video:proof_stale" in result["failures"]


def test_website_status_export_is_public_safe(tmp_path):
    release.verify_release_spine(evidence_root=tmp_path / "evidence", build_id="pass-001", verdict="pass")
    release.promote_passing_candidate(evidence_root=tmp_path / "evidence", build_id="pass-001")

    result = release.export_website_status(
        evidence_root=tmp_path / "evidence",
        out=tmp_path / "site" / "suite-status.json",
    )
    text = json.dumps(result).lower()

    assert result["schema"] == release.SUITE_STATUS_SCHEMA
    assert result["public_safe"] is True
    assert "c:\\users\\" not in text
    assert "192.168." not in text
    assert "service_token" not in text


def test_android_release_export_does_not_fake_missing_proof(tmp_path):
    release.verify_release_spine(evidence_root=tmp_path / "evidence", build_id="draft-001")

    result = release.export_android_release_status(
        evidence_root=tmp_path / "evidence",
        out=tmp_path / "android" / "android-release-status.json",
    )

    assert result["schema"] == release.ANDROID_RELEASE_STATUS_SCHEMA
    assert result["apk_sha256"] == ""
    assert result["signing_status"] == "missing"
    assert result["proof_missing"] is True
    assert result["summary"]["does_not_fake_missing_proof"] is True


def test_store_capability_export_blocks_prerelease_without_passing_candidate(tmp_path):
    release.verify_release_spine(evidence_root=tmp_path / "evidence", build_id="draft-001")

    result = release.export_store_capabilities(
        evidence_root=tmp_path / "evidence",
        store_capabilities=_store(tmp_path / "store.json"),
        out=tmp_path / "store" / "store-capability-stages.json",
    )

    assert result["capabilities"][0]["state"] == "blocked"
    assert result["capabilities"][0]["effective_release_stage"] == "blocked"
    assert result["capabilities"][0]["blocked_reason"] == "missing_passing_release_candidate"


def test_release_module_cli_verify(tmp_path, capsys):
    code = release.main(["verify", "--evidence-root", str(tmp_path), "--build-id", "cli-001", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["build_id"] == "cli-001"
    assert (tmp_path / "latest-build.json").exists()


def test_release_module_cli_promote_validate_and_exports(tmp_path, capsys):
    release.verify_release_spine(evidence_root=tmp_path / "evidence", build_id="cli-pass", verdict="pass")
    _proof(tmp_path / "evidence", "cli-pass")
    matrix = _matrix(tmp_path / "matrix.json")
    store = _store(tmp_path / "store.json")

    promote_code = release.main(
        [
            "promote-passing",
            "--evidence-root",
            str(tmp_path / "evidence"),
            "--build-id",
            "cli-pass",
            "--json",
        ]
    )
    promote_payload = json.loads(capsys.readouterr().out)
    validate_code = release.main(
        [
            "validate-workflows",
            "--evidence-root",
            str(tmp_path / "evidence"),
            "--build-id",
            "cli-pass",
            "--matrix",
            str(matrix),
            "--store-capabilities",
            str(store),
            "--json",
        ]
    )
    validate_payload = json.loads(capsys.readouterr().out)
    website_code = release.main(
        [
            "export-website-status",
            "--evidence-root",
            str(tmp_path / "evidence"),
            "--out",
            str(tmp_path / "site" / "suite-status.json"),
            "--json",
        ]
    )
    website_payload = json.loads(capsys.readouterr().out)
    android_code = release.main(
        [
            "export-android-release",
            "--evidence-root",
            str(tmp_path / "evidence"),
            "--out",
            str(tmp_path / "android" / "android-release-status.json"),
            "--json",
        ]
    )
    android_payload = json.loads(capsys.readouterr().out)
    store_code = release.main(
        [
            "export-store-capabilities",
            "--evidence-root",
            str(tmp_path / "evidence"),
            "--store-capabilities",
            str(store),
            "--out",
            str(tmp_path / "store" / "store-capability-stages.json"),
            "--json",
        ]
    )
    store_payload = json.loads(capsys.readouterr().out)

    assert promote_code == 0
    assert promote_payload["ok"] is True
    assert validate_code == 0
    assert validate_payload["ok"] is True
    assert website_code == 0
    assert website_payload["schema"] == release.SUITE_STATUS_SCHEMA
    assert android_code == 0
    assert android_payload["schema"] == release.ANDROID_RELEASE_STATUS_SCHEMA
    assert store_code == 0
    assert store_payload["schema"] == release.STORE_CAPABILITY_STAGES_SCHEMA
    assert (tmp_path / "evidence" / "latest-passing.json").exists()
    assert (tmp_path / "site" / "suite-status.json").exists()
    assert (tmp_path / "android" / "android-release-status.json").exists()
    assert (tmp_path / "store" / "store-capability-stages.json").exists()


def test_aibenchie_local_release_spine_compat_flags(tmp_path, capsys):
    code = aibenchie_local.main(
        [
            "--release-spine-verify",
            "--release-spine-evidence-root",
            str(tmp_path),
            "--release-spine-build-id",
            "compat-001",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["build_id"] == "compat-001"
    assert (tmp_path / "latest-verdict.json").exists()


def test_aibenchie_local_release_spine_promote_and_validate_flags(tmp_path, capsys):
    release.verify_release_spine(evidence_root=tmp_path / "evidence", build_id="compat-pass", verdict="pass")
    _proof(tmp_path / "evidence", "compat-pass")
    matrix = _matrix(tmp_path / "matrix.json")
    store = _store(tmp_path / "store.json")

    promote_code = aibenchie_local.main(
        [
            "--release-spine-promote-passing",
            "--release-spine-evidence-root",
            str(tmp_path / "evidence"),
            "--release-spine-build-id",
            "compat-pass",
            "--json",
        ]
    )
    promote_payload = json.loads(capsys.readouterr().out)
    validate_code = aibenchie_local.main(
        [
            "--release-spine-validate-workflows",
            "--release-spine-evidence-root",
            str(tmp_path / "evidence"),
            "--release-spine-build-id",
            "compat-pass",
            "--release-spine-workflow-matrix",
            str(matrix),
            "--release-spine-store-capabilities",
            str(store),
            "--json",
        ]
    )
    validate_payload = json.loads(capsys.readouterr().out)

    assert promote_code == 0
    assert promote_payload["ok"] is True
    assert validate_code == 0
    assert validate_payload["ok"] is True
