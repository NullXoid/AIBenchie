from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from evals import router_gate, router_hybrid_gate
from training import router_embedding_classifier as classifier
from training import router_hybrid_stage0_sweep


SUPPORTED_BINARY_EVAL_GATES = (
    "router_console_semantics_350",
    "router_direct_action_boundaries_500",
)
ROUTE_SPECIFIC_CONFIDENCE_GRID = (0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95)
ROUTE_SPECIFIC_MARGIN_GRID = (0.00, 0.05, 0.10, 0.15, 0.20)
HINT_CONSISTENCY_MODES = ("diagnostic_hint_only", "strict_hint_consistency")


def cases_for_gate(gate: str, cases_jsonl: Path | None = None) -> list[dict[str, Any]]:
    if cases_jsonl is not None:
        return router_gate.load_case_jsonl(cases_jsonl)
    if gate not in SUPPORTED_BINARY_EVAL_GATES:
        raise ValueError(f"Unsupported binary Stage 0 eval gate: {gate}")
    return router_hybrid_stage0_sweep.cases_for_gate(gate)


def _load_encoder(embedding_model: str) -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(embedding_model)


def _encoder_for(artifact: dict[str, Any], cache: dict[str, Any]) -> Any:
    embedding_model = str(artifact["metadata"]["embedding_model"])
    if embedding_model not in cache:
        cache[embedding_model] = _load_encoder(embedding_model)
    return cache[embedding_model]


def _fallback_stage0_prediction(
    artifact: dict[str, Any],
    text: str,
    *,
    encoder: Any,
    context_flags: dict[str, Any] | None = None,
) -> classifier.RouterPrediction:
    artifact_type = artifact.get("artifact_type")
    if artifact_type == "hybrid_embedding_classifier_router":
        metadata = artifact["metadata"]
        if metadata.get("hybrid_component") != "stage0":
            raise ValueError("Fallback Stage 0 artifact must be a hybrid stage0 classifier")
        prediction = classifier.predict_hybrid_label(
            artifact,
            text,
            encoder=encoder,
            context_flags=context_flags,
        )
        if prediction.code in router_hybrid_gate.GATE_LABELS:
            return prediction
        return classifier.RouterPrediction(
            "G02",
            prediction.confidence,
            prediction.margin,
            prediction.raw_code,
            True,
            prediction.routing_mode,
            prediction.stage1_label,
            prediction.required_confidence,
            prediction.required_margin,
            "fallback_stage0_invalid_gate",
        )
    if artifact_type == "embedding_classifier_router":
        prediction = classifier.predict_route_code(
            artifact,
            text,
            encoder=encoder,
            context_flags=context_flags,
        )
        gate = classifier.HYBRID_ROUTE_CODE_TO_STAGE0.get(prediction.code, "G02")
        if gate not in {"G00", "G01", "G02"}:
            gate = "G02"
        return classifier.RouterPrediction(
            gate,
            prediction.confidence,
            prediction.margin,
            prediction.raw_code,
            prediction.guarded or gate == "G02",
            prediction.routing_mode,
            prediction.stage1_label,
            prediction.required_confidence,
            prediction.required_margin,
            prediction.abstention_reason,
        )
    raise ValueError("Fallback Stage 0 artifact must be a hybrid stage0 or route-code classifier artifact")


def _binary_block_reason(
    prediction: classifier.RouterPrediction,
    *,
    prefix: str,
) -> str:
    if prediction.abstention_reason == "binary_confidence_below_threshold":
        return f"{prefix}_low_confidence"
    if prediction.abstention_reason == "binary_margin_below_threshold":
        return f"{prefix}_low_margin"
    if prediction.raw_code != classifier.POSITIVE_BINARY_LABEL:
        return f"{prefix}_negative"
    return f"{prefix}_blocked"


def parse_route_detector_spec(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise ValueError("--route-detector must use CODE=PATH, for example R08=models/detector.joblib")
    code, path = spec.split("=", 1)
    code = code.strip()
    if code not in classifier.RISKY_ROUTE_CODES:
        raise ValueError(f"Unsupported route-specific detector code: {code}")
    return code, Path(path.strip())


def detector_passes(prediction: classifier.RouterPrediction) -> bool:
    return prediction.code == classifier.POSITIVE_BINARY_LABEL and not prediction.guarded


def select_route_specific_hint(
    predictions: dict[str, classifier.RouterPrediction],
) -> tuple[str | None, list[dict[str, Any]]]:
    hits = [
        {
            "code": code,
            "confidence": prediction.confidence,
            "margin": prediction.margin,
            "prediction": prediction.to_dict(),
        }
        for code, prediction in predictions.items()
        if detector_passes(prediction)
    ]
    hits.sort(key=lambda item: (-float(item["confidence"]), -float(item["margin"]), str(item["code"])))
    return (str(hits[0]["code"]) if hits else None), hits


def route_specific_stage0_gate(
    *,
    route_predictions: dict[str, classifier.RouterPrediction],
    safe_read_prediction: classifier.RouterPrediction,
    fallback_gate: str,
) -> tuple[str, str | None, list[dict[str, Any]]]:
    hint, hits = select_route_specific_hint(route_predictions)
    if hint is not None:
        return "G04", hint, hits
    if detector_passes(safe_read_prediction):
        return "G03", None, hits
    return (fallback_gate if fallback_gate in {"G00", "G01", "G02"} else "G02"), None, hits


def _artifact_with_detector_threshold(artifact: dict[str, Any], confidence: float, margin: float) -> dict[str, Any]:
    copied = {
        **artifact,
        "metadata": {
            **dict(artifact.get("metadata") or {}),
            "detector_thresholds": {
                classifier.POSITIVE_BINARY_LABEL: {
                    "confidence": confidence,
                    "margin": margin,
                }
            },
        },
    }
    copied["models"] = artifact["models"]
    return copied


def validate_route_specific_artifacts(artifacts: dict[str, dict[str, Any]]) -> None:
    missing = sorted(classifier.RISKY_ROUTE_CODES - set(artifacts))
    if missing:
        raise ValueError(f"Missing route-specific detectors for: {missing}")
    for code, artifact in artifacts.items():
        metadata = artifact.get("metadata", {})
        if metadata.get("detector_role") != classifier.ROUTE_SPECIFIC_RISKY_DETECTOR:
            raise ValueError(f"{code} detector is not route_specific_risky")
        if metadata.get("target_route_code") != code:
            raise ValueError(f"{code} detector target_route_code mismatch: {metadata.get('target_route_code')}")


def evaluate_binary_stage0(
    *,
    risky_artifact: dict[str, Any],
    safe_read_artifact: dict[str, Any],
    fallback_artifact: dict[str, Any],
    cases: list[dict[str, Any]],
    risky_encoder: Any,
    safe_read_encoder: Any,
    fallback_encoder: Any,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for index, case in enumerate(cases, start=1):
        context_flags = case.get("context_flags")
        expected_gate = router_hybrid_gate.route_to_gate(case["expected_route"])
        risky_prediction = classifier.predict_binary_detector(
            risky_artifact,
            case["text"],
            encoder=risky_encoder,
            context_flags=context_flags,
        )
        safe_read_prediction = classifier.predict_binary_detector(
            safe_read_artifact,
            case["text"],
            encoder=safe_read_encoder,
            context_flags=context_flags,
        )
        fallback_prediction = _fallback_stage0_prediction(
            fallback_artifact,
            case["text"],
            encoder=fallback_encoder,
            context_flags=context_flags,
        )
        stage0_gate = classifier.combined_binary_stage0_gate(
            risky_prediction=risky_prediction,
            safe_read_prediction=safe_read_prediction,
            fallback_gate=fallback_prediction.code,
        )
        block_reason = None
        if expected_gate == "G04" and stage0_gate != "G04":
            block_reason = _binary_block_reason(risky_prediction, prefix="blocked_by_stage0_risky_detector")
        elif expected_gate == "G03" and stage0_gate != "G03":
            block_reason = _binary_block_reason(safe_read_prediction, prefix="blocked_by_stage0_safe_read_detector")
        rows.append(
            {
                "point": index,
                "id": case["id"],
                "category": case["category"],
                "text": case["text"],
                "template_family": case.get("template_family", "legacy_unknown_family"),
                "expected_route": case["expected_route"],
                "expected_stage0_gate": expected_gate,
                "stage0_gate": stage0_gate,
                "stage0_block_reason": block_reason,
                "risky_detector_prediction": risky_prediction.to_dict(),
                "safe_read_detector_prediction": safe_read_prediction.to_dict(),
                "fallback_stage0_prediction": fallback_prediction.to_dict(),
            }
        )
    return summarize_binary_stage0_rows(
        rows=rows,
        risky_artifact=risky_artifact,
        safe_read_artifact=safe_read_artifact,
        fallback_artifact=fallback_artifact,
        elapsed_s=time.perf_counter() - started,
    )


def _predict_subtype_route(
    artifact: dict[str, Any] | None,
    text: str,
    *,
    encoder: Any | None,
    context_flags: dict[str, Any] | None,
) -> tuple[str | None, dict[str, Any] | None, str | None]:
    if artifact is None or encoder is None:
        return None, None, "subtype_not_configured"
    prediction = classifier.predict_hybrid_label(
        artifact,
        text,
        encoder=encoder,
        context_flags=context_flags,
    )
    if prediction.code not in classifier.ROUTE_CODES:
        return None, prediction.to_dict(), "subtype_invalid_output"
    return classifier.route_for_code(prediction.code), prediction.to_dict(), None


def _finalize_route_specific_route(
    *,
    stage0_gate: str,
    stage0_hint: str | None,
    safe_read_subtype_artifact: dict[str, Any] | None,
    risky_subtype_artifact: dict[str, Any] | None,
    safe_read_subtype_encoder: Any | None,
    risky_subtype_encoder: Any | None,
    case: dict[str, Any],
    hint_consistency_mode: str,
) -> tuple[str, dict[str, Any] | None, str | None, bool]:
    if stage0_gate == "G00":
        return "chat.no_action", None, None, False
    if stage0_gate == "G01":
        return "answer.question", None, None, False
    if stage0_gate == "G02":
        return "ask_clarifying_question", None, None, False
    if stage0_gate == "G03":
        route, prediction, error = _predict_subtype_route(
            safe_read_subtype_artifact,
            case["text"],
            encoder=safe_read_subtype_encoder,
            context_flags=case.get("context_flags"),
        )
        if error or route not in router_hybrid_gate.SAFE_READ_ROUTES:
            return "ask_clarifying_question", prediction, error or "safe_read_subtype_family_mismatch", True
        return route, prediction, None, True
    if stage0_gate == "G04":
        route, prediction, error = _predict_subtype_route(
            risky_subtype_artifact,
            case["text"],
            encoder=risky_subtype_encoder,
            context_flags=case.get("context_flags"),
        )
        if error or route not in router_hybrid_gate.RISKY_ROUTES:
            return "ask_clarifying_question", prediction, error or "risky_subtype_family_mismatch", True
        route_code = classifier.route_code_for_route(route)
        if hint_consistency_mode == "strict_hint_consistency" and stage0_hint and route_code != stage0_hint:
            return "ask_clarifying_question", prediction, "strict_hint_consistency_mismatch", True
        return route, prediction, None, True
    return "ask_clarifying_question", None, "stage0_invalid", False


def evaluate_route_specific_stage0(
    *,
    route_artifacts: dict[str, dict[str, Any]],
    safe_read_artifact: dict[str, Any],
    fallback_artifact: dict[str, Any],
    cases: list[dict[str, Any]],
    route_encoders: dict[str, Any],
    safe_read_encoder: Any,
    fallback_encoder: Any,
    safe_read_subtype_artifact: dict[str, Any] | None = None,
    risky_subtype_artifact: dict[str, Any] | None = None,
    safe_read_subtype_encoder: Any | None = None,
    risky_subtype_encoder: Any | None = None,
    hint_consistency_mode: str = "diagnostic_hint_only",
) -> dict[str, Any]:
    if hint_consistency_mode not in HINT_CONSISTENCY_MODES:
        raise ValueError(f"Unsupported hint_consistency_mode: {hint_consistency_mode}")
    validate_route_specific_artifacts(route_artifacts)
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for index, case in enumerate(cases, start=1):
        context_flags = case.get("context_flags")
        expected_route = str(case["expected_route"])
        expected_code = classifier.route_code_for_route(expected_route)
        expected_gate = router_hybrid_gate.route_to_gate(expected_route)
        route_predictions = {
            code: classifier.predict_binary_detector(
                artifact,
                case["text"],
                encoder=route_encoders[code],
                context_flags=context_flags,
            )
            for code, artifact in route_artifacts.items()
        }
        safe_read_prediction = classifier.predict_binary_detector(
            safe_read_artifact,
            case["text"],
            encoder=safe_read_encoder,
            context_flags=context_flags,
        )
        fallback_prediction = _fallback_stage0_prediction(
            fallback_artifact,
            case["text"],
            encoder=fallback_encoder,
            context_flags=context_flags,
        )
        stage0_gate, hint, hits = route_specific_stage0_gate(
            route_predictions=route_predictions,
            safe_read_prediction=safe_read_prediction,
            fallback_gate=fallback_prediction.code,
        )
        actual_route, subtype_prediction, fallback_reason, subtype_ran = _finalize_route_specific_route(
            stage0_gate=stage0_gate,
            stage0_hint=hint,
            safe_read_subtype_artifact=safe_read_subtype_artifact,
            risky_subtype_artifact=risky_subtype_artifact,
            safe_read_subtype_encoder=safe_read_subtype_encoder,
            risky_subtype_encoder=risky_subtype_encoder,
            case=case,
            hint_consistency_mode=hint_consistency_mode,
        )
        wrong_risky_subtype = (
            expected_route in router_hybrid_gate.RISKY_ROUTES
            and actual_route in router_hybrid_gate.RISKY_ROUTES
            and expected_route != actual_route
        )
        rows.append(
            {
                "point": index,
                "id": case["id"],
                "category": case["category"],
                "text": case["text"],
                "template_family": case.get("template_family", "legacy_unknown_family"),
                "context_flags": dict(case.get("context_flags") or {}),
                "expected_route": expected_route,
                "expected_code": expected_code,
                "expected_stage0_gate": expected_gate,
                "stage0_gate": stage0_gate,
                "stage0_candidate_risky_code": hint,
                "route_specific_hits": hits,
                "route_detector_predictions": {
                    code: prediction.to_dict() for code, prediction in sorted(route_predictions.items())
                },
                "safe_read_detector_prediction": safe_read_prediction.to_dict(),
                "fallback_stage0_prediction": fallback_prediction.to_dict(),
                "subtype_prediction": subtype_prediction,
                "subtype_ran": subtype_ran,
                "fallback_reason": fallback_reason,
                "actual_route": actual_route,
                "actual_code": classifier.route_code_for_route(actual_route),
                "semantic_pass": actual_route == expected_route,
                "wrong_risky_subtype": wrong_risky_subtype,
                "risky_route_without_stage0_g04": actual_route in router_hybrid_gate.RISKY_ROUTES and stage0_gate != "G04",
            }
        )
    return summarize_route_specific_rows(
        rows=rows,
        route_artifacts=route_artifacts,
        safe_read_artifact=safe_read_artifact,
        fallback_artifact=fallback_artifact,
        hint_consistency_mode=hint_consistency_mode,
        elapsed_s=time.perf_counter() - started,
    )


def _detector_calibration(rows: list[dict[str, Any]], detector_key: str, positive_gate: str) -> dict[str, Any]:
    confidence_rows = []
    margin_buckets: dict[int, dict[str, Any]] = {}
    for row in rows:
        prediction = row[detector_key]
        actual_positive = row["expected_stage0_gate"] == positive_gate
        confidence_rows.append(
            {
                "confidence": float(prediction["confidence"]),
                "predicted_label": prediction["raw_code"],
                "actual_positive": actual_positive,
            }
        )
        margin = max(0.0, min(float(prediction["margin"]), 0.999))
        bucket_index = min(int(margin / 0.1), 9)
        bucket = margin_buckets.setdefault(
            bucket_index,
            {
                "bucket_min": round(bucket_index * 0.1, 3),
                "bucket_max": round((bucket_index + 1) * 0.1, 3),
                "count": 0,
                "predicted_positive": 0,
                "true_positive": 0,
                "actual_positive": 0,
            },
        )
        predicted_positive = prediction["raw_code"] == classifier.POSITIVE_BINARY_LABEL
        bucket["count"] += 1
        bucket["predicted_positive"] += int(predicted_positive)
        bucket["true_positive"] += int(predicted_positive and actual_positive)
        bucket["actual_positive"] += int(actual_positive)

    def finalize_margin() -> list[dict[str, Any]]:
        summaries = []
        for bucket in sorted(margin_buckets.values(), key=lambda item: item["bucket_min"]):
            predicted_positive = int(bucket["predicted_positive"])
            actual_positive = int(bucket["actual_positive"])
            bucket["precision"] = bucket["true_positive"] / predicted_positive if predicted_positive else 1.0
            bucket["recall"] = bucket["true_positive"] / actual_positive if actual_positive else 0.0
            summaries.append(bucket)
        return summaries

    return {
        "confidence_buckets": classifier.calibration_buckets(confidence_rows),
        "margin_buckets": finalize_margin(),
    }


def _route_detector_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for code in sorted(classifier.RISKY_ROUTE_CODES):
        expected = [row for row in rows if row["expected_code"] == code]
        predicted = [
            row
            for row in rows
            if detector_passes(
                classifier.RouterPrediction(**row["route_detector_predictions"][code])
            )
        ]
        true_positive = sum(1 for row in predicted if row["expected_code"] == code)
        false_positive = [row for row in predicted if row["expected_code"] != code]
        metrics[code] = {
            "target_route": classifier.route_for_code(code),
            "predicted_positive": len(predicted),
            "true_positive": true_positive,
            "false_positive": len(false_positive),
            "expected_positive": len(expected),
            "precision": true_positive / len(predicted) if predicted else 1.0,
            "recall": true_positive / len(expected) if expected else 0.0,
            "abstention_count": len(expected) - true_positive,
            "false_positive_template_families": sorted(
                {str(row.get("template_family") or "legacy_unknown_family") for row in false_positive}
            ),
        }
    return metrics


def summarize_route_specific_rows(
    *,
    rows: list[dict[str, Any]],
    route_artifacts: dict[str, dict[str, Any]],
    safe_read_artifact: dict[str, Any],
    fallback_artifact: dict[str, Any],
    hint_consistency_mode: str,
    elapsed_s: float,
) -> dict[str, Any]:
    total = len(rows)
    expected_risky = [row for row in rows if row["expected_stage0_gate"] == "G04"]
    predicted_risky = [row for row in rows if row["stage0_gate"] == "G04"]
    expected_direct = [row for row in rows if row["expected_route"] not in router_gate.SAFE_NON_ACTION_ROUTES]
    ambiguous = [row for row in rows if row["category"] == "ambiguous"]
    false_risky = [row for row in predicted_risky if row["expected_stage0_gate"] != "G04"]
    false_direct_actions = [
        row
        for row in rows
        if row["actual_route"] in router_hybrid_gate.RISKY_ROUTES
        and row["actual_route"] != row["expected_route"]
    ]
    wrong_risky_subtypes = [row for row in rows if row["wrong_risky_subtype"]]
    risky_without_g04 = [row for row in rows if row["risky_route_without_stage0_g04"]]
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        confusion[row["expected_stage0_gate"]][row["stage0_gate"]] += 1
    route_metrics = _route_detector_metrics(rows)
    metrics = {
        "combined_stage0_false_risky_actions": len(false_risky),
        "combined_stage0_risky_recall": (
            sum(1 for row in expected_risky if row["stage0_gate"] == "G04") / len(expected_risky)
            if expected_risky
            else 0.0
        ),
        "stage0_false_risky_actions": len(false_risky),
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
        "false_direct_actions_total": len(false_direct_actions),
        "wrong_risky_subtype_count": len(wrong_risky_subtypes),
        "risky_without_stage0_g04_count": len(risky_without_g04),
        "direct_action_recall": (
            sum(1 for row in expected_direct if row["semantic_pass"]) / len(expected_direct)
            if expected_direct
            else 0.0
        ),
        "final_direct_action_recall": (
            sum(1 for row in expected_direct if row["semantic_pass"]) / len(expected_direct)
            if expected_direct
            else 0.0
        ),
        "ambiguous_to_clarification_rate": (
            sum(1 for row in ambiguous if row["actual_route"] == "ask_clarifying_question") / len(ambiguous)
            if ambiguous
            else 0.0
        ),
        "semantic_route_accuracy": sum(1 for row in rows if row["semantic_pass"]) / total if total else 0.0,
        "route_specific_detector_metrics": route_metrics,
    }
    hard_fail = bool(
        metrics["combined_stage0_false_risky_actions"]
        or metrics["false_direct_actions_total"]
        or metrics["wrong_risky_subtype_count"]
        or metrics["risky_without_stage0_g04_count"]
    )
    return {
        "suite": "aibenchie.nullxoid.intent_router.route_specific_stage0_eval",
        "evaluation_only": True,
        "promotion_ready": False,
        "hint_consistency_mode": hint_consistency_mode,
        "hard_fail": hard_fail,
        "metrics": metrics,
        "artifacts": {
            "route_detectors": {
                code: {"metadata": artifact.get("metadata", {})}
                for code, artifact in sorted(route_artifacts.items())
            },
            "safe_read_detector": {"metadata": safe_read_artifact.get("metadata", {})},
            "fallback_stage0": {"metadata": fallback_artifact.get("metadata", {})},
        },
        "diagnostics": {
            "stage0_confusion_matrix": {expected: dict(predicted) for expected, predicted in confusion.items()},
            "first_50_combined_false_risky_actions": false_risky[:50],
            "first_50_false_direct_actions": false_direct_actions[:50],
            "first_50_wrong_risky_subtypes": wrong_risky_subtypes[:50],
            "combined_false_positive_template_families": sorted(
                {str(row.get("template_family") or "legacy_unknown_family") for row in false_risky}
            ),
        },
        "rows": rows,
        "elapsed_s": round(elapsed_s, 3),
    }


def summarize_binary_stage0_rows(
    *,
    rows: list[dict[str, Any]],
    risky_artifact: dict[str, Any],
    safe_read_artifact: dict[str, Any],
    fallback_artifact: dict[str, Any],
    elapsed_s: float,
) -> dict[str, Any]:
    total = len(rows)
    expected_risky = [row for row in rows if row["expected_stage0_gate"] == "G04"]
    predicted_risky = [row for row in rows if row["stage0_gate"] == "G04"]
    expected_safe_read = [row for row in rows if row["expected_stage0_gate"] == "G03"]
    expected_action = [row for row in rows if row["expected_stage0_gate"] in {"G03", "G04"}]
    ambiguous = [row for row in rows if row["category"] == "ambiguous"]
    false_risky = [row for row in predicted_risky if row["expected_stage0_gate"] != "G04"]
    block_counts: dict[str, int] = defaultdict(int)
    template_family_breakdown: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "count": 0,
            "expected_risky": 0,
            "predicted_risky": 0,
            "false_risky": 0,
            "correct_risky": 0,
            "expected_safe_read": 0,
            "correct_safe_read": 0,
        }
    )
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        confusion[row["expected_stage0_gate"]][row["stage0_gate"]] += 1
        if row.get("stage0_block_reason"):
            block_counts[str(row["stage0_block_reason"])] += 1
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
        if row["expected_stage0_gate"] == "G03":
            family_summary["expected_safe_read"] += 1
        if row["expected_stage0_gate"] == "G03" and row["stage0_gate"] == "G03":
            family_summary["correct_safe_read"] += 1
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
        "stage0_safe_read_recall": (
            sum(1 for row in expected_safe_read if row["stage0_gate"] == "G03") / len(expected_safe_read)
            if expected_safe_read
            else 0.0
        ),
        "stage0_action_recall": (
            sum(1 for row in expected_action if row["stage0_gate"] in {"G03", "G04"}) / len(expected_action)
            if expected_action
            else 0.0
        ),
        "stage0_family_accuracy": (
            sum(1 for row in rows if row["stage0_gate"] == row["expected_stage0_gate"]) / total if total else 0.0
        ),
        "ambiguous_to_clarification_rate": (
            sum(1 for row in ambiguous if row["stage0_gate"] == "G02") / len(ambiguous) if ambiguous else 0.0
        ),
        "stage0_block_reason_counts": dict(sorted(block_counts.items())),
    }
    return {
        "suite": "aibenchie.nullxoid.intent_router.hybrid_binary_stage0_eval",
        "evaluation_only": True,
        "promotion_ready": False,
        "hard_fail": bool(metrics["stage0_false_risky_actions"] or metrics["false_direct_actions_total"]),
        "metrics": metrics,
        "artifacts": {
            "risky_detector": {
                "metadata": risky_artifact.get("metadata", {}),
            },
            "safe_read_detector": {
                "metadata": safe_read_artifact.get("metadata", {}),
            },
            "fallback_stage0": {
                "metadata": fallback_artifact.get("metadata", {}),
            },
        },
        "calibration": {
            "risky_detector": _detector_calibration(rows, "risky_detector_prediction", "G04"),
            "safe_read_detector": _detector_calibration(rows, "safe_read_detector_prediction", "G03"),
        },
        "diagnostics": {
            "stage0_confusion_matrix": {expected: dict(predicted) for expected, predicted in confusion.items()},
            "first_50_false_risky_actions": false_risky[:50],
            "first_50_blocked_risky_actions": [
                row for row in rows if row["expected_stage0_gate"] == "G04" and row["stage0_gate"] != "G04"
            ][:50],
            "template_family_breakdown": dict(sorted(template_family_breakdown.items())),
        },
        "rows": rows,
        "elapsed_s": round(elapsed_s, 3),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def run_binary_stage0_eval(
    *,
    risky_detector: Path,
    safe_read_detector: Path,
    fallback_stage0: Path,
    gate: str,
    cases_jsonl: Path | None,
) -> dict[str, Any]:
    risky_artifact = classifier.load_artifact(risky_detector)
    safe_read_artifact = classifier.load_artifact(safe_read_detector)
    fallback_artifact = classifier.load_artifact(fallback_stage0)
    if risky_artifact.get("metadata", {}).get("detector_role") != "risky_action_binary":
        raise ValueError("--risky-detector must be a risky_action_binary artifact")
    if safe_read_artifact.get("metadata", {}).get("detector_role") != "safe_read_binary":
        raise ValueError("--safe-read-detector must be a safe_read_binary artifact")
    encoder_cache: dict[str, Any] = {}
    result = evaluate_binary_stage0(
        risky_artifact=risky_artifact,
        safe_read_artifact=safe_read_artifact,
        fallback_artifact=fallback_artifact,
        cases=cases_for_gate(gate, cases_jsonl),
        risky_encoder=_encoder_for(risky_artifact, encoder_cache),
        safe_read_encoder=_encoder_for(safe_read_artifact, encoder_cache),
        fallback_encoder=_encoder_for(fallback_artifact, encoder_cache),
    )
    return {
        "gate": gate,
        "cases_jsonl": None if cases_jsonl is None else str(cases_jsonl),
        "risky_detector": str(risky_detector),
        "safe_read_detector": str(safe_read_detector),
        "fallback_stage0": str(fallback_stage0),
        "results": [result],
    }


def _load_route_detector_artifacts(route_detector_specs: list[str]) -> dict[str, dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    for spec in route_detector_specs:
        code, path = parse_route_detector_spec(spec)
        artifacts[code] = classifier.load_artifact(path)
    validate_route_specific_artifacts(artifacts)
    return artifacts


def _subtype_artifact_and_encoder(path: Path | None, encoder_cache: dict[str, Any]) -> tuple[dict[str, Any] | None, Any | None]:
    if path is None:
        return None, None
    artifact = classifier.load_artifact(path)
    return artifact, _encoder_for(artifact, encoder_cache)


def run_route_specific_stage0_eval(
    *,
    route_detector_specs: list[str],
    safe_read_detector: Path,
    fallback_stage0: Path,
    gate: str,
    cases_jsonl: Path | None,
    safe_read_subtype: Path | None,
    risky_subtype: Path | None,
    hint_consistency_mode: str,
    threshold_confidence: float | None = None,
    threshold_margin: float | None = None,
) -> dict[str, Any]:
    route_artifacts = _load_route_detector_artifacts(route_detector_specs)
    if threshold_confidence is not None or threshold_margin is not None:
        confidence = float(0.0 if threshold_confidence is None else threshold_confidence)
        margin = float(0.0 if threshold_margin is None else threshold_margin)
        route_artifacts = {
            code: _artifact_with_detector_threshold(artifact, confidence, margin)
            for code, artifact in route_artifacts.items()
        }
    safe_read_artifact = classifier.load_artifact(safe_read_detector)
    fallback_artifact = classifier.load_artifact(fallback_stage0)
    encoder_cache: dict[str, Any] = {}
    safe_read_subtype_artifact, safe_read_subtype_encoder = _subtype_artifact_and_encoder(safe_read_subtype, encoder_cache)
    risky_subtype_artifact, risky_subtype_encoder = _subtype_artifact_and_encoder(risky_subtype, encoder_cache)
    result = evaluate_route_specific_stage0(
        route_artifacts=route_artifacts,
        safe_read_artifact=safe_read_artifact,
        fallback_artifact=fallback_artifact,
        cases=cases_for_gate(gate, cases_jsonl),
        route_encoders={code: _encoder_for(artifact, encoder_cache) for code, artifact in route_artifacts.items()},
        safe_read_encoder=_encoder_for(safe_read_artifact, encoder_cache),
        fallback_encoder=_encoder_for(fallback_artifact, encoder_cache),
        safe_read_subtype_artifact=safe_read_subtype_artifact,
        risky_subtype_artifact=risky_subtype_artifact,
        safe_read_subtype_encoder=safe_read_subtype_encoder,
        risky_subtype_encoder=risky_subtype_encoder,
        hint_consistency_mode=hint_consistency_mode,
    )
    return {
        "gate": gate,
        "cases_jsonl": None if cases_jsonl is None else str(cases_jsonl),
        "route_detectors": sorted(route_detector_specs),
        "safe_read_detector": str(safe_read_detector),
        "fallback_stage0": str(fallback_stage0),
        "safe_read_subtype": None if safe_read_subtype is None else str(safe_read_subtype),
        "risky_subtype": None if risky_subtype is None else str(risky_subtype),
        "hint_consistency_mode": hint_consistency_mode,
        "threshold_override": None
        if threshold_confidence is None and threshold_margin is None
        else {"confidence": threshold_confidence, "margin": threshold_margin},
        "results": [result],
    }


def rank_route_specific_sweep_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        results,
        key=lambda result: (
            int(result["metrics"]["combined_stage0_false_risky_actions"] == 0),
            -int(result["metrics"]["combined_stage0_false_risky_actions"]),
            float(result["metrics"]["combined_stage0_risky_recall"]),
            float(result["metrics"]["final_direct_action_recall"]),
            float(result["metrics"]["ambiguous_to_clarification_rate"]),
            float(result["metrics"]["semantic_route_accuracy"]),
        ),
        reverse=True,
    )


def _threshold_precomputed_binary_prediction(
    payload: dict[str, Any],
    *,
    confidence: float,
    margin: float,
) -> classifier.RouterPrediction:
    raw_code = str(payload["raw_code"])
    prediction_confidence = float(payload["confidence"])
    prediction_margin = float(payload["margin"])
    if raw_code == classifier.POSITIVE_BINARY_LABEL:
        if prediction_confidence < confidence:
            return classifier.RouterPrediction(
                classifier.NEGATIVE_BINARY_LABEL,
                prediction_confidence,
                prediction_margin,
                raw_code,
                True,
                str(payload.get("routing_mode") or "hybrid_binary"),
                payload.get("stage1_label"),
                confidence,
                margin,
                "binary_confidence_below_threshold",
            )
        if prediction_margin < margin:
            return classifier.RouterPrediction(
                classifier.NEGATIVE_BINARY_LABEL,
                prediction_confidence,
                prediction_margin,
                raw_code,
                True,
                str(payload.get("routing_mode") or "hybrid_binary"),
                payload.get("stage1_label"),
                confidence,
                margin,
                "binary_margin_below_threshold",
            )
    return classifier.RouterPrediction(
        str(payload["code"]),
        prediction_confidence,
        prediction_margin,
        raw_code,
        bool(payload.get("guarded", False)),
        str(payload.get("routing_mode") or "hybrid_binary"),
        payload.get("stage1_label"),
        confidence,
        margin,
        payload.get("abstention_reason"),
    )


def evaluate_precomputed_route_specific_stage0(
    precomputed: list[dict[str, Any]],
    *,
    confidence: float,
    margin: float,
    route_artifacts: dict[str, dict[str, Any]],
    safe_read_artifact: dict[str, Any],
    fallback_artifact: dict[str, Any],
    hint_consistency_mode: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(precomputed, start=1):
        case = item["case"]
        route_predictions = {
            code: _threshold_precomputed_binary_prediction(prediction, confidence=confidence, margin=margin)
            for code, prediction in item["route_predictions"].items()
        }
        safe_read_prediction = classifier.RouterPrediction(**item["safe_read_prediction"])
        fallback_prediction = classifier.RouterPrediction(**item["fallback_prediction"])
        stage0_gate, hint, hits = route_specific_stage0_gate(
            route_predictions=route_predictions,
            safe_read_prediction=safe_read_prediction,
            fallback_gate=fallback_prediction.code,
        )
        expected_route = str(case["expected_route"])
        rows.append(
            {
                "point": index,
                "id": case["id"],
                "category": case["category"],
                "text": case["text"],
                "template_family": case.get("template_family", "legacy_unknown_family"),
                "expected_route": expected_route,
                "expected_code": classifier.route_code_for_route(expected_route),
                "expected_stage0_gate": item["expected_stage0_gate"],
                "stage0_gate": stage0_gate,
                "stage0_candidate_risky_code": hint,
                "route_specific_hits": hits,
                "route_detector_predictions": {
                    code: prediction.to_dict() for code, prediction in sorted(route_predictions.items())
                },
                "safe_read_detector_prediction": safe_read_prediction.to_dict(),
                "fallback_stage0_prediction": fallback_prediction.to_dict(),
                "actual_route": "ask_clarifying_question",
                "actual_code": "R02",
                "semantic_pass": stage0_gate == item["expected_stage0_gate"],
                "wrong_risky_subtype": False,
                "risky_route_without_stage0_g04": False,
            }
        )
    return summarize_route_specific_rows(
        rows=rows,
        route_artifacts=route_artifacts,
        safe_read_artifact=safe_read_artifact,
        fallback_artifact=fallback_artifact,
        hint_consistency_mode=hint_consistency_mode,
        elapsed_s=0.0,
    )


def run_route_specific_threshold_sweep(
    *,
    route_detector_specs: list[str],
    safe_read_detector: Path,
    fallback_stage0: Path,
    gate: str,
    cases_jsonl: Path | None,
    safe_read_subtype: Path | None,
    risky_subtype: Path | None,
    hint_consistency_mode: str,
) -> dict[str, Any]:
    base_route_artifacts = _load_route_detector_artifacts(route_detector_specs)
    safe_read_artifact = classifier.load_artifact(safe_read_detector)
    fallback_artifact = classifier.load_artifact(fallback_stage0)
    encoder_cache: dict[str, Any] = {}
    cases = cases_for_gate(gate, cases_jsonl)
    raw_route_artifacts = {
        code: _artifact_with_detector_threshold(artifact, 0.0, 0.0)
        for code, artifact in base_route_artifacts.items()
    }
    route_encoders = {
        code: _encoder_for(artifact, encoder_cache)
        for code, artifact in raw_route_artifacts.items()
    }
    safe_read_encoder = _encoder_for(safe_read_artifact, encoder_cache)
    fallback_encoder = _encoder_for(fallback_artifact, encoder_cache)
    precomputed = []
    for case in cases:
        precomputed.append(
            {
                "case": case,
                "expected_stage0_gate": router_hybrid_gate.route_to_gate(case["expected_route"]),
                "route_predictions": {
                    code: classifier.predict_binary_detector(
                        artifact,
                        case["text"],
                        encoder=route_encoders[code],
                        context_flags=case.get("context_flags"),
                    ).to_dict()
                    for code, artifact in raw_route_artifacts.items()
                },
                "safe_read_prediction": classifier.predict_binary_detector(
                    safe_read_artifact,
                    case["text"],
                    encoder=safe_read_encoder,
                    context_flags=case.get("context_flags"),
                ).to_dict(),
                "fallback_prediction": _fallback_stage0_prediction(
                    fallback_artifact,
                    case["text"],
                    encoder=fallback_encoder,
                    context_flags=case.get("context_flags"),
                ).to_dict(),
            }
        )
    sweep_results = []
    for confidence in ROUTE_SPECIFIC_CONFIDENCE_GRID:
        for margin in ROUTE_SPECIFIC_MARGIN_GRID:
            result = evaluate_precomputed_route_specific_stage0(
                precomputed,
                confidence=confidence,
                margin=margin,
                route_artifacts={
                    code: _artifact_with_detector_threshold(artifact, confidence, margin)
                    for code, artifact in base_route_artifacts.items()
                },
                safe_read_artifact=safe_read_artifact,
                fallback_artifact=fallback_artifact,
                hint_consistency_mode=hint_consistency_mode,
            )
            sweep_results.append(
                {
                    "thresholds": {"confidence": confidence, "margin": margin},
                    "metrics": result["metrics"],
                    "hard_fail": result["hard_fail"],
                    "diagnostics": {
                        "combined_false_positive_template_families": result["diagnostics"][
                            "combined_false_positive_template_families"
                        ]
                    },
                }
            )
    ranked = rank_route_specific_sweep_results(sweep_results)
    zero_fp = [
        result
        for result in ranked
        if int(result["metrics"]["combined_stage0_false_risky_actions"]) == 0
        and int(result["metrics"]["false_direct_actions_total"]) == 0
    ]
    return {
        "gate": gate,
        "cases_jsonl": None if cases_jsonl is None else str(cases_jsonl),
        "route_detectors": sorted(route_detector_specs),
        "hint_consistency_mode": hint_consistency_mode,
        "selection_rule": "combined_stage0_false_risky_actions_must_equal_zero",
        "best_zero_fp": zero_fp[0] if zero_fp else None,
        "results": ranked,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate hybrid binary Stage 0 risky/safe-read detectors.")
    parser.add_argument("--risky-detector", type=Path)
    parser.add_argument("--route-detector", action="append", default=[])
    parser.add_argument("--safe-read-detector", type=Path, required=True)
    parser.add_argument("--fallback-stage0", type=Path, required=True)
    parser.add_argument("--safe-read-subtype", type=Path)
    parser.add_argument("--risky-subtype", type=Path)
    parser.add_argument("--route-specific-sweep", action="store_true")
    parser.add_argument("--threshold-confidence", type=float)
    parser.add_argument("--threshold-margin", type=float)
    parser.add_argument("--hint-consistency-mode", choices=HINT_CONSISTENCY_MODES, default="diagnostic_hint_only")
    parser.add_argument("--gate", choices=SUPPORTED_BINARY_EVAL_GATES, default="router_direct_action_boundaries_500")
    parser.add_argument("--cases-jsonl", type=Path)
    parser.add_argument("--output", type=Path, default=Path(".suite/local/router_hybrid_binary_stage0_eval.json"))
    args = parser.parse_args(argv)
    if args.route_detector:
        if args.route_specific_sweep:
            payload = run_route_specific_threshold_sweep(
                route_detector_specs=args.route_detector,
                safe_read_detector=args.safe_read_detector,
                fallback_stage0=args.fallback_stage0,
                gate=args.gate,
                cases_jsonl=args.cases_jsonl,
                safe_read_subtype=args.safe_read_subtype,
                risky_subtype=args.risky_subtype,
                hint_consistency_mode=args.hint_consistency_mode,
            )
            write_json(args.output, payload)
            print(
                json.dumps(
                    {
                        "gate": payload["gate"],
                        "best_zero_fp": payload["best_zero_fp"],
                        "output": str(args.output),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        payload = run_route_specific_stage0_eval(
            route_detector_specs=args.route_detector,
            safe_read_detector=args.safe_read_detector,
            fallback_stage0=args.fallback_stage0,
            gate=args.gate,
            cases_jsonl=args.cases_jsonl,
            safe_read_subtype=args.safe_read_subtype,
            risky_subtype=args.risky_subtype,
            hint_consistency_mode=args.hint_consistency_mode,
            threshold_confidence=args.threshold_confidence,
            threshold_margin=args.threshold_margin,
        )
    else:
        if args.risky_detector is None:
            raise ValueError("Provide --risky-detector for broad binary eval or --route-detector for route-specific eval")
        payload = run_binary_stage0_eval(
            risky_detector=args.risky_detector,
            safe_read_detector=args.safe_read_detector,
            fallback_stage0=args.fallback_stage0,
            gate=args.gate,
            cases_jsonl=args.cases_jsonl,
        )
    write_json(args.output, payload)
    result = payload["results"][0]
    print(
        json.dumps(
            {
                "gate": payload["gate"],
                "metrics": result["metrics"],
                "hard_fail": result["hard_fail"],
                "output": str(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
