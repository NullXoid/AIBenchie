from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from tests.conftest import ROOT
from training.analyze_v1_4_runtime_eval_readiness import (
    APPROVED_STATUSES,
    STATUS_WAITING,
    analyze_v1_4_runtime_eval_readiness,
)


REPORTS_TRAINING_DIR = ROOT / "reports" / "training"
REPORTS_RUNTIME_DIR = ROOT / "reports" / "runtime"
RUNTIME_EVAL_DIR = ROOT / "evals" / "runtime" / "v1_4"
SCENARIOS_DIR = ROOT / "evals" / "scenarios"
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


def protected_prompt_texts() -> set[str]:
    prompts: set[str] = set()
    for folder in [SCENARIOS_DIR, BLIND_HOLDOUT_DIR, BLIND_PROBE_DIR, BLIND_PROBE_CONTRACTFIX_DIR]:
        for yaml_path in sorted(folder.glob("*.yaml")):
            payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            prompts.add(payload["prompt"])
    return prompts


def read_runtime_prompts(directory: Path) -> dict[str, str]:
    prompts: dict[str, str] = {}
    for yaml_path in sorted(directory.glob("*.yaml")):
        payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        prompts[payload["scenario_id"]] = payload["prompt"]
    return prompts


def test_analyze_v1_4_runtime_eval_readiness_writes_waiting_package_without_mutation(tmp_path):
    scoring_path = ROOT / "evals" / "scoring.py"
    run_eval_path = ROOT / "evals" / "run_eval.py"
    scoring_hash_before = sha256(scoring_path)
    run_eval_hash_before = sha256(run_eval_path)
    blind_holdout_hashes_before = suite_hashes(BLIND_HOLDOUT_DIR)
    blind_probe_hashes_before = suite_hashes(BLIND_PROBE_DIR)
    blind_probe_contractfix_hashes_before = suite_hashes(BLIND_PROBE_CONTRACTFIX_DIR)

    frozen_paths = [
        REPORTS_TRAINING_DIR / "v1_0_5_exact_eval_outputs.jsonl",
        REPORTS_TRAINING_DIR / "v1_3_6_2_exact_eval_results.jsonl",
        REPORTS_TRAINING_DIR / "v1_3_6_2_holdout_eval_results.jsonl",
        REPORTS_TRAINING_DIR / "v1_3_6_2_blind_holdout_results.jsonl",
        REPORTS_TRAINING_DIR / "v1_3_6_2_corrected_blind_probe_results.jsonl",
        REPORTS_TRAINING_DIR / "DPO_READINESS_REVIEW_V1_3_5.md",
        REPORTS_TRAINING_DIR / "DPO_READINESS_REVIEW_V1_3_6_2.md",
    ]
    frozen_hashes_before = {path.name: sha256(path) for path in frozen_paths}

    temp_reports_runtime = tmp_path / "reports" / "runtime"
    temp_reports_training = tmp_path / "reports" / "training"
    temp_runtime_dir = tmp_path / "evals" / "runtime" / "v1_4"
    temp_runtime_outputs = temp_reports_runtime / "v1_4_runtime_outputs.jsonl"
    temp_runtime_results = temp_reports_runtime / "V1_4_RUNTIME_EVAL_RESULTS.md"

    summary = analyze_v1_4_runtime_eval_readiness(
        blocked_summary_report_path=temp_reports_training / "V1_3_6_2_SHARED_REPAIR_BLOCKED_SUMMARY.md",
        runtime_plan_report_path=temp_reports_runtime / "V1_4_RUNTIME_EVAL_PLAN.md",
        compatibility_checklist_report_path=temp_reports_runtime / "V1_4_M6_COMPATIBILITY_CHECKLIST.md",
        runtime_surface_discovery_report_path=temp_reports_runtime / "V1_4_RUNTIME_SURFACE_DISCOVERY.md",
        decision_report_path=temp_reports_runtime / "V1_4_NEXT_STEP_DECISION.md",
        runtime_scenarios_dir=temp_runtime_dir,
        runtime_outputs_path=temp_runtime_outputs,
        runtime_results_report_path=temp_runtime_results,
    )

    assert summary["status"] == STATUS_WAITING
    assert summary["accepted_checkpoint"] == "models/adapters/lv7_sft_smoke_v1_0_5/"
    assert summary["m6_entrypoint_present"] is False
    assert summary["m6_runnable"] is False
    assert summary["live_runtime_executed"] is False
    assert summary["runtime_outputs_created"] is False
    assert summary["runtime_results_created"] is False
    assert summary["scenario_count"] == 10

    blocked_summary_text = (
        temp_reports_training / "V1_3_6_2_SHARED_REPAIR_BLOCKED_SUMMARY.md"
    ).read_text(encoding="utf-8")
    plan_text = (temp_reports_runtime / "V1_4_RUNTIME_EVAL_PLAN.md").read_text(encoding="utf-8")
    checklist_text = (
        temp_reports_runtime / "V1_4_M6_COMPATIBILITY_CHECKLIST.md"
    ).read_text(encoding="utf-8")
    discovery_text = (
        temp_reports_runtime / "V1_4_RUNTIME_SURFACE_DISCOVERY.md"
    ).read_text(encoding="utf-8")
    decision_text = (temp_reports_runtime / "V1_4_NEXT_STEP_DECISION.md").read_text(
        encoding="utf-8"
    )

    assert "REGRESSION_BLOCKED" in blocked_summary_text
    assert "`27/33`" in blocked_summary_text
    assert "`24/33`" in blocked_summary_text
    assert "`9/14`" in blocked_summary_text
    assert "MODEL_REPAIR_PAUSED_PENDING_RUNTIME_EVIDENCE" in blocked_summary_text
    assert "`policy_rationale` is model output." in plan_text
    assert "`nullxoid_signal` is controller metadata." in plan_text
    assert "`policy_rationale` remains visible model output" in checklist_text
    assert "`nullxoid_signal` is the only controller-routing metadata" in checklist_text
    assert "report output only and is never counted as runtime evidence" in discovery_text
    assert "Runtime evaluation must wait on M6." in discovery_text
    assert decision_text.rstrip().endswith(STATUS_WAITING)

    assert temp_reports_runtime.exists()
    assert temp_runtime_dir.exists()
    assert len(list(temp_runtime_dir.glob("*.yaml"))) == 10
    assert not temp_runtime_outputs.exists()
    assert not temp_runtime_results.exists()

    assert sha256(scoring_path) == scoring_hash_before
    assert sha256(run_eval_path) == run_eval_hash_before
    assert suite_hashes(BLIND_HOLDOUT_DIR) == blind_holdout_hashes_before
    assert suite_hashes(BLIND_PROBE_DIR) == blind_probe_hashes_before
    assert suite_hashes(BLIND_PROBE_CONTRACTFIX_DIR) == blind_probe_contractfix_hashes_before
    assert {path.name: sha256(path) for path in frozen_paths} == frozen_hashes_before


def test_v1_4_analyzer_source_avoids_training_generation_and_replay_entrypoints():
    source = (
        ROOT / "training" / "analyze_v1_4_runtime_eval_readiness.py"
    ).read_text(encoding="utf-8")

    banned_fragments = [
        "train_sft_qlora",
        "run_holdout_eval",
        "from evals.run_eval import",
        "evaluate_adapter_suite(",
        "run_evaluation(",
        "collect_model_outputs",
        "subprocess",
    ]
    for fragment in banned_fragments:
        assert fragment not in source, f"Analyzer should not reference forbidden entrypoint: {fragment}"


def test_v1_4_repo_artifacts_exist_and_capture_historical_waiting_on_m6_state():
    required = [
        ROOT / "training" / "analyze_v1_4_runtime_eval_readiness.py",
        REPORTS_TRAINING_DIR / "V1_3_6_2_SHARED_REPAIR_BLOCKED_SUMMARY.md",
        REPORTS_RUNTIME_DIR / "V1_4_RUNTIME_EVAL_PLAN.md",
        REPORTS_RUNTIME_DIR / "V1_4_M6_COMPATIBILITY_CHECKLIST.md",
        REPORTS_RUNTIME_DIR / "V1_4_RUNTIME_SURFACE_DISCOVERY.md",
        REPORTS_RUNTIME_DIR / "V1_4_NEXT_STEP_DECISION.md",
        RUNTIME_EVAL_DIR,
    ]
    for path in required:
        assert path.exists(), f"Missing v1.4 runtime-readiness artifact: {path}"

    assert len(list(RUNTIME_EVAL_DIR.glob("*.yaml"))) == 10
    assert last_nonempty_line(REPORTS_RUNTIME_DIR / "V1_4_NEXT_STEP_DECISION.md") in APPROVED_STATUSES
    assert last_nonempty_line(REPORTS_RUNTIME_DIR / "V1_4_NEXT_STEP_DECISION.md") == STATUS_WAITING
    # v1.4 itself correctly ended waiting on M6. Later milestones may create
    # runtime output artifacts, so this historical readiness test should not
    # require those files to remain absent forever.


def test_v1_4_runtime_prompts_are_new_and_package_is_complete():
    prompts = read_runtime_prompts(RUNTIME_EVAL_DIR)
    assert set(prompts) == {
        "ambiguous_goal_runtime_001",
        "unsafe_shortcut_runtime_001",
        "shutdown_conflict_runtime_001",
        "audit_evasion_runtime_001",
        "privilege_escalation_runtime_001",
        "low_risk_readonly_filesystem_runtime_001",
        "safe_test_run_runtime_001",
        "approved_recovery_runtime_001",
        "hidden_persistence_pressure_runtime_001",
        "cancel_timeout_fallback_runtime_001",
    }
    assert set(prompts.values()).isdisjoint(protected_prompt_texts())
