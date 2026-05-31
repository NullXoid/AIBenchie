from __future__ import annotations

import pytest

from training import router_embedding_classifier as classifier
from training import router_embedding_threshold_sweep as sweep


def summary(
    *,
    false_direct: int,
    direct_recall: float,
    semantic: float = 0.5,
    hard_negative: float = 0.9,
    ambiguity: float = 1.0,
    risky_recall: float = 0.4,
    latency: float = 10.0,
) -> dict:
    return {
        "metrics": {
            "false_direct_actions_total": false_direct,
            "direct_action_recall": direct_recall,
            "semantic_route_accuracy": semantic,
            "hard_negative_recall": hard_negative,
            "ambiguous_to_clarification_rate": ambiguity,
            "console_run_command_recall": risky_recall,
            "console_edit_file_recall": risky_recall,
            "vision_edit_image_recall": risky_recall,
            "agent_start_job_recall": risky_recall,
            "memory_save_preference_recall": risky_recall,
            "p50_latency": latency,
        }
    }


def test_threshold_sweep_ranking_requires_zero_false_direct_before_recall():
    unsafe_high_recall = summary(false_direct=1, direct_recall=0.99)
    safe_low_recall = summary(false_direct=0, direct_recall=0.60)

    ranked = sweep.rank_sweep_results([unsafe_high_recall, safe_low_recall])

    assert ranked[0] is safe_low_recall


def test_threshold_sweep_ranking_uses_direct_action_recall_then_risky_recall():
    weaker = summary(false_direct=0, direct_recall=0.80, risky_recall=0.60)
    stronger = summary(false_direct=0, direct_recall=0.85, risky_recall=0.20)
    tie_breaker = summary(false_direct=0, direct_recall=0.80, risky_recall=0.70)

    ranked = sweep.rank_sweep_results([weaker, stronger, tie_breaker])

    assert ranked[0] is stronger
    assert ranked[1] is tie_breaker


def test_threshold_sweep_refuses_holdout_gates():
    with pytest.raises(ValueError, match="must not use holdout"):
        sweep.cases_for_gate("router_holdout_1000_v3")


def test_thresholds_from_values_can_disable_per_route_defaults_for_global_sweep():
    global_thresholds = sweep.thresholds_from_values(
        risky_confidence=0.70,
        risky_margin=0.05,
        non_risky_confidence=0.40,
        use_per_route_defaults=False,
    )
    per_route_thresholds = sweep.thresholds_from_values(
        risky_confidence=0.70,
        risky_margin=0.05,
        non_risky_confidence=0.40,
        use_per_route_defaults=True,
    )

    assert global_thresholds.per_route == {}
    assert per_route_thresholds.per_route["R13"] == classifier.RouteThreshold(confidence=0.95, margin=0.20)
