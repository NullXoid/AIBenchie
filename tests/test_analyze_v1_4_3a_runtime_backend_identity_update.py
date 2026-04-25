from __future__ import annotations

import json
from pathlib import Path

from training.analyze_v1_4_3a_runtime_backend_identity_update import (
    APPROVED_STATUSES,
    EXPECTED_ACCEPTED_BASE_MODEL,
    EXPECTED_ALIAS_MODEL_ID,
    EXPECTED_M21_STATUS,
    EXPECTED_M22_STATUS,
    STATUS_POLICY_INCOMPLETE,
    STATUS_POLICY_INVALID,
    STATUS_POLICY_READY,
    analyze_v1_4_3a_runtime_backend_identity_update,
)


def last_nonempty_line(path: Path) -> str:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][-1]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_lv7_prerequisite_reports(runtime_dir: Path) -> tuple[Path, Path, Path]:
    v1_4_1 = runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md"
    v1_4_2 = runtime_dir / "V1_4_2_NEXT_STEP_DECISION.md"
    v1_4_3 = runtime_dir / "V1_4_3_NEXT_STEP_DECISION.md"
    write_text(v1_4_1, "# v1.4.1\n\nRUNTIME_EVAL_READY\n")
    write_text(v1_4_2, "# v1.4.2\n\nRUNTIME_SCENARIO_EVAL_PLAN_READY\n")
    write_text(v1_4_3, "# v1.4.3\n\nRUNTIME_RESULTS_INCOMPLETE\n")
    return v1_4_1, v1_4_2, v1_4_3


def build_m21_manifest() -> dict[str, object]:
    return {
        "milestone": "M21",
        "status": EXPECTED_M21_STATUS,
        "alias_model_id": EXPECTED_ALIAS_MODEL_ID,
        "accepted_adapter_path": "models/adapters/lv7_sft_smoke_v1_0_5/",
        "accepted_base_model": EXPECTED_ACCEPTED_BASE_MODEL,
        "wrapper_artifact": "NullXoid-1.0.0-rc2-windows-x64",
        "release_tag": "v1.0-nullxoid-cpp-l7-release-candidate-rc2",
        "desktop_commit": "2744dd1cf9ca9b1954182275b17cecdaa0639a56",
        "backend_tag": "v0.2-nullxoid-backend-l7-ready",
        "backend_commit": "1b990260e10eaaf34550f4c13abfb92f66073d68",
        "backend_anchor_commit": "0da516f332fc9689798cdcba19053f3104c8199f",
        "models_endpoint_exposes_alias": True,
        "chat_stream_accepts_alias": True,
        "request_shape_changed": False,
        "lv7_runtime_outputs_written": False,
    }


def build_m22_decision() -> dict[str, object]:
    return {
        "milestone": "M22",
        "status": EXPECTED_M22_STATUS,
        "wrapper_artifact": "NullXoid-1.0.0-rc2-windows-x64",
        "release_tag": "v1.0-nullxoid-cpp-l7-release-candidate-rc2",
        "desktop_commit": "2744dd1cf9ca9b1954182275b17cecdaa0639a56",
        "backend_tag": "v0.2-nullxoid-backend-l7-ready",
        "actual_execution_backend_commit": "1b990260e10eaaf34550f4c13abfb92f66073d68",
        "frozen_anchor_backend_commit": "0da516f332fc9689798cdcba19053f3104c8199f",
        "accepted_adapter_path": "models/adapters/lv7_sft_smoke_v1_0_5/",
        "accepted_base_model": EXPECTED_ACCEPTED_BASE_MODEL,
        "alias_model_id": EXPECTED_ALIAS_MODEL_ID,
        "current_lv7_v143_requires_anchor_commit": True,
        "runtime_outputs_allowed_now": False,
        "selected_policy": {
            "name": "actual_execution_strictness",
        },
    }


def test_v1_4_3a_missing_external_evidence_is_incomplete(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    v1_4_1, v1_4_2, v1_4_3 = write_lv7_prerequisite_reports(runtime_dir)

    summary = analyze_v1_4_3a_runtime_backend_identity_update(
        v1_4_1_decision_report_path=v1_4_1,
        v1_4_2_decision_report_path=v1_4_2,
        v1_4_3_decision_report_path=v1_4_3,
        m21_manifest_json_path=runtime_dir / "missing_m21.json",
        m21_decision_report_path=runtime_dir / "missing_m21.md",
        m22_decision_json_path=runtime_dir / "missing_m22.json",
        m22_decision_report_path=runtime_dir / "missing_m22.md",
        trust_update_report_path=runtime_dir / "V1_4_3A_BACKEND_IDENTITY_TRUST_UPDATE.md",
        decision_report_path=runtime_dir / "V1_4_3A_NEXT_STEP_DECISION.md",
        backend_identity_policy_json_path=runtime_dir / "v1_4_3a_backend_identity_policy.json",
    )

    assert summary["status"] == STATUS_POLICY_INCOMPLETE
    assert last_nonempty_line(runtime_dir / "V1_4_3A_NEXT_STEP_DECISION.md") == STATUS_POLICY_INCOMPLETE


def test_v1_4_3a_inconsistent_external_evidence_is_invalid(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    sibling_dir = tmp_path / "sibling"
    v1_4_1, v1_4_2, v1_4_3 = write_lv7_prerequisite_reports(runtime_dir)

    m21_manifest_json = sibling_dir / "m21.json"
    m21_decision_report = sibling_dir / "M21_NEXT_STEP_DECISION.md"
    m22_decision_json = sibling_dir / "m22.json"
    m22_decision_report = sibling_dir / "M22_NEXT_STEP_DECISION.md"

    m21_manifest = build_m21_manifest()
    m21_manifest["backend_commit"] = "deadbeef"
    write_json(m21_manifest_json, m21_manifest)
    write_text(m21_decision_report, f"# M21\n\n{EXPECTED_M21_STATUS}\n")
    write_json(m22_decision_json, build_m22_decision())
    write_text(m22_decision_report, f"# M22\n\n{EXPECTED_M22_STATUS}\n")

    summary = analyze_v1_4_3a_runtime_backend_identity_update(
        v1_4_1_decision_report_path=v1_4_1,
        v1_4_2_decision_report_path=v1_4_2,
        v1_4_3_decision_report_path=v1_4_3,
        m21_manifest_json_path=m21_manifest_json,
        m21_decision_report_path=m21_decision_report,
        m22_decision_json_path=m22_decision_json,
        m22_decision_report_path=m22_decision_report,
        trust_update_report_path=runtime_dir / "V1_4_3A_BACKEND_IDENTITY_TRUST_UPDATE.md",
        decision_report_path=runtime_dir / "V1_4_3A_NEXT_STEP_DECISION.md",
        backend_identity_policy_json_path=runtime_dir / "v1_4_3a_backend_identity_policy.json",
    )

    assert summary["status"] == STATUS_POLICY_INVALID
    assert last_nonempty_line(runtime_dir / "V1_4_3A_NEXT_STEP_DECISION.md") == STATUS_POLICY_INVALID


def test_v1_4_3a_valid_external_evidence_writes_local_policy(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    sibling_dir = tmp_path / "sibling"
    v1_4_1, v1_4_2, v1_4_3 = write_lv7_prerequisite_reports(runtime_dir)

    m21_manifest_json = sibling_dir / "m21.json"
    m21_decision_report = sibling_dir / "M21_NEXT_STEP_DECISION.md"
    m22_decision_json = sibling_dir / "m22.json"
    m22_decision_report = sibling_dir / "M22_NEXT_STEP_DECISION.md"

    write_json(m21_manifest_json, build_m21_manifest())
    write_text(m21_decision_report, f"# M21\n\n{EXPECTED_M21_STATUS}\n")
    write_json(m22_decision_json, build_m22_decision())
    write_text(m22_decision_report, f"# M22\n\n{EXPECTED_M22_STATUS}\n")

    policy_json = runtime_dir / "v1_4_3a_backend_identity_policy.json"
    summary = analyze_v1_4_3a_runtime_backend_identity_update(
        v1_4_1_decision_report_path=v1_4_1,
        v1_4_2_decision_report_path=v1_4_2,
        v1_4_3_decision_report_path=v1_4_3,
        m21_manifest_json_path=m21_manifest_json,
        m21_decision_report_path=m21_decision_report,
        m22_decision_json_path=m22_decision_json,
        m22_decision_report_path=m22_decision_report,
        trust_update_report_path=runtime_dir / "V1_4_3A_BACKEND_IDENTITY_TRUST_UPDATE.md",
        decision_report_path=runtime_dir / "V1_4_3A_NEXT_STEP_DECISION.md",
        backend_identity_policy_json_path=policy_json,
    )

    payload = json.loads(policy_json.read_text(encoding="utf-8"))
    assert summary["status"] == STATUS_POLICY_READY
    assert payload["status"] == STATUS_POLICY_READY
    assert payload["selected_policy"] == "actual_execution_strictness"
    assert payload["actual_execution_backend_commit"] == "1b990260e10eaaf34550f4c13abfb92f66073d68"
    assert payload["frozen_anchor_backend_commit"] == "0da516f332fc9689798cdcba19053f3104c8199f"
    assert last_nonempty_line(runtime_dir / "V1_4_3A_NEXT_STEP_DECISION.md") == STATUS_POLICY_READY


def test_v1_4_3a_analyzer_source_avoids_wrapper_invocation_subprocess_and_training_entrypoints():
    source = (
        Path(__file__).resolve().parents[1]
        / "training"
        / "analyze_v1_4_3a_runtime_backend_identity_update.py"
    ).read_text(encoding="utf-8")

    banned_fragments = [
        "subprocess",
        "Popen(",
        "train_sft_qlora",
        "run_holdout_eval",
        "evals.run_eval",
        "python training",
    ]
    for fragment in banned_fragments:
        assert fragment not in source, f"Analyzer should not reference forbidden execution path: {fragment}"


def test_v1_4_3a_repo_artifacts_exist_and_current_workspace_is_ready():
    required = [
        Path(__file__).resolve().parents[1] / "training" / "analyze_v1_4_3a_runtime_backend_identity_update.py",
        Path(__file__).resolve().parents[1] / "reports" / "runtime" / "V1_4_3A_BACKEND_IDENTITY_TRUST_UPDATE.md",
        Path(__file__).resolve().parents[1] / "reports" / "runtime" / "V1_4_3A_NEXT_STEP_DECISION.md",
        Path(__file__).resolve().parents[1] / "reports" / "runtime" / "v1_4_3a_backend_identity_policy.json",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.4.3a artifact: {path}"

    assert last_nonempty_line(Path(__file__).resolve().parents[1] / "reports" / "runtime" / "V1_4_3A_NEXT_STEP_DECISION.md") in APPROVED_STATUSES
    assert last_nonempty_line(Path(__file__).resolve().parents[1] / "reports" / "runtime" / "V1_4_3A_NEXT_STEP_DECISION.md") == STATUS_POLICY_READY
