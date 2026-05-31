from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from evals import router_gate
from evals.router_backend import ProviderResult
from training import router_embedding_classifier as classifier


RISKY_CONFIDENCE_GRID = (0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95)
RISKY_MARGIN_GRID = (0.00, 0.05, 0.10, 0.15, 0.20)
NON_RISKY_CONFIDENCE_GRID = (0.35, 0.40, 0.45, 0.50)
FOCUSED_SWEEP_GATES = {"router_console_semantics_350", "router_direct_action_boundaries_500"}
HOLDOUT_GATES = {"router_holdout_1000", "router_holdout_1000_v2", "router_holdout_1000_v3"}
RISKY_RECALL_METRICS = (
    "console_run_command_recall",
    "console_edit_file_recall",
    "vision_edit_image_recall",
    "agent_start_job_recall",
    "memory_save_preference_recall",
)


def cases_for_gate(gate: str) -> list[dict[str, Any]]:
    if gate == "router_console_semantics_350":
        return router_gate.build_console_semantics_cases()
    if gate == "router_direct_action_boundaries_500":
        return router_gate.build_direct_action_boundaries_cases()
    if gate == "router_protocol_200":
        return router_gate.build_cases(router_gate.SPLIT_200)
    if gate in HOLDOUT_GATES:
        raise ValueError(f"Threshold sweeps must not use holdout gate: {gate}")
    raise ValueError(f"Unsupported threshold sweep gate: {gate}")


def route_specific_risky_recall(metrics: dict[str, Any]) -> float:
    values = [float(metrics.get(name, 0.0)) for name in RISKY_RECALL_METRICS]
    return sum(values) / len(values) if values else 0.0


def sweep_rank_key(summary: dict[str, Any]) -> tuple[Any, ...]:
    metrics = summary["metrics"]
    zero_false_direct = int(metrics.get("false_direct_actions_total", 0) == 0)
    return (
        zero_false_direct,
        -int(metrics.get("false_direct_actions_total", 0)),
        float(metrics.get("direct_action_recall", 0.0)),
        route_specific_risky_recall(metrics),
        float(metrics.get("hard_negative_recall", 0.0)),
        float(metrics.get("ambiguous_to_clarification_rate", 0.0)),
        float(metrics.get("semantic_route_accuracy", 0.0)),
        -float(metrics.get("p50_latency", 0.0)),
    )


def rank_sweep_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(results, key=sweep_rank_key, reverse=True)


def thresholds_from_values(
    *,
    risky_confidence: float,
    risky_margin: float,
    non_risky_confidence: float,
    use_per_route_defaults: bool,
) -> classifier.ClassifierThresholds:
    return classifier.ClassifierThresholds(
        risky_confidence=risky_confidence,
        risky_margin=risky_margin,
        non_risky_confidence=non_risky_confidence,
        per_route=classifier.default_per_route_thresholds() if use_per_route_defaults else {},
    )


def _slice_embedding(embeddings: Any, index: int) -> Any:
    return embeddings[index : index + 1]


def precompute_raw_predictions(
    artifact: dict[str, Any],
    cases: list[dict[str, Any]],
    *,
    encoder: Any,
    context_flags: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    metadata = artifact["metadata"]
    routing_mode = str(metadata["routing_mode"])
    context_mode = str(metadata.get("context_mode") or "text_only")
    texts = [
        classifier.format_classifier_text(case["text"], context_mode=context_mode, context_flags=context_flags)
        for case in cases
    ]
    embeddings = classifier.encode_texts(encoder, texts)
    raw_predictions: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        embedding = _slice_embedding(embeddings, index)
        if routing_mode == "flat_15_class":
            ranked = classifier._probabilities(artifact["models"]["flat"], embedding)
            raw_code, confidence = ranked[0]
            raw_predictions.append(
                {
                    "case": case,
                    "raw_code": raw_code,
                    "confidence": confidence,
                    "margin": classifier._top_margin(ranked),
                    "stage1_label": None,
                }
            )
            continue
        stage1_ranked = classifier._probabilities(artifact["models"]["stage1"], embedding)
        stage1_label, stage1_confidence = stage1_ranked[0]
        stage1_margin = classifier._top_margin(stage1_ranked)
        if routing_mode == "two_stage":
            if stage1_label != classifier.ACTION_STAGE_LABEL:
                raw_predictions.append(
                    {
                        "case": case,
                        "raw_code": stage1_label,
                        "confidence": stage1_confidence,
                        "margin": stage1_margin,
                        "stage1_label": stage1_label,
                    }
                )
                continue
            stage2_ranked = classifier._probabilities(artifact["models"]["stage2"], embedding)
            raw_code, confidence = stage2_ranked[0]
            raw_predictions.append(
                {
                    "case": case,
                    "raw_code": raw_code,
                    "confidence": confidence,
                    "margin": classifier._top_margin(stage2_ranked),
                    "stage1_label": stage1_label,
                }
            )
            continue
        if routing_mode != "three_stage":
            raise ValueError(f"Unsupported routing_mode in artifact: {routing_mode}")
        if stage1_label in classifier.THREE_STAGE_SAFE_LABEL_TO_CODE:
            raw_predictions.append(
                {
                    "case": case,
                    "raw_code": classifier.THREE_STAGE_SAFE_LABEL_TO_CODE[stage1_label],
                    "confidence": stage1_confidence,
                    "margin": stage1_margin,
                    "stage1_label": stage1_label,
                }
            )
            continue
        if stage1_label == classifier.THREE_STAGE_SAFE_READ:
            stage2_ranked = classifier._probabilities(artifact["models"]["safe_read"], embedding)
            raw_code, confidence = stage2_ranked[0]
            raw_predictions.append(
                {
                    "case": case,
                    "raw_code": raw_code,
                    "confidence": confidence,
                    "margin": classifier._top_margin(stage2_ranked),
                    "stage1_label": stage1_label,
                    "stage1_confidence": stage1_confidence,
                    "stage1_margin": stage1_margin,
                }
            )
            continue
        if stage1_label == classifier.THREE_STAGE_RISKY:
            stage2_ranked = classifier._probabilities(artifact["models"]["risky"], embedding)
            raw_code, confidence = stage2_ranked[0]
            raw_predictions.append(
                {
                    "case": case,
                    "raw_code": raw_code,
                    "confidence": confidence,
                    "margin": classifier._top_margin(stage2_ranked),
                    "stage1_label": stage1_label,
                    "stage1_confidence": stage1_confidence,
                    "stage1_margin": stage1_margin,
                }
            )
            continue
        raise ValueError(f"Unsupported three_stage label: {stage1_label}")
    return raw_predictions


def prediction_from_raw(
    raw: dict[str, Any],
    *,
    thresholds: classifier.ClassifierThresholds,
    routing_mode: str,
) -> classifier.RouterPrediction:
    if (
        routing_mode == "three_stage"
        and raw.get("stage1_label") == classifier.THREE_STAGE_RISKY
        and not (
            float(raw.get("stage1_confidence", 0.0)) >= thresholds.risky_confidence
            and float(raw.get("stage1_margin", 0.0)) >= thresholds.risky_margin
        )
    ):
        return classifier.RouterPrediction(
            "R02",
            float(raw.get("stage1_confidence", 0.0)),
            float(raw.get("stage1_margin", 0.0)),
            classifier.THREE_STAGE_RISKY,
            True,
            routing_mode,
            classifier.THREE_STAGE_RISKY,
            thresholds.risky_confidence,
            thresholds.risky_margin,
            "stage1_blocks_risky_action",
        )
    code, guarded, required_confidence, required_margin, reason = classifier.threshold_decision(
        str(raw["raw_code"]),
        float(raw["confidence"]),
        float(raw["margin"]),
        thresholds,
    )
    return classifier.RouterPrediction(
        code,
        float(raw["confidence"]),
        float(raw["margin"]),
        str(raw["raw_code"]),
        guarded,
        routing_mode,
        raw.get("stage1_label"),
        required_confidence,
        required_margin,
        reason,
    )


def evaluate_raw_predictions(
    raw_predictions: list[dict[str, Any]],
    *,
    thresholds: classifier.ClassifierThresholds,
    routing_mode: str,
    model_name: str,
    gate: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for index, raw in enumerate(raw_predictions, start=1):
        row_started = time.perf_counter()
        case = raw["case"]
        prediction = prediction_from_raw(raw, thresholds=thresholds, routing_mode=routing_mode)
        latency_ms = int((time.perf_counter() - row_started) * 1000)
        actual_route = classifier.ROUTE_CODES[prediction.code]
        provider_result = ProviderResult(
            text=prediction.code,
            backend="embedding_classifier",
            model=model_name,
            device="local",
            dtype="embedding_classifier",
            quantization=None,
            latency_ms=latency_ms,
            tokens_generated=1,
            tokens_per_second=0.0,
            stop_enforced=True,
            protocol="route_code",
            classifier_metadata={
                "thresholds": thresholds.to_dict(),
                "last_prediction": prediction.to_dict(),
            },
        )
        rows.append(
            {
                "point": index,
                "id": case["id"],
                "category": case["category"],
                "text": case["text"],
                "expected_route": case["expected_route"],
                "expected_output": router_gate.expected_output_for_route(case["expected_route"], "route_code"),
                "actual_route": actual_route,
                "raw": prediction.code,
                "protocol_valid": True,
                "semantic_pass": actual_route == case["expected_route"],
                "action_family": case["action_family"],
                "provider_result": provider_result.to_dict(),
            }
        )
    return router_gate.summarize_rows(
        "embedding_classifier",
        model_name,
        rows,
        "route_code",
        gate=gate,
        elapsed_s=time.perf_counter() - started,
    )


def run_threshold_sweep(
    artifact: dict[str, Any],
    cases: list[dict[str, Any]],
    *,
    encoder: Any,
    model_name: str,
    gate: str,
    use_per_route_defaults: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    routing_mode = str(artifact["metadata"]["routing_mode"])
    raw_predictions = precompute_raw_predictions(artifact, cases, encoder=encoder)
    for risky_confidence in RISKY_CONFIDENCE_GRID:
        for risky_margin in RISKY_MARGIN_GRID:
            for non_risky_confidence in NON_RISKY_CONFIDENCE_GRID:
                thresholds = thresholds_from_values(
                    risky_confidence=risky_confidence,
                    risky_margin=risky_margin,
                    non_risky_confidence=non_risky_confidence,
                    use_per_route_defaults=use_per_route_defaults,
                )
                summary = evaluate_raw_predictions(
                    raw_predictions,
                    thresholds=thresholds,
                    routing_mode=routing_mode,
                    model_name=model_name,
                    gate=gate,
                )
                summary["thresholds"] = thresholds.to_dict()
                summary["route_specific_risky_recall"] = route_specific_risky_recall(summary["metrics"])
                results.append(summary)
    return rank_sweep_results(results)


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": result["model"],
        "gate": result["gate"],
        "thresholds": result["thresholds"],
        "promotion_ready": result["promotion_ready"],
        "promotion_blockers": result["promotion_blockers"],
        "route_specific_risky_recall": result["route_specific_risky_recall"],
        "metrics": result["metrics"],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sweep embedding classifier router safety thresholds.")
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument(
        "--gate",
        action="append",
        choices=sorted(FOCUSED_SWEEP_GATES | {"router_protocol_200"}),
        default=[],
    )
    parser.add_argument("--cases-jsonl", type=Path)
    parser.add_argument("--use-per-route-defaults", action="store_true")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--best-artifact-output", type=Path)
    parser.add_argument("--output", type=Path, default=Path(".suite/local/router_embedding_threshold_sweep.json"))
    args = parser.parse_args(argv)

    artifact = classifier.load_artifact(args.artifact)
    metadata = artifact["metadata"]
    if args.cases_jsonl:
        cases = router_gate.load_case_jsonl(args.cases_jsonl)
        gates = [str(args.cases_jsonl)]
    else:
        gates = args.gate or ["router_console_semantics_350", "router_direct_action_boundaries_500"]
        cases = []
        for gate in gates:
            cases.extend(cases_for_gate(gate))
    from sentence_transformers import SentenceTransformer

    encoder = SentenceTransformer(metadata["embedding_model"])
    ranked = run_threshold_sweep(
        artifact,
        cases,
        encoder=encoder,
        model_name=str(args.artifact),
        gate="threshold_sweep_combined",
        use_per_route_defaults=args.use_per_route_defaults,
    )
    best = ranked[0]
    if args.best_artifact_output:
        best_thresholds = classifier.ClassifierThresholds.from_dict(best["thresholds"])
        classifier.save_artifact(classifier.apply_thresholds_to_artifact(artifact, best_thresholds), args.best_artifact_output)
    payload = {
        "suite": "aibenchie.nullxoid.intent_router.embedding_threshold_sweep",
        "artifact": str(args.artifact),
        "gates": gates,
        "case_count": len(cases),
        "use_per_route_defaults": args.use_per_route_defaults,
        "best": compact_result(best),
        "top_results": [compact_result(result) for result in ranked[: args.top_n]],
    }
    write_json(args.output, payload)
    print(json.dumps({"output": str(args.output), "case_count": len(cases), "best": payload["best"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
