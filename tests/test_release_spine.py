from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import aibenchie_local
from aibenchie import release


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _test_private_windows_path() -> str:
    return "C:" + "\\Users" + "\\Example" + "\\private" + "\\artifact" + ".mp4"


def _test_private_ip() -> str:
    return "192" + ".168.1.10"


def _test_token_marker() -> str:
    return "to" + "ken=se" + "cret"


def _test_raw_serial(label: str) -> str:
    return "RAW-" + label + "-SERIAL"


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
                "store_profile_id": "video-text-alpha",
                "provider_workflow": "video_default",
                "artifact_kind": "video",
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
        "artifact_open_proof": True,
        "artifact_save_proof": True,
        "failure_message_proof": True,
        "aibenchie_verdict": "pass",
        "primary_device": "S23 FE",
        "secondary_device": "A17",
        "device_proof_order": ["S23 FE", "A17"],
        "devices": [{"alias": "S23 FE"}, {"alias": "A17"}],
        "store_profile_id": "video-text-alpha",
        "provider_workflow": "video_default",
        "provider_backing": "real",
        "real_provider_proof": True,
        "mock_backed": False,
        "artifact_kind": "video",
        "artifact_validation": {
            "ok": True,
            "artifact_kind": "video",
            "validationStatus": "passed",
            "videoStreamCount": 1,
        },
        "blocked_reason": None,
        "generated_at": "2026-05-20T00:00:00Z",
        "build_id": build_id,
    }
    if expires_at:
        proof["expires_at"] = expires_at
    _write_json(proof_dir / "workflow-proof.json", proof)
    _write_json(proof_dir / "aibenchie-verdict.json", {"ok": True, "verdict": "pass"})
    return proof_dir


def _ms3_matrix(path: Path, *, unsafe_display_name: bool = False) -> Path:
    workflows = []
    for workflow_id, expected in release.EXPECTED_MS3_PRERELEASE_WORKFLOWS.items():
        workflows.append(
            {
                "workflow_id": workflow_id,
                "display_name": _test_private_windows_path()
                if unsafe_display_name and workflow_id == "text-to-video"
                else workflow_id.replace("-", " ").title(),
                "release_stage": "prerelease",
                "state": "prerelease",
                "store_profile_id": expected["store_profile_id"],
                "provider_workflow": expected["provider_workflow"],
                "artifact_kind": expected["artifact_kind"],
                "audio_mode": expected.get("audio_mode", ""),
                "proof_path": f"workflow-proofs/{workflow_id}",
                "blocked_reason": None,
            }
        )
    workflows.append(
        {
            "workflow_id": "masked-edit",
            "display_name": "Masked Edit",
            "release_stage": "blocked",
            "state": "blocked",
            "proof_path": "workflow-proofs/masked-edit",
            "blocked_reason": "Waiting for FLUX Fill/inpaint proof.",
        }
    )
    _write_json(
        path,
        {
            "schema": release.WORKFLOW_MATRIX_SCHEMA,
            "schema_version": release.SCHEMA_VERSION,
            "suite": "echolabs",
            "frozen_prerelease_workflows": list(release.EXPECTED_MS3_PRERELEASE_WORKFLOWS),
            "workflows": workflows,
        },
    )
    return path


def _ms3_store(path: Path) -> Path:
    capabilities = []
    for workflow_id, expected in release.EXPECTED_MS3_PRERELEASE_WORKFLOWS.items():
        capabilities.append(
            {
                "capability_id": workflow_id,
                "workflow_id": workflow_id,
                "display_name": workflow_id.replace("-", " ").title(),
                "release_stage": "prerelease",
                "state": "installable",
                "store_profile_id": expected["store_profile_id"],
                "provider_workflow": expected["provider_workflow"],
                "artifact_kind": expected["artifact_kind"],
                "audio_mode": expected.get("audio_mode", ""),
                "proof_path": f"workflow-proofs/{workflow_id}",
                "blocked_reason": None,
            }
        )
    capabilities.append(
        {
            "capability_id": "masked-edit",
            "workflow_id": "masked-edit",
            "display_name": "Masked Edit",
            "release_stage": "blocked",
            "state": "blocked",
            "proof_path": "workflow-proofs/masked-edit",
            "blocked_reason": "Waiting for FLUX Fill/inpaint proof.",
        }
    )
    _write_json(
        path,
        {
            "schema": release.STORE_CAPABILITIES_SCHEMA,
            "schema_version": release.SCHEMA_VERSION,
            "suite": "echolabs",
            "capabilities": capabilities,
        },
    )
    return path


def _ms3_proof_set(evidence_root: Path, build_id: str) -> None:
    for workflow_id, expected in release.EXPECTED_MS3_PRERELEASE_WORKFLOWS.items():
        proof_dir = evidence_root / build_id / "workflow-proofs" / workflow_id
        proof_dir.mkdir(parents=True, exist_ok=True)
        for filename in release.REQUIRED_WORKFLOW_PROOF_FILES:
            target = proof_dir / filename
            if filename.endswith(".json"):
                target.write_text("{}", encoding="utf-8")
            else:
                target.write_text("proof", encoding="utf-8")
        validation = {
            "ok": True,
            "artifact_kind": expected["artifact_kind"],
            "validationStatus": "passed",
            "artifactId": f"{workflow_id}-artifact",
        }
        if expected["artifact_kind"] == "video":
            validation["videoStreamCount"] = 1
        if workflow_id in release.AUDIO_WORKFLOW_IDS:
            validation.update(
                {
                    "hasAudio": True,
                    "audioStreamCount": 1,
                    "audioDurationMs": 4000,
                    "videoDurationMs": 4020,
                    "nonSilentAudio": True,
                    "durationCompatible": True,
                    "validationFailureReason": "",
                }
            )
        if expected["artifact_kind"] == "model3d":
            validation["output_formats"] = ["glb"]
        proof = {
            "schema_version": release.SCHEMA_VERSION,
            "workflow_id": workflow_id,
            "release_stage": "prerelease",
            "android_submit_proof": True,
            "job_status_proof": True,
            "gallery_artifact_proof": True,
            "artifact_open_proof": True,
            "artifact_save_proof": True,
            "failure_message_proof": True,
            "aibenchie_verdict": "pass",
            "primary_device": "S23 FE",
            "secondary_device": "A17",
            "device_proof_order": ["S23 FE", "A17"],
            "devices": [
                {"alias": "S23 FE", "serial": _test_raw_serial("S23")},
                {"alias": "A17", "serial": _test_raw_serial("A17")},
            ],
            "store_profile_id": expected["store_profile_id"],
            "provider_workflow": expected["provider_workflow"],
            "provider_backing": "real",
            "real_provider_proof": True,
            "mock_backed": False,
            "artifact_kind": expected["artifact_kind"],
            "artifact_validation": validation,
            "audio_mode": expected.get("audio_mode", ""),
            "blocked_reason": None,
            "generated_at": "2026-05-20T00:00:00Z",
            "build_id": build_id,
        }
        _write_json(proof_dir / "workflow-proof.json", proof)
        _write_json(proof_dir / "aibenchie-verdict.json", {"ok": True, "verdict": "pass"})
        (proof_dir / "raw-provider-log.txt").write_text(
            f"{_test_private_windows_path()} {_test_token_marker()} {_test_private_ip()}",
            encoding="utf-8",
        )


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


def test_workflow_matrix_rejects_mock_backed_proof(tmp_path):
    proof_dir = _proof(tmp_path / "evidence", "build-001")
    proof = json.loads((proof_dir / "workflow-proof.json").read_text(encoding="utf-8"))
    proof["provider_backing"] = "mock"
    _write_json(proof_dir / "workflow-proof.json", proof)

    result = release.validate_workflow_matrix(
        matrix=_matrix(tmp_path / "matrix.json"),
        store_capabilities=_store(tmp_path / "store.json"),
        evidence_root=tmp_path / "evidence",
        build_id="build-001",
    )

    assert result["ok"] is False
    assert "text-to-video:mock_provider_detected:provider_backing" in result["failures"]


def test_workflow_matrix_rejects_wrong_device_order(tmp_path):
    proof_dir = _proof(tmp_path / "evidence", "build-001")
    proof = json.loads((proof_dir / "workflow-proof.json").read_text(encoding="utf-8"))
    proof["device_proof_order"] = ["A17", "S23 FE"]
    _write_json(proof_dir / "workflow-proof.json", proof)

    result = release.validate_workflow_matrix(
        matrix=_matrix(tmp_path / "matrix.json"),
        store_capabilities=_store(tmp_path / "store.json"),
        evidence_root=tmp_path / "evidence",
        build_id="build-001",
    )

    assert result["ok"] is False
    assert "text-to-video:device_order_invalid" in result["failures"]


def test_workflow_matrix_writes_aggregate_verdict(tmp_path):
    _proof(tmp_path / "evidence", "build-001")

    result = release.validate_workflow_matrix(
        matrix=_matrix(tmp_path / "matrix.json"),
        store_capabilities=_store(tmp_path / "store.json"),
        evidence_root=tmp_path / "evidence",
        build_id="build-001",
    )

    verdict_path = tmp_path / "evidence" / "build-001" / "workflow-matrix-verdict.json"
    payload = json.loads(verdict_path.read_text(encoding="utf-8"))
    assert result["ok"] is True
    assert payload["schema"] == release.WORKFLOW_MATRIX_VERDICT_SCHEMA
    assert payload["aibenchie_verdict"] == "pass"


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


def test_website_status_export_can_select_current_verdict(tmp_path):
    release.verify_release_spine(evidence_root=tmp_path / "evidence", build_id="pass-001", verdict="pass")
    release.promote_passing_candidate(evidence_root=tmp_path / "evidence", build_id="pass-001")
    release.verify_release_spine(evidence_root=tmp_path / "evidence", build_id="current-001")

    latest_passing = release.export_website_status(
        evidence_root=tmp_path / "evidence",
        out=tmp_path / "site" / "suite-status-passing.json",
    )
    current = release.export_website_status(
        evidence_root=tmp_path / "evidence",
        out=tmp_path / "site" / "suite-status-current.json",
        prefer_passing=False,
    )

    assert latest_passing["build_id"] == "pass-001"
    assert latest_passing["source_selection"] == "latest_passing"
    assert current["build_id"] == "current-001"
    assert current["latest_source"] == "latest-verdict.json"
    assert current["source_selection"] == "current"
    assert current["release_candidate_ok"] is False


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


def test_workflow_summary_export_generates_public_safe_ms3_files(tmp_path):
    build_id = "ms3-live-test"
    evidence = tmp_path / "evidence"
    _ms3_proof_set(evidence, build_id)

    result = release.export_workflow_summary(
        build_id=build_id,
        evidence_root=evidence,
        matrix=_ms3_matrix(tmp_path / "matrix.json"),
        store_capabilities=_ms3_store(tmp_path / "store.json"),
        out=tmp_path / "site" / "workflow-evidence" / build_id,
    )
    output_root = tmp_path / "site" / "workflow-evidence" / build_id
    summary = json.loads((output_root / "workflow-matrix-summary.json").read_text(encoding="utf-8"))
    audio = json.loads((output_root / "workflows" / "video-generated-audio.json").read_text(encoding="utf-8"))
    exported_text = "\n".join(path.read_text(encoding="utf-8") for path in output_root.rglob("*") if path.is_file())

    assert result["ok"] is True
    assert summary["schema"] == release.WORKFLOW_MATRIX_SUMMARY_SCHEMA
    assert summary["workflow_count"] == 7
    assert summary["passed"] == 7
    assert summary["raw_evidence_exported"] is False
    assert summary["media_files_exported"] is False
    assert {item["workflow_id"] for item in summary["workflows"]} == set(release.EXPECTED_MS3_PRERELEASE_WORKFLOWS)
    assert audio["audio_validation"]["audio_stream_present"] is True
    assert audio["audio_validation"]["non_silent_audio"] is True
    assert audio["audio_validation"]["duration_compatible"] is True
    assert audio["audio_validation"]["audio_duration_ms"] == 4000
    assert audio["audio_validation"]["video_duration_ms"] == 4020
    assert "masked-edit" in {item["workflow_id"] for item in summary["blocked_later_workflows"]}
    assert "C:" + "\\Users" not in exported_text
    assert "192" + ".168." not in exported_text
    assert "token" not in exported_text.lower()
    assert "secret" not in exported_text.lower()
    assert _test_raw_serial("S23") not in exported_text
    assert "artifact" + ".mp4" not in exported_text
    assert not any(path.suffix.lower() in {".png", ".mp4", ".webm", ".log", ".txt"} for path in output_root.rglob("*"))


def test_workflow_summary_export_rejects_public_unsafe_summary_fields(tmp_path):
    build_id = "ms3-live-test"
    evidence = tmp_path / "evidence"
    _ms3_proof_set(evidence, build_id)

    with pytest.raises(ValueError):
        release.export_workflow_summary(
            build_id=build_id,
            evidence_root=evidence,
            matrix=_ms3_matrix(tmp_path / "matrix.json", unsafe_display_name=True),
            store_capabilities=_ms3_store(tmp_path / "store.json"),
            out=tmp_path / "site" / "workflow-evidence" / build_id,
        )


def test_release_module_cli_exports_workflow_summary(tmp_path, capsys):
    build_id = "ms3-live-test"
    evidence = tmp_path / "evidence"
    _ms3_proof_set(evidence, build_id)

    code = release.main(
        [
            "export-workflow-summary",
            "--evidence-root",
            str(evidence),
            "--build-id",
            build_id,
            "--matrix",
            str(_ms3_matrix(tmp_path / "matrix.json")),
            "--store-capabilities",
            str(_ms3_store(tmp_path / "store.json")),
            "--out",
            str(tmp_path / "site" / "workflow-evidence" / build_id),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert (tmp_path / "site" / "workflow-evidence" / build_id / "workflow-matrix-summary.md").exists()


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
