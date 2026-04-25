from __future__ import annotations

import hashlib
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_3_1_blind_dpo_repair import (
    APPROVED_STATUSES,
    REPAIR_OPTIONS,
    STATUS_DPO_PROBE_TARGETED_EXPANSION,
    analyze_v1_3_1_blind_dpo_repair,
)


REPORTS_DIR = ROOT / "reports" / "training"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def last_nonempty_line(path: Path) -> str:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][-1]


def test_analyze_v1_3_1_blind_dpo_repair_generates_reports_without_mutation(tmp_path):
    run_eval_path = ROOT / "evals" / "run_eval.py"
    selected_dataset = ROOT / "data" / "dpo_smoke_v1_1" / "dpo_pairs_selected.jsonl"
    run_eval_hash_before = sha256(run_eval_path)
    selected_hash_before = sha256(selected_dataset)

    summary = analyze_v1_3_1_blind_dpo_repair(
        dpo_holdout_results_path=REPORTS_DIR / "v1_3_dpo_blind_holdout_results.jsonl",
        sft_holdout_results_path=REPORTS_DIR / "v1_3_sft_blind_holdout_results.jsonl",
        dpo_probe_results_path=REPORTS_DIR / "v1_3_dpo_blind_probe_results.jsonl",
        sft_probe_results_path=REPORTS_DIR / "v1_3_sft_blind_probe_results.jsonl",
        dev_dpo_probe_results_path=REPORTS_DIR / "v1_2_4_dpo_probe_results.jsonl",
        run_config_path=REPORTS_DIR / "v1_2_4_dpo_run_config.json",
        train_log_path=REPORTS_DIR / "v1_2_4_dpo_train_log.jsonl",
        selected_dpo_path=selected_dataset,
        blind_probe_dir=ROOT / "evals" / "dpo_probes" / "blind_v1_3",
        delta_review_path=tmp_path / "delta.md",
        probe_failure_review_path=tmp_path / "probe_failures.md",
        coverage_review_path=tmp_path / "coverage.md",
        repair_options_path=tmp_path / "options.md",
        decision_review_path=tmp_path / "decision.md",
    )

    assert summary["status"] == STATUS_DPO_PROBE_TARGETED_EXPANSION
    assert summary["status"] in APPROVED_STATUSES
    assert summary["dpo_blind_probe_total"] == 7
    assert summary["sft_blind_probe_total"] == 9
    assert summary["underperformed_categories"] == [
        "audit_evasion_vs_audit_preservation",
        "unsafe_compliance_vs_safe_challenge",
    ]

    delta_text = (tmp_path / "delta.md").read_text(encoding="utf-8")
    assert "DPO vs SFT blind probe delta" in delta_text
    assert "`7/14 - 9/14 = -2`" in delta_text

    probe_failure_text = (tmp_path / "probe_failures.md").read_text(encoding="utf-8")
    assert "categories where DPO underperformed SFT" in probe_failure_text
    assert "`audit_evasion_vs_audit_preservation`" in probe_failure_text
    assert "`unsafe_compliance_vs_safe_challenge`" in probe_failure_text

    coverage_text = (tmp_path / "coverage.md").read_text(encoding="utf-8")
    assert "re-derived via `audit_pair`" in coverage_text
    assert "`overrefusal_vs_bounded_execute`" in coverage_text

    options_text = (tmp_path / "options.md").read_text(encoding="utf-8")
    for option in REPAIR_OPTIONS:
        assert f"## {option}" in options_text

    decision_text = (tmp_path / "decision.md").read_text(encoding="utf-8")
    assert decision_text.rstrip().endswith(STATUS_DPO_PROBE_TARGETED_EXPANSION)

    assert sha256(run_eval_path) == run_eval_hash_before
    assert sha256(selected_dataset) == selected_hash_before


def test_v1_3_1_repo_artifacts_exist_and_end_with_approved_status():
    required = [
        ROOT / "training" / "analyze_v1_3_1_blind_dpo_repair.py",
        REPORTS_DIR / "V1_3_1_BLIND_DPO_DELTA_REVIEW.md",
        REPORTS_DIR / "V1_3_1_BLIND_PROBE_FAILURE_REVIEW.md",
        REPORTS_DIR / "V1_3_1_DPO_DATA_COVERAGE_REVIEW.md",
        REPORTS_DIR / "V1_3_1_DPO_REPAIR_OPTIONS.md",
        REPORTS_DIR / "DPO_READINESS_REVIEW_V1_3_1.md",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.3.1 artifact: {path}"

    assert last_nonempty_line(REPORTS_DIR / "DPO_READINESS_REVIEW_V1_3_1.md") in APPROVED_STATUSES


def test_v1_3_1_actual_reports_capture_blind_dpo_repair_signal():
    delta_text = (REPORTS_DIR / "V1_3_1_BLIND_DPO_DELTA_REVIEW.md").read_text(encoding="utf-8")
    probe_failure_text = (
        REPORTS_DIR / "V1_3_1_BLIND_PROBE_FAILURE_REVIEW.md"
    ).read_text(encoding="utf-8")
    coverage_text = (
        REPORTS_DIR / "V1_3_1_DPO_DATA_COVERAGE_REVIEW.md"
    ).read_text(encoding="utf-8")
    options_text = (
        REPORTS_DIR / "V1_3_1_DPO_REPAIR_OPTIONS.md"
    ).read_text(encoding="utf-8")

    assert "DPO vs SFT blind probe delta" in delta_text
    assert "`7/14 - 9/14 = -2`" in delta_text
    assert "categories where DPO underperformed SFT" in probe_failure_text
    assert "`audit_evasion_vs_audit_preservation`" in probe_failure_text
    assert "`unsafe_compliance_vs_safe_challenge`" in probe_failure_text
    assert "re-derived via `audit_pair`" in coverage_text
    for option in REPAIR_OPTIONS:
        assert f"## {option}" in options_text
