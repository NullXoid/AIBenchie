from __future__ import annotations

from tests.conftest import ROOT, SCENARIOS_DIR
from training.analyze_final_two_failures import generate_final_two_failure_analysis


def test_generate_final_two_failure_analysis_is_targeted_and_complete(tmp_path):
    output_path = tmp_path / "V0_8_FINAL_TWO_FAILURE_ANALYSIS.md"
    summary = generate_final_two_failure_analysis(
        ROOT / "reports" / "training" / "v0_7_sft_eval_results.jsonl",
        SCENARIOS_DIR,
        output_path,
    )

    text = output_path.read_text(encoding="utf-8")

    assert summary["scenario_count"] == 2
    assert "| `danger_shortcut_001` |" in text
    assert "| `shutdown_conflict_001` |" in text
    assert "| `audit_evasion_001` |" not in text
    assert "exact_phrase_repair_needed" in text
    assert "safe_wording_to_avoid_forbidden_phrases" in text
