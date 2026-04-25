from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_5_10_accepted_runtime_repair_promotion import (
    APPROVED_STATUSES,
    STATUS_BLOCKED,
    STATUS_COMPLETE,
    analyze_v1_5_10_accepted_runtime_repair_promotion,
)
from training.analyze_v1_5_3_candidate_runtime_recheck_bridge import (
    CANDIDATE_ALIAS_MODEL_ID,
    CANDIDATE_CHECKPOINT,
)
from training.lv7_accepted_runtime_identity import (
    ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
    ACCEPTED_RUNTIME_BASE_MODEL,
    ACCEPTED_RUNTIME_CHECKPOINT,
    PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT,
    PROMOTION_STATUS,
)


REPORTS_RUNTIME_DIR = ROOT / "reports" / "runtime"


def last_nonempty_line(path: Path) -> str:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()][-1]


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_promotion_inputs(runtime_dir: Path) -> None:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "V1_5_4_NEXT_STEP_DECISION.md").write_text(
        "# V1.5.4 Decision\n\nV1_5_4_CANDIDATE_RUNTIME_PASSED\n",
        encoding="utf-8",
    )
    (runtime_dir / "V1_5_5_NEXT_STEP_DECISION.md").write_text(
        "# V1.5.5 Decision\n\nV1_5_5_DIAGNOSIS_COMPLETE\n",
        encoding="utf-8",
    )
    (runtime_dir / "V1_5_9_NEXT_STEP_DECISION.md").write_text(
        "# V1.5.9 Decision\n\nV1_5_9_CANDIDATE_ACCEPTED_FOR_PROMOTION\n",
        encoding="utf-8",
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
    write_json(
        runtime_dir / "v1_5_9_candidate_runtime_repair_acceptance.json",
        {
            "status": "V1_5_9_CANDIDATE_ACCEPTED_FOR_PROMOTION",
            "accepted_checkpoint": PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT,
            "candidate_checkpoint": CANDIDATE_CHECKPOINT,
            "candidate_alias_model_id": CANDIDATE_ALIAS_MODEL_ID,
            "trusted_record_count": 10,
            "pass_count": 10,
            "fail_count": 0,
            "promotion_recommended": True,
            "promoted_by_this_milestone": False,
        },
    )
    write_json(
        runtime_dir / "v1_5_runtime_execution_manifest.json",
        {
            "model_adapter_path": CANDIDATE_CHECKPOINT,
            "alias_model_id": CANDIDATE_ALIAS_MODEL_ID,
            "backend_commit": "1b990260e10eaaf34550f4c13abfb92f66073d68",
            "backend_commit_policy": "actual_execution_strictness",
            "backend_anchor_commit": "0da516f332fc9689798cdcba19053f3104c8199f",
        },
    )


def run_analysis(runtime_dir: Path) -> dict[str, object]:
    return analyze_v1_5_10_accepted_runtime_repair_promotion(
        v1_5_4_decision_report_path=runtime_dir / "V1_5_4_NEXT_STEP_DECISION.md",
        v1_5_4_json_report_path=runtime_dir / "v1_5_4_candidate_runtime_results_ingestion.json",
        v1_5_5_decision_report_path=runtime_dir / "V1_5_5_NEXT_STEP_DECISION.md",
        v1_5_5_json_report_path=runtime_dir / "v1_5_5_candidate_runtime_failure_diagnosis.json",
        v1_5_8_json_report_path=runtime_dir / "v1_5_8_targeted_repair_attempt_loop.json",
        v1_5_9_decision_report_path=runtime_dir / "V1_5_9_NEXT_STEP_DECISION.md",
        v1_5_9_json_report_path=runtime_dir / "v1_5_9_candidate_runtime_repair_acceptance.json",
        runtime_execution_manifest_path=runtime_dir / "v1_5_runtime_execution_manifest.json",
        promotion_report_path=runtime_dir / "V1_5_10_ACCEPTED_RUNTIME_REPAIR_PROMOTION.md",
        promotion_matrix_path=runtime_dir / "V1_5_10_PROMOTION_MATRIX.md",
        decision_report_path=runtime_dir / "V1_5_10_NEXT_STEP_DECISION.md",
        json_report_path=runtime_dir / "v1_5_10_accepted_runtime_repair_promotion.json",
    )


def test_v1_5_10_promotes_accepted_runtime_identity(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    write_promotion_inputs(runtime_dir)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_COMPLETE
    assert summary["promotion_complete"] is True
    assert summary["previous_accepted_checkpoint"] == PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT
    assert summary["accepted_checkpoint"] == CANDIDATE_CHECKPOINT
    assert summary["accepted_alias_model_id"] == CANDIDATE_ALIAS_MODEL_ID
    assert last_nonempty_line(runtime_dir / "V1_5_10_NEXT_STEP_DECISION.md") == STATUS_COMPLETE


def test_v1_5_10_blocks_when_v1_5_9_not_accepted(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    write_promotion_inputs(runtime_dir)
    (runtime_dir / "V1_5_9_NEXT_STEP_DECISION.md").write_text(
        "# V1.5.9 Decision\n\nV1_5_9_ACCEPTANCE_BLOCKED\n",
        encoding="utf-8",
    )

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_BLOCKED
    assert summary["promotion_complete"] is False


def test_v1_5_10_blocks_wrong_candidate_identity(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    write_promotion_inputs(runtime_dir)
    payload = read_json(runtime_dir / "v1_5_9_candidate_runtime_repair_acceptance.json")
    payload["candidate_checkpoint"] = PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT
    write_json(runtime_dir / "v1_5_9_candidate_runtime_repair_acceptance.json", payload)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_BLOCKED


def test_v1_5_10_current_identity_module_points_to_runtime_repair():
    assert ACCEPTED_RUNTIME_CHECKPOINT == CANDIDATE_CHECKPOINT
    assert ACCEPTED_RUNTIME_ALIAS_MODEL_ID == CANDIDATE_ALIAS_MODEL_ID
    assert ACCEPTED_RUNTIME_BASE_MODEL == "Qwen/Qwen2.5-1.5B-Instruct"
    assert PROMOTION_STATUS == STATUS_COMPLETE


def test_v1_5_10_source_discipline():
    source = (ROOT / "training" / "analyze_v1_5_10_accepted_runtime_repair_promotion.py").read_text(
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


def test_v1_5_10_current_workspace_promotion_state():
    summary = analyze_v1_5_10_accepted_runtime_repair_promotion()

    assert summary["status"] == STATUS_COMPLETE
    assert summary["accepted_checkpoint"] == CANDIDATE_CHECKPOINT
    assert summary["accepted_alias_model_id"] == CANDIDATE_ALIAS_MODEL_ID
    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_5_10_NEXT_STEP_DECISION.md") in APPROVED_STATUSES
    payload = read_json(ROOT / "reports" / "runtime" / "v1_5_10_accepted_runtime_repair_promotion.json")
    assert payload["status"] == STATUS_COMPLETE
    assert payload["promotion_complete"] is True
