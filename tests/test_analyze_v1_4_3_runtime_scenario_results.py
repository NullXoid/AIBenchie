from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_4_3_runtime_scenario_results import (
    APPROVED_STATUSES,
    EXPECTED_ARTIFACT,
    EXPECTED_BACKEND_COMMIT,
    EXPECTED_BACKEND_TAG,
    EXPECTED_DESKTOP_COMMIT,
    EXPECTED_RELEASE_TAG,
    STATUS_INCOMPLETE,
    STATUS_INVALID,
    STATUS_MODEL_REPAIR,
    STATUS_PASSED,
    STATUS_WRAPPER_REPAIR,
    analyze_v1_4_3_runtime_scenario_results,
)


REPORTS_RUNTIME_DIR = ROOT / "reports" / "runtime"
BLIND_HOLDOUT_DIR = ROOT / "evals" / "holdout" / "blind_v1_3"
BLIND_PROBE_DIR = ROOT / "evals" / "dpo_probes" / "blind_v1_3"
BLIND_PROBE_CONTRACTFIX_DIR = ROOT / "evals" / "dpo_probes" / "blind_v1_3_contractfix_v1_3_5"
ACTUAL_BACKEND_COMMIT = "1b990260e10eaaf34550f4c13abfb92f66073d68"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def last_nonempty_line(path: Path) -> str:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][-1]


def suite_hashes(directory: Path) -> dict[str, str]:
    return {path.name: sha256(path) for path in sorted(directory.glob("*.yaml"))}


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


def iso_at(offset_minutes: int) -> str:
    base = datetime(2026, 4, 21, 21, 0, tzinfo=timezone.utc)
    return base.replace(minute=base.minute + offset_minutes).isoformat()


def build_base_records(*, backend_commit: str = EXPECTED_BACKEND_COMMIT) -> list[dict[str, object]]:
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
                "model_adapter_path": "models/adapters/lv7_sft_smoke_v1_0_5/",
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
                "executed_at": datetime(2026, 4, 21, 21, index, tzinfo=timezone.utc).isoformat(),
            }
        )
    return records


def write_runtime_results_bundle(
    runtime_dir: Path,
    *,
    records: list[dict[str, object]],
    with_execution_manifest: bool = False,
    execution_manifest_overrides: dict[str, object] | None = None,
) -> None:
    write_jsonl(runtime_dir / "v1_4_runtime_outputs.jsonl", records)
    (runtime_dir / "V1_4_RUNTIME_EVAL_RESULTS.md").write_text("# runtime results\n", encoding="utf-8")
    if with_execution_manifest:
        manifest_payload: dict[str, object] = {
            "suite_id": "lv7_runtime_v1_4",
            "scenario_count": 10,
            "scenario_ids": [record["scenario_id"] for record in records],
            "scenario_sha256": {record["scenario_id"]: record["scenario_sha256"] for record in records},
            "prompt_sha256": {record["scenario_id"]: record["prompt_sha256"] for record in records},
            "model_adapter_path": "models/adapters/lv7_sft_smoke_v1_0_5/",
            "wrapper_artifact": EXPECTED_ARTIFACT,
            "release_tag": EXPECTED_RELEASE_TAG,
            "desktop_commit": EXPECTED_DESKTOP_COMMIT,
            "backend_tag": EXPECTED_BACKEND_TAG,
            "backend_commit": records[0]["backend_commit"],
            "execution_started_at": datetime(2026, 4, 21, 20, 55, tzinfo=timezone.utc).isoformat(),
            "execution_finished_at": datetime(2026, 4, 21, 21, 15, tzinfo=timezone.utc).isoformat(),
        }
        if execution_manifest_overrides:
            manifest_payload.update(execution_manifest_overrides)
        write_json(runtime_dir / "v1_4_runtime_execution_manifest.json", manifest_payload)


def write_backend_identity_policy(
    runtime_dir: Path,
    *,
    actual_backend_commit: str = ACTUAL_BACKEND_COMMIT,
) -> Path:
    policy_path = runtime_dir / "v1_4_3a_backend_identity_policy.json"
    write_json(
        policy_path,
        {
            "milestone": "LV7 v1.4.3a",
            "status": "RUNTIME_BACKEND_IDENTITY_POLICY_READY",
            "selected_policy": "actual_execution_strictness",
            "alias_model_id": "lv7_sft_smoke_v1_0_5:qwen2.5-1.5b-instruct",
            "accepted_adapter_path": "models/adapters/lv7_sft_smoke_v1_0_5/",
            "accepted_base_model": "Qwen/Qwen2.5-1.5B-Instruct",
            "wrapper_artifact": EXPECTED_ARTIFACT,
            "release_tag": EXPECTED_RELEASE_TAG,
            "desktop_commit": EXPECTED_DESKTOP_COMMIT,
            "backend_tag": EXPECTED_BACKEND_TAG,
            "actual_execution_backend_commit": actual_backend_commit,
            "frozen_anchor_backend_commit": EXPECTED_BACKEND_COMMIT,
            "requires_execution_manifest": True,
            "execution_manifest_requirements": {
                "backend_commit_policy": "actual_execution_strictness",
                "backend_anchor_commit": EXPECTED_BACKEND_COMMIT,
            },
        },
    )
    return policy_path


def run_analysis(
    runtime_dir: Path,
    *,
    backend_identity_policy_path: Path | None = None,
) -> dict[str, object]:
    return analyze_v1_4_3_runtime_scenario_results(
        runtime_outputs_path=runtime_dir / "v1_4_runtime_outputs.jsonl",
        runtime_results_report_path=runtime_dir / "V1_4_RUNTIME_EVAL_RESULTS.md",
        runtime_execution_manifest_path=runtime_dir / "v1_4_runtime_execution_manifest.json",
        backend_identity_policy_path=(
            backend_identity_policy_path
            if backend_identity_policy_path is not None
            else runtime_dir / "v1_4_3a_backend_identity_policy.json"
        ),
        ingestion_review_report_path=runtime_dir / "V1_4_3_RUNTIME_RESULTS_INGESTION_REVIEW.md",
        scenario_result_matrix_report_path=runtime_dir / "V1_4_3_SCENARIO_RESULT_MATRIX.md",
        wrapper_failure_review_report_path=runtime_dir / "V1_4_3_WRAPPER_FAILURE_REVIEW.md",
        model_failure_review_report_path=runtime_dir / "V1_4_3_MODEL_FAILURE_REVIEW.md",
        decision_report_path=runtime_dir / "V1_4_3_NEXT_STEP_DECISION.md",
    )


def test_v1_4_3_missing_runtime_outputs_is_incomplete_without_mutation(tmp_path):
    scoring_path = ROOT / "evals" / "scoring.py"
    run_eval_path = ROOT / "evals" / "run_eval.py"
    scoring_hash_before = sha256(scoring_path)
    run_eval_hash_before = sha256(run_eval_path)
    blind_holdout_hashes_before = suite_hashes(BLIND_HOLDOUT_DIR)
    blind_probe_hashes_before = suite_hashes(BLIND_PROBE_DIR)
    blind_probe_contractfix_hashes_before = suite_hashes(BLIND_PROBE_CONTRACTFIX_DIR)

    runtime_dir = tmp_path / "reports" / "runtime"
    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_INCOMPLETE
    assert last_nonempty_line(runtime_dir / "V1_4_3_NEXT_STEP_DECISION.md") == STATUS_INCOMPLETE
    assert sha256(scoring_path) == scoring_hash_before
    assert sha256(run_eval_path) == run_eval_hash_before
    assert suite_hashes(BLIND_HOLDOUT_DIR) == blind_holdout_hashes_before
    assert suite_hashes(BLIND_PROBE_DIR) == blind_probe_hashes_before
    assert suite_hashes(BLIND_PROBE_CONTRACTFIX_DIR) == blind_probe_contractfix_hashes_before


def test_v1_4_3_malformed_jsonl_is_invalid(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "v1_4_runtime_outputs.jsonl").write_text("{not-json\n", encoding="utf-8")
    (runtime_dir / "V1_4_RUNTIME_EVAL_RESULTS.md").write_text("# runtime results\n", encoding="utf-8")

    summary = run_analysis(runtime_dir)
    assert summary["status"] == STATUS_INVALID
    assert last_nonempty_line(runtime_dir / "V1_4_3_NEXT_STEP_DECISION.md") == STATUS_INVALID


def test_v1_4_3_wrong_field_types_are_invalid(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_base_records()
    records[0]["policy_rationale_visible"] = "true"
    write_runtime_results_bundle(runtime_dir, records=records)

    summary = run_analysis(runtime_dir)
    assert summary["status"] == STATUS_INVALID


def test_v1_4_3_missing_scenario_is_incomplete(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_base_records()[:-1]
    write_runtime_results_bundle(runtime_dir, records=records)

    summary = run_analysis(runtime_dir)
    assert summary["status"] == STATUS_INCOMPLETE


def test_v1_4_3_duplicate_and_unknown_scenarios_are_invalid(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_base_records()
    records.append(dict(records[0]))
    write_runtime_results_bundle(runtime_dir, records=records)

    duplicate_summary = run_analysis(runtime_dir)
    assert duplicate_summary["status"] == STATUS_INVALID

    runtime_dir2 = tmp_path / "reports" / "runtime2"
    records = build_base_records()
    records[0]["scenario_id"] = "unknown_runtime_999"
    write_runtime_results_bundle(runtime_dir2, records=records)

    unknown_summary = run_analysis(runtime_dir2)
    assert unknown_summary["status"] == STATUS_INVALID


def test_v1_4_3_hash_and_identity_mismatches_are_invalid(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_base_records()
    records[0]["scenario_sha256"] = "bad-hash"
    write_runtime_results_bundle(runtime_dir, records=records)
    assert run_analysis(runtime_dir)["status"] == STATUS_INVALID

    runtime_dir2 = tmp_path / "reports" / "runtime2"
    records = build_base_records()
    records[0]["model_adapter_path"] = r"models\adapters\lv7_sft_shared_contract_v1_3_6\\"
    write_runtime_results_bundle(runtime_dir2, records=records)
    assert run_analysis(runtime_dir2)["status"] == STATUS_INVALID

    runtime_dir3 = tmp_path / "reports" / "runtime3"
    records = build_base_records()
    records[0]["wrapper_artifact"] = "WrongArtifact"
    write_runtime_results_bundle(runtime_dir3, records=records)
    assert run_analysis(runtime_dir3)["status"] == STATUS_INVALID

    runtime_dir4 = tmp_path / "reports" / "runtime4"
    records = build_base_records()
    records[0]["backend_commit"] = "deadbeef"
    write_runtime_results_bundle(runtime_dir4, records=records)
    assert run_analysis(runtime_dir4)["status"] == STATUS_INVALID


def test_v1_4_3_execution_manifest_contradiction_is_invalid(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_base_records()
    write_runtime_results_bundle(
        runtime_dir,
        records=records,
        with_execution_manifest=True,
        execution_manifest_overrides={"desktop_commit": "deadbeef"},
    )

    summary = run_analysis(runtime_dir)
    assert summary["status"] == STATUS_INVALID


def test_v1_4_3_actual_backend_policy_requires_execution_manifest(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_base_records(backend_commit=ACTUAL_BACKEND_COMMIT)
    write_runtime_results_bundle(runtime_dir, records=records)
    policy_path = write_backend_identity_policy(runtime_dir)

    summary = run_analysis(runtime_dir, backend_identity_policy_path=policy_path)
    assert summary["status"] == STATUS_INVALID


def test_v1_4_3_actual_backend_policy_accepts_actual_commit_with_anchor_sidecar(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_base_records(backend_commit=ACTUAL_BACKEND_COMMIT)
    write_runtime_results_bundle(
        runtime_dir,
        records=records,
        with_execution_manifest=True,
        execution_manifest_overrides={
            "backend_commit": ACTUAL_BACKEND_COMMIT,
            "backend_commit_policy": "actual_execution_strictness",
            "backend_anchor_commit": EXPECTED_BACKEND_COMMIT,
        },
    )
    policy_path = write_backend_identity_policy(runtime_dir)

    summary = run_analysis(runtime_dir, backend_identity_policy_path=policy_path)
    assert summary["status"] == STATUS_PASSED


def test_v1_4_3_actual_backend_policy_rejects_wrong_anchor_sidecar(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_base_records(backend_commit=ACTUAL_BACKEND_COMMIT)
    write_runtime_results_bundle(
        runtime_dir,
        records=records,
        with_execution_manifest=True,
        execution_manifest_overrides={
            "backend_commit": ACTUAL_BACKEND_COMMIT,
            "backend_commit_policy": "actual_execution_strictness",
            "backend_anchor_commit": "deadbeef",
        },
    )
    policy_path = write_backend_identity_policy(runtime_dir)

    summary = run_analysis(runtime_dir, backend_identity_policy_path=policy_path)
    assert summary["status"] == STATUS_INVALID


def test_v1_4_3_wrapper_and_model_classification_priority(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_base_records()
    records[0]["final_outcome"] = "fail"
    records[0]["wrapper_contract_failures"] = ["pass gating wrong"]
    write_runtime_results_bundle(runtime_dir, records=records)
    assert run_analysis(runtime_dir)["status"] == STATUS_WRAPPER_REPAIR

    runtime_dir2 = tmp_path / "reports" / "runtime2"
    records = build_base_records()
    records[0]["final_outcome"] = "fail"
    records[0]["wrapper_contract_failures"] = ["pass gating wrong"]
    records[0]["model_contract_failures"] = [
        "wrapper behaves correctly but accepted v1.0.5 output chooses the wrong LV7 mode"
    ]
    write_runtime_results_bundle(runtime_dir2, records=records)
    assert run_analysis(runtime_dir2)["status"] == STATUS_WRAPPER_REPAIR

    runtime_dir3 = tmp_path / "reports" / "runtime3"
    records = build_base_records()
    records[0]["final_outcome"] = "fail"
    records[0]["model_contract_failures"] = [
        "wrapper behaves correctly but accepted v1.0.5 output chooses the wrong LV7 mode"
    ]
    write_runtime_results_bundle(runtime_dir3, records=records)
    assert run_analysis(runtime_dir3)["status"] == STATUS_MODEL_REPAIR


def test_v1_4_3_all_clean_passing_records_yield_passed(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    records = build_base_records()
    write_runtime_results_bundle(runtime_dir, records=records, with_execution_manifest=True)

    summary = run_analysis(runtime_dir)
    assert summary["status"] == STATUS_PASSED
    assert last_nonempty_line(runtime_dir / "V1_4_3_NEXT_STEP_DECISION.md") == STATUS_PASSED


def test_v1_4_3_analyzer_source_avoids_wrapper_invocation_subprocess_and_training_entrypoints():
    source = (
        ROOT / "training" / "analyze_v1_4_3_runtime_scenario_results.py"
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


def test_v1_4_3_repo_artifacts_exist_and_current_workspace_captures_model_runtime_result():
    required = [
        ROOT / "training" / "analyze_v1_4_3_runtime_scenario_results.py",
        ROOT / "reports" / "runtime" / "V1_4_3_RUNTIME_RESULTS_INGESTION_REVIEW.md",
        ROOT / "reports" / "runtime" / "V1_4_3_SCENARIO_RESULT_MATRIX.md",
        ROOT / "reports" / "runtime" / "V1_4_3_WRAPPER_FAILURE_REVIEW.md",
        ROOT / "reports" / "runtime" / "V1_4_3_MODEL_FAILURE_REVIEW.md",
        ROOT / "reports" / "runtime" / "V1_4_3_NEXT_STEP_DECISION.md",
        ROOT / "reports" / "runtime" / "v1_4_runtime_outputs.jsonl",
        ROOT / "reports" / "runtime" / "V1_4_RUNTIME_EVAL_RESULTS.md",
        ROOT / "reports" / "runtime" / "v1_4_runtime_execution_manifest.json",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.4.3 artifact: {path}"

    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_4_3_NEXT_STEP_DECISION.md") in APPROVED_STATUSES
    assert (
        last_nonempty_line(ROOT / "reports" / "runtime" / "V1_4_3_NEXT_STEP_DECISION.md")
        == STATUS_MODEL_REPAIR
    )
