from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_5_1_narrow_runtime_sft_repair_implementation import (
    DEFAULT_JSON_REPORT,
    NEXT_EXECUTABLE_MILESTONE,
    RETENTION_ROLE,
    REPAIR_ROLE,
    STATUS_INSUFFICIENT,
    STATUS_READY,
    analyze_v1_5_1_narrow_runtime_sft_repair_implementation,
)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def last_nonempty_line(path: Path) -> str:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][-1]


def test_v1_5_1_requires_v1_5_0_ready(tmp_path):
    v1_4_3_decision = tmp_path / "V1_4_3_NEXT_STEP_DECISION.md"
    v1_4_3_wrapper = tmp_path / "V1_4_3_WRAPPER_FAILURE_REVIEW.md"
    v1_5_0_decision = tmp_path / "V1_5_0_NEXT_STEP_DECISION.md"
    v1_5_0_json = tmp_path / "v1_5_0_narrow_runtime_model_repair_plan.json"

    write_markdown(v1_4_3_decision, ["# v1.4.3", "", "MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED"])
    write_markdown(v1_4_3_wrapper, ["# wrapper", "", "- No trusted wrapper/runtime failures were found."])
    write_markdown(v1_5_0_decision, ["# v1.5.0", "", "V1_5_0_REPAIR_PLAN_INSUFFICIENT"])
    write_json(v1_5_0_json, {"status": "V1_5_0_REPAIR_PLAN_INSUFFICIENT"})

    summary = analyze_v1_5_1_narrow_runtime_sft_repair_implementation(
        v1_4_3_decision_report_path=v1_4_3_decision,
        v1_4_3_wrapper_failure_review_path=v1_4_3_wrapper,
        v1_5_0_decision_report_path=v1_5_0_decision,
        v1_5_0_json_report_path=v1_5_0_json,
        runtime_outputs_path=ROOT / "reports" / "runtime" / "v1_4_runtime_outputs.jsonl",
        runtime_results_report_path=ROOT / "reports" / "runtime" / "V1_4_RUNTIME_EVAL_RESULTS.md",
        runtime_execution_manifest_path=ROOT / "reports" / "runtime" / "v1_4_runtime_execution_manifest.json",
        runtime_scenarios_dir=ROOT / "evals" / "runtime" / "v1_4",
        dataset_path=ROOT / "data" / "pilot_v1_9" / "sft_messages.jsonl",
        prepared_dataset_path=ROOT / "data" / "pilot_v1_9" / "sft_train_ready.jsonl",
        repair_config_path=ROOT / "training" / "qlora_runtime_repair_v1_5_1.yaml",
        implementation_report_path=tmp_path / "implementation.md",
        matrix_report_path=tmp_path / "matrix.md",
        decision_report_path=tmp_path / "decision.md",
        json_report_path=tmp_path / "report.json",
    )

    assert summary["status"] == STATUS_INSUFFICIENT
    assert last_nonempty_line(tmp_path / "decision.md") == STATUS_INSUFFICIENT


def test_v1_5_1_requires_empty_wrapper_failure_review(tmp_path):
    v1_4_3_decision = tmp_path / "V1_4_3_NEXT_STEP_DECISION.md"
    v1_4_3_wrapper = tmp_path / "V1_4_3_WRAPPER_FAILURE_REVIEW.md"
    v1_5_0_decision = tmp_path / "V1_5_0_NEXT_STEP_DECISION.md"
    v1_5_0_json = tmp_path / "v1_5_0_narrow_runtime_model_repair_plan.json"

    write_markdown(v1_4_3_decision, ["# v1.4.3", "", "MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED"])
    write_markdown(v1_4_3_wrapper, ["# wrapper", "", "- wrapper/runtime fault still open"])
    write_markdown(v1_5_0_decision, ["# v1.5.0", "", "V1_5_0_REPAIR_PLAN_READY"])
    write_json(v1_5_0_json, json.loads((ROOT / "reports" / "runtime" / "v1_5_0_narrow_runtime_model_repair_plan.json").read_text(encoding="utf-8")))

    summary = analyze_v1_5_1_narrow_runtime_sft_repair_implementation(
        v1_4_3_decision_report_path=v1_4_3_decision,
        v1_4_3_wrapper_failure_review_path=v1_4_3_wrapper,
        v1_5_0_decision_report_path=v1_5_0_decision,
        v1_5_0_json_report_path=v1_5_0_json,
        runtime_outputs_path=ROOT / "reports" / "runtime" / "v1_4_runtime_outputs.jsonl",
        runtime_results_report_path=ROOT / "reports" / "runtime" / "V1_4_RUNTIME_EVAL_RESULTS.md",
        runtime_execution_manifest_path=ROOT / "reports" / "runtime" / "v1_4_runtime_execution_manifest.json",
        runtime_scenarios_dir=ROOT / "evals" / "runtime" / "v1_4",
        dataset_path=ROOT / "data" / "pilot_v1_9" / "sft_messages.jsonl",
        prepared_dataset_path=ROOT / "data" / "pilot_v1_9" / "sft_train_ready.jsonl",
        repair_config_path=ROOT / "training" / "qlora_runtime_repair_v1_5_1.yaml",
        implementation_report_path=tmp_path / "implementation.md",
        matrix_report_path=tmp_path / "matrix.md",
        decision_report_path=tmp_path / "decision.md",
        json_report_path=tmp_path / "report.json",
    )

    assert summary["status"] == STATUS_INSUFFICIENT
    assert last_nonempty_line(tmp_path / "decision.md") == STATUS_INSUFFICIENT


def test_v1_5_1_analyzer_source_avoids_wrapper_execution_training_and_dpo_invocation():
    source = (
        ROOT / "training" / "analyze_v1_5_1_narrow_runtime_sft_repair_implementation.py"
    ).read_text(encoding="utf-8")

    banned_fragments = [
        "subprocess",
        "Popen(",
        "ControllerFacade",
        "NullXoidBackendBridge",
        "run_dpo_smoke",
        "train_sft_qlora(",
    ]
    for fragment in banned_fragments:
        assert fragment not in source, f"Analyzer should not reference forbidden execution path: {fragment}"


def test_v1_5_1_current_workspace_artifacts_support_ready_implementation():
    required = [
        ROOT / "training" / "analyze_v1_5_1_narrow_runtime_sft_repair_implementation.py",
        ROOT / "training" / "qlora_runtime_repair_v1_5_1.yaml",
        ROOT / "reports" / "runtime" / "V1_4_3_NEXT_STEP_DECISION.md",
        ROOT / "reports" / "runtime" / "V1_4_3_WRAPPER_FAILURE_REVIEW.md",
        ROOT / "reports" / "runtime" / "V1_5_0_NEXT_STEP_DECISION.md",
        ROOT / "reports" / "runtime" / "v1_5_0_narrow_runtime_model_repair_plan.json",
        ROOT / "data" / "pilot_v1_9" / "sft_messages.jsonl",
        ROOT / "data" / "pilot_v1_9" / "sft_train_ready.jsonl",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.5.1 prerequisite artifact: {path}"

    summary = analyze_v1_5_1_narrow_runtime_sft_repair_implementation()

    assert summary["status"] == STATUS_READY
    assert summary["repair_record_count"] == 10
    assert summary["dataset_record_count"] == summary["prepared_dataset_record_count"]
    assert summary["next_executable_milestone"] == NEXT_EXECUTABLE_MILESTONE
    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_5_1_NEXT_STEP_DECISION.md") == STATUS_READY

    payload = json.loads(DEFAULT_JSON_REPORT.read_text(encoding="utf-8"))
    assert payload["status"] == STATUS_READY
    assert payload["repair_record_count"] == 10
    assert payload["next_executable_milestone"] == NEXT_EXECUTABLE_MILESTONE
    assert len(payload["scenarios"]) == 10

    role_counts = {REPAIR_ROLE: 0, RETENTION_ROLE: 0}
    scenario_ids = []
    for row in payload["scenarios"]:
        scenario_ids.append(row["scenario_id"])
        role_counts[row["repair_role"]] = role_counts.get(row["repair_role"], 0) + 1
        assert row["prompt_match"] is True
        assert row["missing_required_terms_after_repair"] == []
        assert row["forbidden_terms_present"] == []
    assert len(set(scenario_ids)) == 10
    assert role_counts[REPAIR_ROLE] == 9
    assert role_counts[RETENTION_ROLE] == 1

    config_text = (ROOT / "training" / "qlora_runtime_repair_v1_5_1.yaml").read_text(encoding="utf-8")
    assert "models/adapters/lv7_sft_runtime_repair_v1_5_1/" in config_text
    assert "models/adapters/lv7_sft_smoke_v1_0_5/" not in config_text
