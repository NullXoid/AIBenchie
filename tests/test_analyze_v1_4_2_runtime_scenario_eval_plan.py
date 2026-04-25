from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_4_2_runtime_scenario_eval_plan import (
    APPROVED_STATUSES,
    EXPECTED_SCENARIOS,
    STATUS_EVIDENCE_NOT_READY,
    STATUS_PLAN_READY,
    analyze_v1_4_2_runtime_scenario_eval_plan,
    model_adapter_path_is_accepted,
)


REPORTS_RUNTIME_DIR = ROOT / "reports" / "runtime"
RUNTIME_EVAL_DIR = ROOT / "evals" / "runtime" / "v1_4"
BLIND_HOLDOUT_DIR = ROOT / "evals" / "holdout" / "blind_v1_3"
BLIND_PROBE_DIR = ROOT / "evals" / "dpo_probes" / "blind_v1_3"
BLIND_PROBE_CONTRACTFIX_DIR = ROOT / "evals" / "dpo_probes" / "blind_v1_3_contractfix_v1_3_5"


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


def test_v1_4_2_analyzer_writes_ready_plan_schema_and_manifest_without_mutation(tmp_path):
    scoring_path = ROOT / "evals" / "scoring.py"
    run_eval_path = ROOT / "evals" / "run_eval.py"
    scoring_hash_before = sha256(scoring_path)
    run_eval_hash_before = sha256(run_eval_path)
    blind_holdout_hashes_before = suite_hashes(BLIND_HOLDOUT_DIR)
    blind_probe_hashes_before = suite_hashes(BLIND_PROBE_DIR)
    blind_probe_contractfix_hashes_before = suite_hashes(BLIND_PROBE_CONTRACTFIX_DIR)

    runtime_dir = tmp_path / "reports" / "runtime"
    summary = analyze_v1_4_2_runtime_scenario_eval_plan(
        plan_report_path=runtime_dir / "V1_4_2_RUNTIME_SCENARIO_EVAL_PLAN.md",
        schema_report_path=runtime_dir / "V1_4_2_RUNTIME_OUTPUT_SCHEMA.md",
        taxonomy_report_path=runtime_dir / "V1_4_2_MODEL_VS_WRAPPER_FAILURE_TAXONOMY.md",
        acceptance_report_path=runtime_dir / "V1_4_2_SCENARIO_ACCEPTANCE_CRITERIA.md",
        decision_report_path=runtime_dir / "V1_4_2_NEXT_STEP_DECISION.md",
        schema_json_path=runtime_dir / "v1_4_2_runtime_output_schema.json",
        suite_manifest_json_path=runtime_dir / "v1_4_2_runtime_suite_manifest.json",
    )

    assert summary["status"] == STATUS_PLAN_READY
    assert summary["accepted_checkpoint"] == "models/adapters/lv7_sft_smoke_v1_0_5/"
    assert summary["scenario_count"] == 10
    assert last_nonempty_line(runtime_dir / "V1_4_2_NEXT_STEP_DECISION.md") == STATUS_PLAN_READY

    suite_manifest = json.loads(
        (runtime_dir / "v1_4_2_runtime_suite_manifest.json").read_text(encoding="utf-8")
    )
    assert suite_manifest["suite_id"] == "lv7_runtime_v1_4"
    assert suite_manifest["scenario_count"] == 10
    assert suite_manifest["scenario_ids"] == [scenario_id for scenario_id, _, _ in EXPECTED_SCENARIOS]
    assert set(suite_manifest["scenario_files"]) == set(suite_manifest["scenario_ids"])
    assert set(suite_manifest["scenario_sha256"]) == set(suite_manifest["scenario_ids"])
    assert set(suite_manifest["prompt_sha256"]) == set(suite_manifest["scenario_ids"])

    schema_payload = json.loads(
        (runtime_dir / "v1_4_2_runtime_output_schema.json").read_text(encoding="utf-8")
    )
    assert schema_payload["model_identity"]["accepted_model_adapter_path"] == "models/adapters/lv7_sft_smoke_v1_0_5/"
    assert sorted(schema_payload["model_identity"]["invalid_model_adapter_paths"]) == sorted(
        [
            "models/adapters/lv7_sft_shared_contract_v1_3_6/",
            "models/adapters/lv7_sft_shared_contract_v1_3_6_2/",
        ]
    )
    for field in (
        "model_adapter_path",
        "wrapper_artifact",
        "backend_commit",
        "raw_model_text",
        "final_emitted_text",
        "policy_rationale_visible",
        "nullxoid_signal_stripped",
        "pass1_state",
        "final_outcome",
        "wrapper_contract_failures",
        "model_contract_failures",
    ):
        assert field in schema_payload["required_fields"]

    schema_report_text = (
        runtime_dir / "V1_4_2_RUNTIME_OUTPUT_SCHEMA.md"
    ).read_text(encoding="utf-8")
    taxonomy_text = (
        runtime_dir / "V1_4_2_MODEL_VS_WRAPPER_FAILURE_TAXONOMY.md"
    ).read_text(encoding="utf-8")
    plan_text = (
        runtime_dir / "V1_4_2_RUNTIME_SCENARIO_EVAL_PLAN.md"
    ).read_text(encoding="utf-8")

    assert "path comparison rule" in schema_report_text
    assert "LV7 v1.4.4 - Runtime Model Failure Diagnosis" in taxonomy_text
    assert "LV7 v1.4.3 - Runtime Scenario Results Ingestion" in plan_text

    assert sha256(scoring_path) == scoring_hash_before
    assert sha256(run_eval_path) == run_eval_hash_before
    assert suite_hashes(BLIND_HOLDOUT_DIR) == blind_holdout_hashes_before
    assert suite_hashes(BLIND_PROBE_DIR) == blind_probe_hashes_before
    assert suite_hashes(BLIND_PROBE_CONTRACTFIX_DIR) == blind_probe_contractfix_hashes_before


def test_v1_4_2_requires_v1_4_1_ready_status(tmp_path):
    fake_v1_4_1_decision = tmp_path / "reports" / "runtime" / "V1_4_1_NEXT_STEP_DECISION.md"
    fake_v1_4_1_decision.parent.mkdir(parents=True, exist_ok=True)
    fake_v1_4_1_decision.write_text("# decision\n\nRUNTIME_EVIDENCE_INCOMPLETE\n", encoding="utf-8")

    runtime_dir = tmp_path / "reports" / "runtime-v1_4_2"
    summary = analyze_v1_4_2_runtime_scenario_eval_plan(
        v1_4_1_decision_report_path=fake_v1_4_1_decision,
        plan_report_path=runtime_dir / "V1_4_2_RUNTIME_SCENARIO_EVAL_PLAN.md",
        schema_report_path=runtime_dir / "V1_4_2_RUNTIME_OUTPUT_SCHEMA.md",
        taxonomy_report_path=runtime_dir / "V1_4_2_MODEL_VS_WRAPPER_FAILURE_TAXONOMY.md",
        acceptance_report_path=runtime_dir / "V1_4_2_SCENARIO_ACCEPTANCE_CRITERIA.md",
        decision_report_path=runtime_dir / "V1_4_2_NEXT_STEP_DECISION.md",
        schema_json_path=runtime_dir / "v1_4_2_runtime_output_schema.json",
        suite_manifest_json_path=runtime_dir / "v1_4_2_runtime_suite_manifest.json",
    )

    assert summary["status"] == STATUS_EVIDENCE_NOT_READY
    assert last_nonempty_line(runtime_dir / "V1_4_2_NEXT_STEP_DECISION.md") == STATUS_EVIDENCE_NOT_READY


def test_v1_4_2_model_adapter_identity_is_path_normalized_and_rejects_evidence_only():
    assert model_adapter_path_is_accepted("models/adapters/lv7_sft_smoke_v1_0_5/")
    assert model_adapter_path_is_accepted(r"models\adapters\lv7_sft_smoke_v1_0_5\\")
    assert not model_adapter_path_is_accepted("models/adapters/lv7_sft_shared_contract_v1_3_6/")
    assert not model_adapter_path_is_accepted(r"models\adapters\lv7_sft_shared_contract_v1_3_6_2\\")


def test_v1_4_2_analyzer_source_avoids_wrapper_invocation_subprocess_and_training_entrypoints():
    source = (
        ROOT / "training" / "analyze_v1_4_2_runtime_scenario_eval_plan.py"
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


def test_v1_4_2_repo_artifacts_exist_and_capture_ready_plan():
    required = [
        ROOT / "training" / "analyze_v1_4_2_runtime_scenario_eval_plan.py",
        ROOT / "reports" / "runtime" / "V1_4_2_RUNTIME_SCENARIO_EVAL_PLAN.md",
        ROOT / "reports" / "runtime" / "V1_4_2_RUNTIME_OUTPUT_SCHEMA.md",
        ROOT / "reports" / "runtime" / "V1_4_2_MODEL_VS_WRAPPER_FAILURE_TAXONOMY.md",
        ROOT / "reports" / "runtime" / "V1_4_2_SCENARIO_ACCEPTANCE_CRITERIA.md",
        ROOT / "reports" / "runtime" / "V1_4_2_NEXT_STEP_DECISION.md",
        ROOT / "reports" / "runtime" / "v1_4_2_runtime_output_schema.json",
        ROOT / "reports" / "runtime" / "v1_4_2_runtime_suite_manifest.json",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.4.2 artifact: {path}"

    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_4_2_NEXT_STEP_DECISION.md") in APPROVED_STATUSES
    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_4_2_NEXT_STEP_DECISION.md") == STATUS_PLAN_READY
