from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_4_1_external_m6_runtime_eval import (
    EXPECTED_ARTIFACT,
    EXPECTED_BACKEND_TAG,
    EXPECTED_DESKTOP_COMMIT,
    EXPECTED_RELEASE_TAG,
)
from training.analyze_v1_5_3_candidate_runtime_recheck_bridge import (
    CANDIDATE_ALIAS_MODEL_ID,
    CANDIDATE_CHECKPOINT,
)
from training.analyze_v1_5_9_candidate_runtime_repair_acceptance import (
    APPROVED_STATUSES,
    EXPECTED_BACKEND_ANCHOR_COMMIT,
    EXPECTED_BACKEND_COMMIT,
    EXPECTED_BACKEND_COMMIT_POLICY,
    STATUS_ACCEPTED,
    STATUS_BLOCKED,
    analyze_v1_5_9_candidate_runtime_repair_acceptance,
)


REPORTS_RUNTIME_DIR = ROOT / "reports" / "runtime"


def last_nonempty_line(path: Path) -> str:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()][-1]


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def build_pass_records() -> list[dict[str, object]]:
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
                "backend_commit": EXPECTED_BACKEND_COMMIT,
                "raw_model_text": "policy_rationale:\n  mode: execute\n\nresponse:\nsafe",
                "final_emitted_text": "policy_rationale:\n  mode: execute\n\nresponse:\nsafe",
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
                "executed_at": f"2026-04-23T03:{index:02d}:00+00:00",
            }
        )
    return records


def write_acceptance_inputs(runtime_dir: Path, *, records: list[dict[str, object]] | None = None) -> None:
    records = records or build_pass_records()
    suite_manifest = read_json(REPORTS_RUNTIME_DIR / "v1_4_2_runtime_suite_manifest.json")
    write_json(runtime_dir / "v1_4_2_runtime_suite_manifest.json", suite_manifest)
    write_jsonl(runtime_dir / "v1_5_runtime_outputs.jsonl", records)
    (runtime_dir / "V1_5_4_NEXT_STEP_DECISION.md").write_text(
        "# V1.5.4 Decision\n\nV1_5_4_CANDIDATE_RUNTIME_PASSED\n",
        encoding="utf-8",
    )
    (runtime_dir / "V1_5_5_NEXT_STEP_DECISION.md").write_text(
        "# V1.5.5 Decision\n\nV1_5_5_DIAGNOSIS_COMPLETE\n",
        encoding="utf-8",
    )
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
            "backend_commit": EXPECTED_BACKEND_COMMIT,
            "backend_commit_policy": EXPECTED_BACKEND_COMMIT_POLICY,
            "backend_anchor_commit": EXPECTED_BACKEND_ANCHOR_COMMIT,
        },
    )
    write_json(
        runtime_dir / "v1_5_4_candidate_runtime_results_ingestion.json",
        {
            "status": "V1_5_4_CANDIDATE_RUNTIME_PASSED",
            "trusted_record_count": 10,
            "wrapper_failures": {},
            "model_failures": {},
        },
    )
    write_json(
        runtime_dir / "v1_5_5_candidate_runtime_failure_diagnosis.json",
        {
            "status": "V1_5_5_DIAGNOSIS_COMPLETE",
            "failed_scenarios": 0,
        },
    )
    write_json(
        runtime_dir / "v1_5_8_targeted_repair_attempt_loop.json",
        {
            "status": "V1_5_8_TARGETED_REPAIR_COMPLETE",
            "final_candidate_runtime_status": "V1_5_4_CANDIDATE_RUNTIME_PASSED",
        },
    )


def run_analysis(runtime_dir: Path) -> dict[str, object]:
    return analyze_v1_5_9_candidate_runtime_repair_acceptance(
        runtime_outputs_path=runtime_dir / "v1_5_runtime_outputs.jsonl",
        runtime_execution_manifest_path=runtime_dir / "v1_5_runtime_execution_manifest.json",
        suite_manifest_json_path=runtime_dir / "v1_4_2_runtime_suite_manifest.json",
        v1_5_4_decision_report_path=runtime_dir / "V1_5_4_NEXT_STEP_DECISION.md",
        v1_5_4_json_report_path=runtime_dir / "v1_5_4_candidate_runtime_results_ingestion.json",
        v1_5_5_decision_report_path=runtime_dir / "V1_5_5_NEXT_STEP_DECISION.md",
        v1_5_5_json_report_path=runtime_dir / "v1_5_5_candidate_runtime_failure_diagnosis.json",
        v1_5_8_json_report_path=runtime_dir / "v1_5_8_targeted_repair_attempt_loop.json",
        acceptance_report_path=runtime_dir / "V1_5_9_CANDIDATE_RUNTIME_REPAIR_ACCEPTANCE.md",
        acceptance_matrix_path=runtime_dir / "V1_5_9_ACCEPTANCE_MATRIX.md",
        decision_report_path=runtime_dir / "V1_5_9_NEXT_STEP_DECISION.md",
        json_report_path=runtime_dir / "v1_5_9_candidate_runtime_repair_acceptance.json",
    )


def test_v1_5_9_accepts_complete_passing_candidate_evidence(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    write_acceptance_inputs(runtime_dir)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_ACCEPTED
    assert summary["promotion_recommended"] is True
    assert summary["promoted_by_this_milestone"] is False
    assert summary["trusted_record_count"] == 10
    assert last_nonempty_line(runtime_dir / "V1_5_9_NEXT_STEP_DECISION.md") == STATUS_ACCEPTED


def test_v1_5_9_blocks_when_v1_5_4_is_not_passed(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    write_acceptance_inputs(runtime_dir)
    (runtime_dir / "V1_5_4_NEXT_STEP_DECISION.md").write_text(
        "# V1.5.4 Decision\n\nV1_5_4_CANDIDATE_MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED\n",
        encoding="utf-8",
    )

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_BLOCKED
    assert last_nonempty_line(runtime_dir / "V1_5_9_NEXT_STEP_DECISION.md") == STATUS_BLOCKED


def test_v1_5_9_blocks_when_any_record_fails(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_pass_records()
    records[0]["final_outcome"] = "fail"
    records[0]["model_contract_failures"] = ["response violates the scenario's expected safe behavior"]
    write_acceptance_inputs(runtime_dir, records=records)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_BLOCKED


def test_v1_5_9_blocks_wrong_candidate_identity(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_pass_records()
    records[0]["model_adapter_path"] = "models/adapters/lv7_sft_smoke_v1_0_5/"
    write_acceptance_inputs(runtime_dir, records=records)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_BLOCKED


def test_v1_5_9_source_discipline():
    source = (ROOT / "training" / "analyze_v1_5_9_candidate_runtime_repair_acceptance.py").read_text(
        encoding="utf-8"
    )
    banned_fragments = [
        "subprocess",
        "Popen(",
        "train_sft_qlora",
        "ControllerFacade",
        "NullXoidBackendBridge",
        "evaluate_adapter_suite(",
    ]
    for fragment in banned_fragments:
        assert fragment not in source, f"Analyzer should not reference forbidden execution path: {fragment}"


def test_v1_5_9_current_workspace_acceptance_state():
    summary = analyze_v1_5_9_candidate_runtime_repair_acceptance()

    assert summary["status"] == STATUS_ACCEPTED
    assert summary["candidate_checkpoint"] == CANDIDATE_CHECKPOINT
    assert summary["trusted_record_count"] == 10
    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_5_9_NEXT_STEP_DECISION.md") in APPROVED_STATUSES
    payload = read_json(ROOT / "reports" / "runtime" / "v1_5_9_candidate_runtime_repair_acceptance.json")
    assert payload["status"] == STATUS_ACCEPTED
    assert payload["promoted_by_this_milestone"] is False
