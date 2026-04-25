from __future__ import annotations

from tests.conftest import ROOT, SCENARIOS_DIR
from training.analyze_remaining_failures import generate_remaining_failure_analysis


def test_generate_remaining_failure_analysis_is_targeted_and_complete(tmp_path):
    output_path = tmp_path / "V0_7_REMAINING_FAILURE_ANALYSIS.md"
    summary = generate_remaining_failure_analysis(
        ROOT / "reports" / "training" / "v0_6_sft_eval_results.jsonl",
        SCENARIOS_DIR,
        output_path,
    )

    text = output_path.read_text(encoding="utf-8")

    assert summary["scenario_count"] == 6
    assert "| `ambiguous_goal_001` |" in text
    assert "| `shutdown_conflict_001` |" in text
    assert "| `memory_read_summary_001` |" not in text
    assert "exact_phrase_repair_needed" in text
    assert "safe_wording_to_avoid_must_not_include" in text
