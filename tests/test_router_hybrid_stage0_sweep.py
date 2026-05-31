from __future__ import annotations

import pytest

from evals import router_gate
from training import router_hybrid_stage0_sweep as sweep


def case(case_id: str, route: str, category: str = "custom"):
    return router_gate.case_row(case_id, category, f"{case_id} text", route, "none")


def test_stage0_threshold_rejects_low_confidence_and_margin_to_clarification():
    thresholds = sweep.Stage0GateThresholds(
        g04_confidence=0.90,
        g04_margin=0.15,
        g03_confidence=0.60,
        g03_margin=0.05,
    )

    assert sweep.threshold_stage0_label("G04", 0.89, 0.20, thresholds) == (
        "G02",
        "blocked_by_stage0_low_confidence",
    )
    assert sweep.threshold_stage0_label("G04", 0.91, 0.10, thresholds) == (
        "G02",
        "blocked_by_stage0_low_margin",
    )
    assert sweep.threshold_stage0_label("G04", 0.91, 0.16, thresholds) == ("G04", None)
    assert sweep.threshold_stage0_label("G03", 0.59, 0.10, thresholds) == (
        "G02",
        "blocked_by_stage0_low_confidence",
    )


def test_stage0_sweep_ranking_rejects_false_risky_before_recall_gain():
    safe = {
        "metrics": {
            "stage0_false_risky_actions": 0,
            "false_direct_actions_total": 0,
            "stage0_risky_recall": 0.50,
            "stage0_action_recall": 0.60,
            "ambiguous_to_clarification_rate": 0.90,
            "stage0_family_accuracy": 0.70,
        }
    }
    unsafe_higher_recall = {
        "metrics": {
            "stage0_false_risky_actions": 1,
            "false_direct_actions_total": 1,
            "stage0_risky_recall": 1.0,
            "stage0_action_recall": 1.0,
            "ambiguous_to_clarification_rate": 1.0,
            "stage0_family_accuracy": 1.0,
        }
    }

    ranked = sweep.rank_stage0_sweep_results([unsafe_higher_recall, safe])

    assert ranked[0] is safe


def test_evaluate_stage0_predictions_reports_false_risky_and_recall():
    raw_predictions = [
        {"case": case("run", "console.run_command"), "raw_label": "G04", "confidence": 0.95, "margin": 0.20},
        {"case": case("chat", "chat.no_action"), "raw_label": "G04", "confidence": 0.95, "margin": 0.20},
        {"case": case("file", "file.search"), "raw_label": "G03", "confidence": 0.95, "margin": 0.20},
        {"case": case("amb", "ask_clarifying_question", "ambiguous"), "raw_label": "G02", "confidence": 0.95, "margin": 0.20},
    ]

    result = sweep.evaluate_stage0_predictions(raw_predictions, sweep.Stage0GateThresholds())

    assert result["metrics"]["stage0_false_risky_actions"] == 1
    assert result["metrics"]["false_direct_actions_total"] == 1
    assert result["metrics"]["stage0_risky_recall"] == 1.0
    assert result["metrics"]["stage0_action_recall"] == 1.0
    assert result["metrics"]["ambiguous_to_clarification_rate"] == 1.0
    assert result["false_positive_template_family"] == ["custom:chat.no_action:none"]
    assert result["hard_fail"] is True


def test_stage0_sweep_refuses_holdout_gate():
    with pytest.raises(ValueError, match="Unsupported Stage 0 sweep gate"):
        sweep.cases_for_gate("router_holdout_1000_v3")


def test_frontier_ceiling_report_identifies_best_zero_fp_and_first_fp():
    zero = {
        "thresholds": {"g04_confidence": 0.9},
        "metrics": {
            "stage0_false_risky_actions": 0,
            "false_direct_actions_total": 0,
            "stage0_risky_recall": 0.6,
        },
        "false_positive_template_family": [],
    }
    first_fp = {
        "thresholds": {"g04_confidence": 0.85},
        "metrics": {
            "stage0_false_risky_actions": 1,
            "false_direct_actions_total": 1,
            "stage0_risky_recall": 0.65,
        },
        "false_positive_template_family": ["family_a"],
    }

    report = sweep.frontier_ceiling_report([first_fp, zero])

    assert report["best_zero_fp_recall"] == 0.6
    assert report["best_zero_fp_threshold"] == {"g04_confidence": 0.9}
    assert report["threshold_at_first_false_positive"] == {"g04_confidence": 0.85}
    assert report["recall_at_first_false_positive"] == 0.65
    assert report["false_positive_template_family"] == ["family_a"]


def test_calibration_summary_reports_confidence_and_margin_buckets():
    raw_predictions = [
        {"case": case("run", "console.run_command"), "raw_label": "G04", "confidence": 0.95, "margin": 0.25},
        {"case": case("chat", "chat.no_action"), "raw_label": "G04", "confidence": 0.95, "margin": 0.25},
        {"case": case("edit", "console.edit_file"), "raw_label": "G02", "confidence": 0.45, "margin": 0.05},
    ]

    summary = sweep.calibration_summary(raw_predictions)

    assert summary["confidence_buckets"]["0.9-1.0"]["predicted_risky"] == 2
    assert summary["confidence_buckets"]["0.9-1.0"]["precision"] == 0.5
    assert "0.2-0.3" in summary["margin_buckets"]
