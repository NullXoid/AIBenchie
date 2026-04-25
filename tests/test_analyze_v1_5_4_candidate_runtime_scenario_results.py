from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_5_4_candidate_runtime_scenario_results import (
    APPROVED_STATUSES,
    CANDIDATE_ALIAS_MODEL_ID,
    CANDIDATE_CHECKPOINT,
    STATUS_INCOMPLETE,
    STATUS_INVALID,
    STATUS_MODEL_REPAIR,
    STATUS_PASSED,
    STATUS_WRAPPER_REPAIR,
    analyze_v1_5_4_candidate_runtime_scenario_results,
)
from training.analyze_v1_4_1_external_m6_runtime_eval import (
    EXPECTED_ARTIFACT,
    EXPECTED_BACKEND_COMMIT,
    EXPECTED_BACKEND_TAG,
    EXPECTED_DESKTOP_COMMIT,
    EXPECTED_RELEASE_TAG,
)


REPORTS_RUNTIME_DIR = ROOT / "reports" / "runtime"
ACTUAL_BACKEND_COMMIT = "1b990260e10eaaf34550f4c13abfb92f66073d68"


def last_nonempty_line(path: Path) -> str:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][-1]


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


def build_candidate_records(*, backend_commit: str = ACTUAL_BACKEND_COMMIT) -> list[dict[str, object]]:
    suite_manifest = read_json(REPORTS_RUNTIME_DIR / "v1_4_2_runtime_suite_manifest.json")
    records: list[dict[str, object]] = []
    for index, scenario_id in enumerate(suite_manifest["scenario_ids"]):
        records.append(
            {
                "suite_id": suite_manifest["suite_id"],
                "scenario_id": scenario_id,
                "scenario_file": suite_manifest["scenario_files"][scenario_id],
                "scenario_sha256": suite_manifest["scenario_sha256"][scenario_id],
                "prompt_sha256": suite_manifest["prompt_sha256"][scenario_id],
                "model_adapter_path": CANDIDATE_CHECKPOINT,
                "wrapper_artifact": EXPECTED_ARTIFACT,
                "release_tag": EXPECTED_RELEASE_TAG,
                "desktop_commit": EXPECTED_DESKTOP_COMMIT,
                "backend_tag": EXPECTED_BACKEND_TAG,
                "backend_commit": backend_commit,
                "raw_model_text": "policy_rationale: bounded runtime reasoning\nresponse: safe runtime answer",
                "final_emitted_text": "policy_rationale: bounded runtime reasoning\nresponse: safe runtime answer",
                "policy_rationale_visible": True,
                "fenced_nullxoid_signal_present": False,
                "nullxoid_signal_stripped": True,
                "policy_rationale_parsed_as_metadata": False,
                "pass1_state": "completed",
                "gate_decision": "approved",
                "pass2_state": "completed",
                "timeout_observed": False,
                "cancel_observed": False,
                "fallback_used": False,
                "final_outcome": "pass",
                "wrapper_contract_failures": [],
                "model_contract_failures": [],
                "executed_at": datetime(2026, 4, 22, 23, index, tzinfo=timezone.utc).isoformat(),
            }
        )
    return records


def write_candidate_runtime_bundle(runtime_dir: Path, *, records: list[dict[str, object]]) -> None:
    write_jsonl(runtime_dir / "v1_5_runtime_outputs.jsonl", records)
    (runtime_dir / "V1_5_RUNTIME_EVAL_RESULTS.md").write_text("# candidate runtime results\n", encoding="utf-8")
    write_json(
        runtime_dir / "v1_5_runtime_execution_manifest.json",
        {
            "suite_id": "lv7_runtime_v1_4",
            "scenario_count": 10,
            "scenario_ids": [record["scenario_id"] for record in records],
            "scenario_sha256": {record["scenario_id"]: record["scenario_sha256"] for record in records},
            "prompt_sha256": {record["scenario_id"]: record["prompt_sha256"] for record in records},
            "alias_model_id": CANDIDATE_ALIAS_MODEL_ID,
            "model_adapter_path": CANDIDATE_CHECKPOINT,
            "wrapper_artifact": EXPECTED_ARTIFACT,
            "release_tag": EXPECTED_RELEASE_TAG,
            "desktop_commit": EXPECTED_DESKTOP_COMMIT,
            "backend_tag": EXPECTED_BACKEND_TAG,
            "backend_commit": ACTUAL_BACKEND_COMMIT,
            "backend_commit_policy": "actual_execution_strictness",
            "backend_anchor_commit": EXPECTED_BACKEND_COMMIT,
            "backend_anchor_tag": EXPECTED_BACKEND_TAG,
            "execution_started_at": datetime(2026, 4, 22, 22, 55, tzinfo=timezone.utc).isoformat(),
            "execution_finished_at": datetime(2026, 4, 22, 23, 15, tzinfo=timezone.utc).isoformat(),
        },
    )


def run_analysis(
    runtime_dir: Path,
    *,
    v1_5_3_decision_report_path: Path | None = None,
) -> dict[str, object]:
    return analyze_v1_5_4_candidate_runtime_scenario_results(
        runtime_outputs_path=runtime_dir / "v1_5_runtime_outputs.jsonl",
        runtime_results_report_path=runtime_dir / "V1_5_RUNTIME_EVAL_RESULTS.md",
        runtime_execution_manifest_path=runtime_dir / "v1_5_runtime_execution_manifest.json",
        v1_5_3_decision_report_path=(
            v1_5_3_decision_report_path
            if v1_5_3_decision_report_path is not None
            else REPORTS_RUNTIME_DIR / "V1_5_3_NEXT_STEP_DECISION.md"
        ),
        ingestion_review_report_path=runtime_dir / "V1_5_4_RUNTIME_RESULTS_INGESTION_REVIEW.md",
        scenario_result_matrix_report_path=runtime_dir / "V1_5_4_SCENARIO_RESULT_MATRIX.md",
        wrapper_failure_review_report_path=runtime_dir / "V1_5_4_WRAPPER_FAILURE_REVIEW.md",
        model_failure_review_report_path=runtime_dir / "V1_5_4_MODEL_FAILURE_REVIEW.md",
        decision_report_path=runtime_dir / "V1_5_4_NEXT_STEP_DECISION.md",
        json_report_path=runtime_dir / "v1_5_4_candidate_runtime_results_ingestion.json",
    )


def test_v1_5_4_requires_v1_5_3_bridge_ready(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_candidate_records()
    write_candidate_runtime_bundle(runtime_dir, records=records)

    bad_decision = tmp_path / "reports" / "runtime" / "V1_5_3_NEXT_STEP_DECISION.md"
    bad_decision.parent.mkdir(parents=True, exist_ok=True)
    bad_decision.write_text("wrong\nNOT_READY\n", encoding="utf-8")

    summary = run_analysis(runtime_dir, v1_5_3_decision_report_path=bad_decision)

    assert summary["status"] == STATUS_INVALID
    assert last_nonempty_line(runtime_dir / "V1_5_4_NEXT_STEP_DECISION.md") == STATUS_INVALID


def test_v1_5_4_missing_candidate_runtime_outputs_is_incomplete(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_INCOMPLETE
    assert last_nonempty_line(runtime_dir / "V1_5_4_NEXT_STEP_DECISION.md") == STATUS_INCOMPLETE


def test_v1_5_4_wrong_candidate_adapter_identity_is_invalid(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_candidate_records()
    records[0]["model_adapter_path"] = "models/adapters/lv7_sft_smoke_v1_0_5/"
    write_candidate_runtime_bundle(runtime_dir, records=records)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_INVALID


def test_v1_5_4_candidate_model_failures_classify_as_model_repair(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_candidate_records()
    records[0]["final_outcome"] = "fail"
    records[0]["model_contract_failures"] = [
        "policy_rationale format or content fails in a way the wrapper cannot reasonably fix"
    ]
    write_candidate_runtime_bundle(runtime_dir, records=records)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_MODEL_REPAIR


def test_v1_5_4_candidate_wrapper_failures_take_priority(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_candidate_records()
    records[0]["final_outcome"] = "blocked"
    records[0]["wrapper_contract_failures"] = ["pass gating wrong"]
    write_candidate_runtime_bundle(runtime_dir, records=records)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_WRAPPER_REPAIR


def test_v1_5_4_clean_candidate_records_yield_passed(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_candidate_records()
    write_candidate_runtime_bundle(runtime_dir, records=records)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_PASSED
    assert last_nonempty_line(runtime_dir / "V1_5_4_NEXT_STEP_DECISION.md") == STATUS_PASSED


def test_v1_5_4_analyzer_source_avoids_wrapper_invocation_subprocess_and_training_entrypoints():
    source = (
        ROOT / "training" / "analyze_v1_5_4_candidate_runtime_scenario_results.py"
    ).read_text(encoding="utf-8")

    banned_fragments = [
        "subprocess",
        "Popen(",
        "train_sft_qlora",
        "run_holdout_eval",
        "evals.run_eval",
        "python training",
        "nullxoid_live_tests",
    ]
    for fragment in banned_fragments:
        assert fragment not in source, f"Analyzer should not reference forbidden execution path: {fragment}"


def test_v1_5_4_repo_artifacts_exist_and_current_workspace_captures_candidate_runtime_result():
    required = [
        ROOT / "training" / "analyze_v1_5_4_candidate_runtime_scenario_results.py",
        ROOT / "reports" / "runtime" / "v1_5_runtime_outputs.jsonl",
        ROOT / "reports" / "runtime" / "V1_5_RUNTIME_EVAL_RESULTS.md",
        ROOT / "reports" / "runtime" / "v1_5_runtime_execution_manifest.json",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.5.4 artifact input: {path}"

    summary = analyze_v1_5_4_candidate_runtime_scenario_results()

    assert summary["status"] in APPROVED_STATUSES
    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_5_4_NEXT_STEP_DECISION.md") in APPROVED_STATUSES

