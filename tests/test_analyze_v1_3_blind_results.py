from __future__ import annotations

import hashlib
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_3_blind_results import (
    APPROVED_STATUSES,
    analyze_existing_v1_3_results,
)


REPORTS_DIR = ROOT / "reports" / "training"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def last_nonempty_line(path: Path) -> str:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()][-1]


def test_analyze_existing_v1_3_results_generates_reports_without_mutation(tmp_path):
    run_eval_path = ROOT / "evals" / "run_eval.py"
    selected_dataset = ROOT / "data" / "dpo_smoke_v1_1" / "dpo_pairs_selected.jsonl"
    run_eval_hash_before = sha256(run_eval_path)
    selected_hash_before = sha256(selected_dataset)

    summary = analyze_existing_v1_3_results(
        dpo_holdout_results_path=REPORTS_DIR / "v1_3_dpo_blind_holdout_results.jsonl",
        dpo_probe_results_path=REPORTS_DIR / "v1_3_dpo_blind_probe_results.jsonl",
        sft_holdout_results_path=REPORTS_DIR / "v1_3_sft_blind_holdout_results.jsonl",
        sft_probe_results_path=REPORTS_DIR / "v1_3_sft_blind_probe_results.jsonl",
        holdout_analysis_path=tmp_path / "holdout.md",
        probe_analysis_path=tmp_path / "probe.md",
        comparison_output_path=tmp_path / "comparison.md",
        decision_output_path=tmp_path / "decision.md",
    )

    assert summary["status"] in APPROVED_STATUSES
    assert (tmp_path / "holdout.md").exists()
    assert (tmp_path / "probe.md").exists()
    assert (tmp_path / "comparison.md").exists()
    assert (tmp_path / "decision.md").exists()
    assert last_nonempty_line(tmp_path / "decision.md") in APPROVED_STATUSES

    assert sha256(run_eval_path) == run_eval_hash_before
    assert sha256(selected_dataset) == selected_hash_before


def test_v1_3_repo_artifacts_exist_and_decision_status_is_approved():
    required = [
        ROOT / "training" / "freeze_v1_2_4_artifacts.py",
        ROOT / "training" / "build_v1_3_blind_suite.py",
        ROOT / "training" / "analyze_v1_3_blind_results.py",
        REPORTS_DIR / "V1_2_4_FREEZE.md",
        REPORTS_DIR / "v1_2_4_artifact_manifest.json",
        REPORTS_DIR / "V1_3_BLIND_PROMPT_LEAKAGE_CHECK.md",
        REPORTS_DIR / "v1_3_blind_prompt_similarity_report.json",
        REPORTS_DIR / "v1_3_dpo_blind_holdout_outputs.jsonl",
        REPORTS_DIR / "v1_3_dpo_blind_holdout_results.jsonl",
        REPORTS_DIR / "v1_3_dpo_blind_probe_outputs.jsonl",
        REPORTS_DIR / "v1_3_dpo_blind_probe_results.jsonl",
        REPORTS_DIR / "v1_3_sft_blind_holdout_outputs.jsonl",
        REPORTS_DIR / "v1_3_sft_blind_holdout_results.jsonl",
        REPORTS_DIR / "v1_3_sft_blind_probe_outputs.jsonl",
        REPORTS_DIR / "v1_3_sft_blind_probe_results.jsonl",
        REPORTS_DIR / "V1_3_BLIND_HOLDOUT_ANALYSIS.md",
        REPORTS_DIR / "V1_3_BLIND_DPO_PROBE_ANALYSIS.md",
        REPORTS_DIR / "V1_3_SFT_VS_DPO_BLIND_COMPARISON.md",
        REPORTS_DIR / "V1_3_NEXT_STEP_DECISION.md",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.3 artifact: {path}"

    assert last_nonempty_line(REPORTS_DIR / "V1_3_NEXT_STEP_DECISION.md") in APPROVED_STATUSES
