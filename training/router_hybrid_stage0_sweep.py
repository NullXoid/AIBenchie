from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from evals import router_gate, router_hybrid_gate
from training import router_embedding_classifier as classifier


G04_CONFIDENCE_GRID = (0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95)
G04_MARGIN_GRID = (0.00, 0.05, 0.10, 0.15, 0.20)
G03_CONFIDENCE_GRID = (0.50, 0.55, 0.60, 0.65, 0.70)
G03_MARGIN_GRID = (0.00, 0.05, 0.10, 0.15)


@dataclass(frozen=True)
class Stage0GateThresholds:
    g04_confidence: float = 0.95
    g04_margin: float = 0.20
    g03_confidence: float = 0.65
    g03_margin: float = 0.08

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def threshold_stage0_label(
    raw_label: str,
    confidence: float,
    margin: float,
    thresholds: Stage0GateThresholds,
) -> tuple[str, str | None]:
    if raw_label == "G04":
        if confidence < thresholds.g04_confidence:
            return "G02", "blocked_by_stage0_low_confidence"
        if margin < thresholds.g04_margin:
            return "G02", "blocked_by_stage0_low_margin"
    if raw_label == "G03":
        if confidence < thresholds.g03_confidence:
            return "G02", "blocked_by_stage0_low_confidence"
        if margin < thresholds.g03_margin:
            return "G02", "blocked_by_stage0_low_margin"
    return raw_label, None


def stage0_sweep_rank_key(summary: dict[str, Any]) -> tuple[Any, ...]:
    metrics = summary["metrics"]
    zero_false_risky = int(metrics.get("stage0_false_risky_actions", 0) == 0)
    zero_false_direct = int(metrics.get("false_direct_actions_total", 0) == 0)
    return (
        zero_false_risky,
        zero_false_direct,
        -int(metrics.get("stage0_false_risky_actions", 0)),
        -int(metrics.get("false_direct_actions_total", 0)),
        float(metrics.get("stage0_risky_recall", 0.0)),
        float(metrics.get("stage0_action_recall", 0.0)),
        float(metrics.get("ambiguous_to_clarification_rate", 0.0)),
        float(metrics.get("stage0_family_accuracy", 0.0)),
    )


def rank_stage0_sweep_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(results, key=stage0_sweep_rank_key, reverse=True)


def evaluate_stage0_predictions(
    raw_predictions: list[dict[str, Any]],
    thresholds: Stage0GateThresholds,
) -> dict[str, Any]:
    rows = []
    for raw in raw_predictions:
        case = raw["case"]
        expected_gate = router_hybrid_gate.route_to_gate(case["expected_route"])
        stage0_gate, block_reason = threshold_stage0_label(
            str(raw["raw_label"]),
            float(raw["confidence"]),
            float(raw["margin"]),
            thresholds,
        )
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "text": case["text"],
                "expected_route": case["expected_route"],
                "expected_stage0_gate": expected_gate,
                "stage0_gate": stage0_gate,
                "raw_stage0_gate": raw["raw_label"],
                "confidence": float(raw["confidence"]),
                "margin": float(raw["margin"]),
                "stage0_block_reason": block_reason,
                "template_family": case.get("template_family", "legacy_unknown_family"),
            }
        )
    total = len(rows)
    expected_risky = [row for row in rows if row["expected_stage0_gate"] == "G04"]
    predicted_risky = [row for row in rows if row["stage0_gate"] == "G04"]
    expected_action = [row for row in rows if row["expected_stage0_gate"] in {"G03", "G04"}]
    ambiguous = [row for row in rows if row["category"] == "ambiguous"]
    false_risky = [row for row in predicted_risky if row["expected_stage0_gate"] != "G04"]
    block_reason_counts: dict[str, int] = defaultdict(int)
    template_family_breakdown: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "count": 0,
            "expected_risky": 0,
            "predicted_risky": 0,
            "false_risky": 0,
            "correct_risky": 0,
            "blocked_by_low_confidence": 0,
            "blocked_by_low_margin": 0,
        }
    )
    for row in rows:
        family = str(row.get("template_family") or "legacy_unknown_family")
        family_summary = template_family_breakdown[family]
        family_summary["count"] += 1
        if row["expected_stage0_gate"] == "G04":
            family_summary["expected_risky"] += 1
        if row["stage0_gate"] == "G04":
            family_summary["predicted_risky"] += 1
        if row in false_risky:
            family_summary["false_risky"] += 1
        if row["expected_stage0_gate"] == "G04" and row["stage0_gate"] == "G04":
            family_summary["correct_risky"] += 1
        reason = row.get("stage0_block_reason")
        if reason:
            block_reason_counts[str(reason)] += 1
            if reason == "blocked_by_stage0_low_confidence":
                family_summary["blocked_by_low_confidence"] += 1
            if reason == "blocked_by_stage0_low_margin":
                family_summary["blocked_by_low_margin"] += 1
    metrics = {
        "stage0_false_risky_actions": len(false_risky),
        "false_direct_actions_total": len(false_risky),
        "stage0_risky_precision": (
            sum(1 for row in predicted_risky if row["expected_stage0_gate"] == "G04") / len(predicted_risky)
            if predicted_risky
            else 1.0
        ),
        "stage0_risky_recall": (
            sum(1 for row in expected_risky if row["stage0_gate"] == "G04") / len(expected_risky)
            if expected_risky
            else 0.0
        ),
        "stage0_action_recall": (
            sum(1 for row in expected_action if row["stage0_gate"] in {"G03", "G04"}) / len(expected_action)
            if expected_action
            else 0.0
        ),
        "stage0_family_accuracy": (
            sum(1 for row in rows if row["stage0_gate"] == row["expected_stage0_gate"]) / total
            if total
            else 0.0
        ),
        "ambiguous_to_clarification_rate": (
            sum(1 for row in ambiguous if row["stage0_gate"] == "G02") / len(ambiguous)
            if ambiguous
            else 0.0
        ),
        "blocked_by_low_confidence": block_reason_counts.get("blocked_by_stage0_low_confidence", 0),
        "blocked_by_low_margin": block_reason_counts.get("blocked_by_stage0_low_margin", 0),
        "stage0_block_reason_counts": dict(sorted(block_reason_counts.items())),
    }
    return {
        "thresholds": thresholds.to_dict(),
        "metrics": metrics,
        "false_positive_template_family": sorted({row["template_family"] for row in false_risky}),
        "template_family_breakdown": dict(sorted(template_family_breakdown.items())),
        "hard_fail": bool(metrics["stage0_false_risky_actions"]),
        "rows": rows,
    }


def cases_for_gate(gate: str) -> list[dict[str, Any]]:
    if gate == "router_console_semantics_350":
        return router_gate.build_console_semantics_cases()
    if gate == "router_direct_action_boundaries_500":
        return router_gate.build_direct_action_boundaries_cases()
    raise ValueError(f"Unsupported Stage 0 sweep gate: {gate}")


def precompute_stage0_predictions(
    artifact: dict[str, Any],
    cases: list[dict[str, Any]],
    *,
    encoder: Any,
) -> list[dict[str, Any]]:
    metadata = artifact["metadata"]
    artifact_type = artifact.get("artifact_type")
    if artifact_type == "hybrid_embedding_classifier_router" and metadata.get("hybrid_component") != "stage0":
        raise ValueError("Stage 0 sweep requires a hybrid stage0 classifier artifact")
    if artifact_type not in {"hybrid_embedding_classifier_router", "embedding_classifier_router"}:
        raise ValueError("Stage 0 sweep requires a hybrid stage0 or route-code classifier artifact")
    predictions = []
    for case in cases:
        if artifact_type == "hybrid_embedding_classifier_router":
            prediction = classifier.predict_hybrid_label(
                artifact,
                case["text"],
                encoder=encoder,
                context_flags=case.get("context_flags"),
            )
            raw_label = prediction.raw_code
        else:
            prediction = classifier.predict_route_code(
                artifact,
                case["text"],
                encoder=encoder,
                context_flags=case.get("context_flags"),
            )
            raw_label = classifier.HYBRID_ROUTE_CODE_TO_STAGE0.get(prediction.raw_code, "G02")
        predictions.append(
            {
                "case": case,
                "raw_label": raw_label,
                "confidence": prediction.confidence,
                "margin": prediction.margin,
            }
        )
    return predictions


def run_stage0_sweep(raw_predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for g04_confidence in G04_CONFIDENCE_GRID:
        for g04_margin in G04_MARGIN_GRID:
            for g03_confidence in G03_CONFIDENCE_GRID:
                for g03_margin in G03_MARGIN_GRID:
                    thresholds = Stage0GateThresholds(
                        g04_confidence=g04_confidence,
                        g04_margin=g04_margin,
                        g03_confidence=g03_confidence,
                        g03_margin=g03_margin,
                    )
                    results.append(evaluate_stage0_predictions(raw_predictions, thresholds))
    return rank_stage0_sweep_results(results)


def frontier_ceiling_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    zero_fp = [
        result
        for result in results
        if int(result["metrics"].get("stage0_false_risky_actions", 0)) == 0
        and int(result["metrics"].get("false_direct_actions_total", 0)) == 0
    ]
    best_zero = max(zero_fp, key=lambda result: result["metrics"].get("stage0_risky_recall", 0.0)) if zero_fp else None
    best_recall = float(best_zero["metrics"]["stage0_risky_recall"]) if best_zero else 0.0
    false_positive_points = [
        result
        for result in results
        if int(result["metrics"].get("stage0_false_risky_actions", 0)) > 0
        and float(result["metrics"].get("stage0_risky_recall", 0.0)) >= best_recall
    ]
    first_fp = min(
        false_positive_points,
        key=lambda result: (
            float(result["metrics"].get("stage0_risky_recall", 0.0)),
            int(result["metrics"].get("stage0_false_risky_actions", 0)),
        ),
    ) if false_positive_points else None
    return {
        "best_zero_fp_recall": best_recall,
        "best_zero_fp_threshold": None if best_zero is None else best_zero["thresholds"],
        "best_zero_fp_metrics": None if best_zero is None else best_zero["metrics"],
        "threshold_at_first_false_positive": None if first_fp is None else first_fp["thresholds"],
        "recall_at_first_false_positive": None if first_fp is None else first_fp["metrics"]["stage0_risky_recall"],
        "false_positive_template_family": [] if first_fp is None else first_fp["false_positive_template_family"],
        "first_false_positive_metrics": None if first_fp is None else first_fp["metrics"],
        "zero_fp_point_count": len(zero_fp),
    }


def confidence_bucket(value: float, bucket_size: float = 0.1) -> str:
    index = min(int(value / bucket_size), int(1.0 / bucket_size) - 1)
    return f"{index * bucket_size:.1f}-{(index + 1) * bucket_size:.1f}"


def calibration_summary(raw_predictions: list[dict[str, Any]]) -> dict[str, Any]:
    confidence_buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "predicted_risky": 0, "true_risky": 0, "correct_risky": 0})
    margin_buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "predicted_risky": 0, "true_risky": 0, "correct_risky": 0})
    for raw in raw_predictions:
        expected_gate = router_hybrid_gate.route_to_gate(raw["case"]["expected_route"])
        predicted_risky = raw["raw_label"] == "G04"
        true_risky = expected_gate == "G04"
        for bucket_map, value in (
            (confidence_buckets, float(raw["confidence"])),
            (margin_buckets, max(0.0, min(float(raw["margin"]), 0.999))),
        ):
            bucket = bucket_map[confidence_bucket(value)]
            bucket["count"] += 1
            bucket["predicted_risky"] += int(predicted_risky)
            bucket["true_risky"] += int(true_risky)
            bucket["correct_risky"] += int(predicted_risky and true_risky)
    def finalize(buckets: dict[str, dict[str, int]]) -> dict[str, dict[str, float | int]]:
        finalized = {}
        for name, values in sorted(buckets.items()):
            predicted = values["predicted_risky"]
            true = values["true_risky"]
            finalized[name] = {
                **values,
                "precision": values["correct_risky"] / predicted if predicted else 1.0,
                "recall": values["correct_risky"] / true if true else 0.0,
            }
        return finalized
    return {
        "confidence_buckets": finalize(confidence_buckets),
        "margin_buckets": finalize(margin_buckets),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sweep dedicated hybrid Stage 0 classifier thresholds.")
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument(
        "--gate",
        choices=["router_console_semantics_350", "router_direct_action_boundaries_500"],
        default="router_direct_action_boundaries_500",
    )
    parser.add_argument("--output", type=Path, default=Path(".suite/local/router_hybrid_stage0_sweep.json"))
    args = parser.parse_args(argv)
    artifact = classifier.load_artifact(args.artifact)
    from sentence_transformers import SentenceTransformer

    encoder = SentenceTransformer(artifact["metadata"]["embedding_model"])
    raw_predictions = precompute_stage0_predictions(artifact, cases_for_gate(args.gate), encoder=encoder)
    ranked = run_stage0_sweep(raw_predictions)
    frontier = frontier_ceiling_report(ranked)
    payload = {
        "suite": "aibenchie.nullxoid.intent_router.hybrid_stage0_threshold_sweep",
        "gate": args.gate,
        "artifact": str(args.artifact),
        "frontier": frontier,
        "calibration": calibration_summary(raw_predictions),
        "results": ranked,
    }
    write_json(args.output, payload)
    print(json.dumps({"output": str(args.output), "frontier": frontier, "best": ranked[0]["metrics"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
