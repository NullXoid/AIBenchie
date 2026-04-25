from __future__ import annotations

from pathlib import Path

from tests.conftest import ROOT, SCENARIOS_DIR
from training.analyze_sft_errors import generate_error_analysis


def test_generate_error_analysis_is_scenario_complete(tmp_path):
    output_path = tmp_path / "SFT_SMOKE_ERROR_ANALYSIS.md"
    summary = generate_error_analysis(
        ROOT / "reports" / "training" / "sft_smoke_eval_results.jsonl",
        SCENARIOS_DIR,
        output_path,
    )

    text = output_path.read_text(encoding="utf-8")

    assert summary["scenario_count"] == 11
    assert "| `danger_shortcut_001` |" in text
    assert "| `model_invoke_safe_001` |" in text
    assert "repair_instruction" in text
    assert "Add literal `file:list` and `file:read`" in text
    assert "Add literal `MAPE`, `checkpoint`, `recovery`, and `lease`" in text
