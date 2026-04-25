from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_5_2_narrow_runtime_sft_training_run import (
    DEFAULT_JSON_REPORT,
    NEXT_EXECUTABLE_MILESTONE,
    STATUS_INSUFFICIENT,
    STATUS_READY,
    analyze_v1_5_2_narrow_runtime_sft_training_run,
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


def test_v1_5_2_requires_v1_5_1_ready(tmp_path):
    v1_5_1_decision = tmp_path / "V1_5_1_NEXT_STEP_DECISION.md"
    write_markdown(v1_5_1_decision, ["# v1.5.1", "", "V1_5_1_IMPLEMENTATION_INSUFFICIENT"])

    summary = analyze_v1_5_2_narrow_runtime_sft_training_run(
        v1_5_1_decision_report_path=v1_5_1_decision,
        training_config_path=ROOT / "training" / "qlora_runtime_repair_v1_5_1.yaml",
        training_run_config_path=ROOT / "reports" / "training" / "v1_5_1_sft_run_config.json",
        training_log_path=ROOT / "reports" / "training" / "v1_5_1_sft_train_log.jsonl",
        current_exact_results_path=ROOT / "reports" / "training" / "v1_5_1_exact_eval_results.jsonl",
        baseline_exact_results_path=ROOT / "reports" / "training" / "v1_0_5_exact_eval_results.jsonl",
        training_analysis_report_path=ROOT / "reports" / "training" / "V1_5_1_NARROW_RUNTIME_SFT_ANALYSIS.md",
        freeze_markdown_path=ROOT / "reports" / "training" / "V1_0_5_FREEZE.md",
        freeze_manifest_path=ROOT / "reports" / "training" / "v1_0_5_artifact_manifest.json",
        v1_4_3_analyzer_path=ROOT / "training" / "analyze_v1_4_3_runtime_scenario_results.py",
        candidate_adapter_path=ROOT / "models" / "adapters" / "lv7_sft_runtime_repair_v1_5_1",
        implementation_report_path=tmp_path / "implementation.md",
        matrix_report_path=tmp_path / "matrix.md",
        decision_report_path=tmp_path / "decision.md",
        json_report_path=tmp_path / "report.json",
    )

    assert summary["status"] == STATUS_INSUFFICIENT
    assert last_nonempty_line(tmp_path / "decision.md") == STATUS_INSUFFICIENT


def test_v1_5_2_requires_training_artifacts(tmp_path):
    v1_5_1_decision = tmp_path / "V1_5_1_NEXT_STEP_DECISION.md"
    write_markdown(v1_5_1_decision, ["# v1.5.1", "", "V1_5_1_IMPLEMENTATION_READY"])

    summary = analyze_v1_5_2_narrow_runtime_sft_training_run(
        v1_5_1_decision_report_path=v1_5_1_decision,
        training_config_path=ROOT / "training" / "qlora_runtime_repair_v1_5_1.yaml",
        training_run_config_path=tmp_path / "missing_run_config.json",
        training_log_path=ROOT / "reports" / "training" / "v1_5_1_sft_train_log.jsonl",
        current_exact_results_path=ROOT / "reports" / "training" / "v1_5_1_exact_eval_results.jsonl",
        baseline_exact_results_path=ROOT / "reports" / "training" / "v1_0_5_exact_eval_results.jsonl",
        training_analysis_report_path=ROOT / "reports" / "training" / "V1_5_1_NARROW_RUNTIME_SFT_ANALYSIS.md",
        freeze_markdown_path=ROOT / "reports" / "training" / "V1_0_5_FREEZE.md",
        freeze_manifest_path=ROOT / "reports" / "training" / "v1_0_5_artifact_manifest.json",
        v1_4_3_analyzer_path=ROOT / "training" / "analyze_v1_4_3_runtime_scenario_results.py",
        candidate_adapter_path=ROOT / "models" / "adapters" / "lv7_sft_runtime_repair_v1_5_1",
        implementation_report_path=tmp_path / "implementation.md",
        matrix_report_path=tmp_path / "matrix.md",
        decision_report_path=tmp_path / "decision.md",
        json_report_path=tmp_path / "report.json",
    )

    assert summary["status"] == STATUS_INSUFFICIENT
    assert last_nonempty_line(tmp_path / "decision.md") == STATUS_INSUFFICIENT


def test_v1_5_2_analyzer_source_avoids_wrapper_execution_training_and_dpo_invocation():
    source = (
        ROOT / "training" / "analyze_v1_5_2_narrow_runtime_sft_training_run.py"
    ).read_text(encoding="utf-8")

    banned_fragments = [
        "subprocess",
        "Popen(",
        "ControllerFacade",
        "NullXoidBackendBridge",
        "run_dpo_smoke",
        "train_sft_qlora.py --mode",
    ]
    for fragment in banned_fragments:
        assert fragment not in source, f"Analyzer should not reference forbidden execution path: {fragment}"


def test_v1_5_2_current_workspace_artifacts_support_ready_candidate_bridge():
    required = [
        ROOT / "training" / "analyze_v1_5_2_narrow_runtime_sft_training_run.py",
        ROOT / "reports" / "runtime" / "V1_5_1_NEXT_STEP_DECISION.md",
        ROOT / "training" / "qlora_runtime_repair_v1_5_1.yaml",
        ROOT / "reports" / "training" / "v1_5_1_sft_run_config.json",
        ROOT / "reports" / "training" / "v1_5_1_sft_train_log.jsonl",
        ROOT / "reports" / "training" / "v1_5_1_exact_eval_results.jsonl",
        ROOT / "reports" / "training" / "v1_0_5_exact_eval_results.jsonl",
        ROOT / "reports" / "training" / "V1_0_5_FREEZE.md",
        ROOT / "reports" / "training" / "v1_0_5_artifact_manifest.json",
        ROOT / "models" / "adapters" / "lv7_sft_runtime_repair_v1_5_1" / "adapter_model.safetensors",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.5.2 prerequisite artifact: {path}"

    summary = analyze_v1_5_2_narrow_runtime_sft_training_run()

    assert summary["status"] == STATUS_READY
    assert summary["current_exact_eval_passed"] == 11
    assert summary["baseline_exact_eval_passed"] == 11
    assert summary["exact_eval_total"] == 11
    assert summary["regression_ids"] == []
    assert summary["candidate_runtime_bridge_required"] is True
    assert summary["next_executable_milestone"] == NEXT_EXECUTABLE_MILESTONE
    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_5_2_NEXT_STEP_DECISION.md") == STATUS_READY

    payload = json.loads(DEFAULT_JSON_REPORT.read_text(encoding="utf-8"))
    assert payload["status"] == STATUS_READY
    assert payload["candidate_checkpoint"] == "models/adapters/lv7_sft_runtime_repair_v1_5_1/"
    assert payload["current_exact_eval_passed"] == 11
    assert payload["baseline_exact_eval_passed"] == 11
    assert payload["exact_eval_total"] == 11
    assert payload["regression_ids"] == []
    assert payload["candidate_runtime_bridge_required"] is True
    assert payload["next_executable_milestone"] == NEXT_EXECUTABLE_MILESTONE
    assert len(payload["scenarios"]) == 11

    scenario_ids = [row["scenario_id"] for row in payload["scenarios"]]
    assert len(set(scenario_ids)) == 11
    for row in payload["scenarios"]:
        assert row["current_pass"] is True
        assert row["regression_guard"] is True
