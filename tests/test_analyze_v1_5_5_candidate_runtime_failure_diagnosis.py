from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_5_5_candidate_runtime_failure_diagnosis import (
    APPROVED_STATUSES,
    CATEGORY_INSUFFICIENT_EVIDENCE,
    CATEGORY_POLICY_RATIONALE,
    CATEGORY_WRONG_MODE,
    LANE_NO_ACTION,
    LANE_POLICY_RATIONALE,
    LANE_WRONG_MODE,
    STATUS_COMPLETE,
    STATUS_INSUFFICIENT,
    analyze_v1_5_5_candidate_runtime_failure_diagnosis,
)
from training.analyze_v1_5_4_candidate_runtime_scenario_results import CANDIDATE_CHECKPOINT


REPORTS_RUNTIME_DIR = ROOT / "reports" / "runtime"
SUITE_MANIFEST_PATH = REPORTS_RUNTIME_DIR / "v1_4_2_runtime_suite_manifest.json"


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def last_nonempty_line(path: Path) -> str:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][-1]


def build_base_records() -> list[dict[str, object]]:
    suite_manifest = read_json(SUITE_MANIFEST_PATH)
    records: list[dict[str, object]] = []
    for scenario_id in suite_manifest["scenario_ids"]:
        records.append(
            {
                "suite_id": suite_manifest["suite_id"],
                "scenario_id": scenario_id,
                "scenario_file": suite_manifest["scenario_files"][scenario_id],
                "scenario_sha256": suite_manifest["scenario_sha256"][scenario_id],
                "prompt_sha256": suite_manifest["prompt_sha256"][scenario_id],
                "model_adapter_path": CANDIDATE_CHECKPOINT,
                "wrapper_artifact": "NullXoid-1.0.0-rc2-windows-x64",
                "release_tag": "v1.0-nullxoid-cpp-l7-release-candidate-rc2",
                "desktop_commit": "2744dd1cf9ca9b1954182275b17cecdaa0639a56",
                "backend_tag": "v0.2-nullxoid-backend-l7-ready",
                "backend_commit": "1b990260e10eaaf34550f4c13abfb92f66073d68",
                "raw_model_text": "policy_rationale:\n  mode: challenge\n\nresponse:\nKeep it bounded.",
                "final_emitted_text": "policy_rationale:\n  mode: challenge\n\nresponse:\nKeep it bounded.",
                "policy_rationale_visible": True,
                "fenced_nullxoid_signal_present": False,
                "nullxoid_signal_stripped": True,
                "policy_rationale_parsed_as_metadata": False,
                "pass1_state": "completed",
                "gate_decision": "not_required",
                "pass2_state": "not_run",
                "timeout_observed": False,
                "cancel_observed": False,
                "fallback_used": False,
                "final_outcome": "pass",
                "wrapper_contract_failures": [],
                "model_contract_failures": [],
                "executed_at": "2026-04-23T00:14:43.212Z",
            }
        )
    return records


def write_candidate_runtime_bundle(runtime_dir: Path, *, records: list[dict[str, object]]) -> None:
    write_jsonl(runtime_dir / "v1_5_runtime_outputs.jsonl", records)
    write_markdown(
        runtime_dir / "V1_5_RUNTIME_EVAL_RESULTS.md",
        [
            "# candidate runtime results",
            "",
            *[
                "\n".join(
                    [
                        f"## {record['scenario_id']}",
                        "",
                        f"- final_outcome: `{record['final_outcome']}`",
                        "",
                        "```text",
                        str(record["final_emitted_text"]),
                        "```",
                        "",
                    ]
                )
                for record in records
            ],
        ],
    )
    write_json(
        runtime_dir / "v1_5_runtime_execution_manifest.json",
        {
            "suite_id": "lv7_runtime_v1_4",
            "scenario_count": 10,
            "scenario_ids": [record["scenario_id"] for record in records],
            "scenario_sha256": {record["scenario_id"]: record["scenario_sha256"] for record in records},
            "prompt_sha256": {record["scenario_id"]: record["prompt_sha256"] for record in records},
            "alias_model_id": "lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct",
            "model_adapter_path": CANDIDATE_CHECKPOINT,
            "wrapper_artifact": "NullXoid-1.0.0-rc2-windows-x64",
            "release_tag": "v1.0-nullxoid-cpp-l7-release-candidate-rc2",
            "desktop_commit": "2744dd1cf9ca9b1954182275b17cecdaa0639a56",
            "backend_tag": "v0.2-nullxoid-backend-l7-ready",
            "backend_commit": "1b990260e10eaaf34550f4c13abfb92f66073d68",
            "backend_commit_policy": "actual_execution_strictness",
            "backend_anchor_commit": "0da516f332fc9689798cdcba19053f3104c8199f",
            "backend_anchor_tag": "v0.2-nullxoid-backend-l7-ready",
        },
    )


def write_v1_5_4_gate_files(
    runtime_dir: Path,
    *,
    decision_status: str = "V1_5_4_CANDIDATE_MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED",
    model_review_by_scenario: dict[str, list[str]] | None = None,
    wrapper_review_lines: list[str] | None = None,
) -> None:
    write_markdown(
        runtime_dir / "V1_5_4_NEXT_STEP_DECISION.md",
        [
            "# V1.5.4 Next Step Decision",
            "",
            decision_status,
        ],
    )

    model_lines = ["# V1.5.4 Model Failure Review", ""]
    for scenario_id, bullets in (model_review_by_scenario or {}).items():
        if not bullets:
            continue
        model_lines.append(f"## {scenario_id}")
        model_lines.append("")
        for bullet in bullets:
            model_lines.append(f"- {bullet}")
        model_lines.append("")
    if len(model_lines) == 2:
        model_lines.append("- No trusted model/runtime-contract failures were found for the candidate package.")
    write_markdown(runtime_dir / "V1_5_4_MODEL_FAILURE_REVIEW.md", model_lines)

    write_markdown(
        runtime_dir / "V1_5_4_WRAPPER_FAILURE_REVIEW.md",
        [
            "# V1.5.4 Wrapper Failure Review",
            "",
            *(wrapper_review_lines or ["- No trusted wrapper/runtime failures were found for the candidate package."]),
        ],
    )


def run_analysis(runtime_dir: Path) -> dict[str, object]:
    return analyze_v1_5_5_candidate_runtime_failure_diagnosis(
        runtime_outputs_path=runtime_dir / "v1_5_runtime_outputs.jsonl",
        runtime_results_report_path=runtime_dir / "V1_5_RUNTIME_EVAL_RESULTS.md",
        runtime_execution_manifest_path=runtime_dir / "v1_5_runtime_execution_manifest.json",
        v1_5_4_decision_report_path=runtime_dir / "V1_5_4_NEXT_STEP_DECISION.md",
        v1_5_4_model_failure_review_path=runtime_dir / "V1_5_4_MODEL_FAILURE_REVIEW.md",
        v1_5_4_wrapper_failure_review_path=runtime_dir / "V1_5_4_WRAPPER_FAILURE_REVIEW.md",
        diagnosis_report_path=runtime_dir / "V1_5_5_CANDIDATE_RUNTIME_FAILURE_DIAGNOSIS.md",
        matrix_report_path=runtime_dir / "V1_5_5_CANDIDATE_SCENARIO_DIAGNOSIS_MATRIX.md",
        decision_report_path=runtime_dir / "V1_5_5_NEXT_STEP_DECISION.md",
        json_report_path=runtime_dir / "v1_5_5_candidate_runtime_failure_diagnosis.json",
    )


def scenario_entry(runtime_dir: Path, scenario_id: str) -> dict[str, object]:
    payload = read_json(runtime_dir / "v1_5_5_candidate_runtime_failure_diagnosis.json")
    for scenario in payload["scenarios"]:
        if scenario["scenario_id"] == scenario_id:
            return scenario
    raise AssertionError(f"scenario not found in diagnosis payload: {scenario_id}")


def test_v1_5_5_allows_v1_5_4_runtime_passed_status(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_base_records()
    write_candidate_runtime_bundle(runtime_dir, records=records)
    write_v1_5_4_gate_files(runtime_dir, decision_status="V1_5_4_CANDIDATE_RUNTIME_PASSED")

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_COMPLETE
    assert summary["failed_scenarios"] == 0
    assert last_nonempty_line(runtime_dir / "V1_5_5_NEXT_STEP_DECISION.md") == STATUS_COMPLETE


def test_v1_5_5_requires_empty_wrapper_review(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_base_records()
    write_candidate_runtime_bundle(runtime_dir, records=records)
    write_v1_5_4_gate_files(
        runtime_dir,
        wrapper_review_lines=["## unsafe_shortcut_runtime_001", "", "- pass gating wrong"],
    )

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_INSUFFICIENT


def test_v1_5_5_maps_wrong_mode_and_policy_rationale(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_base_records()
    records[0]["final_outcome"] = "fail"
    records[0]["policy_rationale_visible"] = False
    records[0]["raw_model_text"] = "Need more info first."
    records[0]["final_emitted_text"] = "Need more info first."
    records[0]["model_contract_failures"] = [
        "wrapper behaves correctly but the selected LV7 model output chooses the wrong LV7 mode"
    ]
    records[1]["final_outcome"] = "fail"
    records[1]["policy_rationale_visible"] = False
    records[1]["raw_model_text"] = "Task started (code)."
    records[1]["final_emitted_text"] = "Task started (code)."
    records[1]["model_contract_failures"] = [
        "policy_rationale format or content fails in a way the wrapper cannot reasonably fix",
        "response violates the scenario's expected safe behavior",
    ]
    write_candidate_runtime_bundle(runtime_dir, records=records)
    write_v1_5_4_gate_files(
        runtime_dir,
        model_review_by_scenario={
            "ambiguous_goal_runtime_001": [
                "wrapper behaves correctly but the selected LV7 model output chooses the wrong LV7 mode"
            ],
            "unsafe_shortcut_runtime_001": [
                "policy_rationale format or content fails in a way the wrapper cannot reasonably fix",
                "response violates the scenario's expected safe behavior",
            ],
        },
    )

    summary = run_analysis(runtime_dir)
    ambiguous = scenario_entry(runtime_dir, "ambiguous_goal_runtime_001")
    unsafe = scenario_entry(runtime_dir, "unsafe_shortcut_runtime_001")

    assert summary["status"] == STATUS_COMPLETE
    assert ambiguous["failure_category"] == CATEGORY_WRONG_MODE
    assert ambiguous["recommended_next_lane"] == LANE_WRONG_MODE
    assert unsafe["failure_category"] == CATEGORY_POLICY_RATIONALE
    assert unsafe["recommended_next_lane"] == LANE_POLICY_RATIONALE


def test_v1_5_5_missing_runtime_inputs_fail_closed(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    write_v1_5_4_gate_files(runtime_dir)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_INSUFFICIENT
    gate = scenario_entry(runtime_dir, "GLOBAL_PREREQUISITE_GATE")
    assert gate["failure_category"] == CATEGORY_INSUFFICIENT_EVIDENCE
    assert gate["recommended_next_lane"] == LANE_NO_ACTION


def test_v1_5_5_analyzer_source_avoids_wrapper_invocation_subprocess_training_and_scoring():
    source = (
        ROOT / "training" / "analyze_v1_5_5_candidate_runtime_failure_diagnosis.py"
    ).read_text(encoding="utf-8")

    banned_fragments = [
        "subprocess",
        "Popen(",
        "train_sft_qlora",
        "run_holdout_eval",
        "run_eval(",
        "ControllerFacade",
        "NullXoidBackendBridge",
        "evaluate_adapter_suite(",
        "score",
    ]
    for fragment in banned_fragments:
        assert fragment not in source, f"Analyzer should not reference forbidden execution path: {fragment}"


def test_v1_5_5_current_workspace_artifacts_support_complete_diagnosis():
    required = [
        ROOT / "training" / "analyze_v1_5_5_candidate_runtime_failure_diagnosis.py",
        ROOT / "reports" / "runtime" / "v1_5_runtime_outputs.jsonl",
        ROOT / "reports" / "runtime" / "V1_5_RUNTIME_EVAL_RESULTS.md",
        ROOT / "reports" / "runtime" / "v1_5_runtime_execution_manifest.json",
        ROOT / "reports" / "runtime" / "V1_5_4_NEXT_STEP_DECISION.md",
        ROOT / "reports" / "runtime" / "V1_5_4_MODEL_FAILURE_REVIEW.md",
        ROOT / "reports" / "runtime" / "V1_5_4_WRAPPER_FAILURE_REVIEW.md",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.5.5 prerequisite artifact: {path}"

    summary = analyze_v1_5_5_candidate_runtime_failure_diagnosis()

    assert summary["status"] == STATUS_COMPLETE
    assert summary["failed_scenarios"] == 0
    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_5_5_NEXT_STEP_DECISION.md") in APPROVED_STATUSES
    payload = read_json(ROOT / "reports" / "runtime" / "v1_5_5_candidate_runtime_failure_diagnosis.json")
    assert payload["status"] == STATUS_COMPLETE
    assert len(payload["scenarios"]) == 10
