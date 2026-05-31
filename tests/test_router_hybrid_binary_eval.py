from __future__ import annotations

import pytest

from evals import router_gate
from training import router_embedding_classifier as classifier
from training import router_hybrid_binary_eval as binary_eval


class TextEncoder:
    def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
        return list(texts)


class TextProbabilityClassifier:
    def __init__(self, labels, probability_by_token, default):
        self.classes_ = list(labels)
        self.probability_by_token = probability_by_token
        self.default = default

    def predict_proba(self, embeddings):
        rows = []
        for text in embeddings:
            probabilities = self.default
            for token, token_probabilities in self.probability_by_token.items():
                if token in text:
                    probabilities = token_probabilities
                    break
            rows.append(probabilities)
        return rows


def case(case_id: str, text: str, route: str, category: str = "custom"):
    return {
        **router_gate.case_row(case_id, category, text, route, "none"),
        "template_family": f"family:{case_id}",
    }


def binary_artifact(role: str, model, target_route_code: str | None = None) -> dict:
    return {
        "artifact_type": "hybrid_binary_detector",
        "version": 1,
        "metadata": {
            "embedding_model": "fake/encoder",
            "classifier_type": "linear_svc_calibrated",
            "routing_mode": "hybrid_binary",
            "detector_role": role,
            "target_route_code": target_route_code,
            "context_mode": "text_only",
            "detector_thresholds": {"allow": {"confidence": 0.90, "margin": 0.0}},
            "class_labels": ["allow", "block"],
            "positive_label": "allow",
            "negative_label": "block",
            "positive_route_codes": sorted(classifier.binary_positive_codes(role, target_route_code)),
        },
        "models": {"classifier": model},
    }


def stage0_artifact(model) -> dict:
    return {
        "artifact_type": "hybrid_embedding_classifier_router",
        "version": 1,
        "metadata": {
            "embedding_model": "fake/encoder",
            "classifier_type": "linear_svc_calibrated",
            "routing_mode": "hybrid",
            "hybrid_component": "stage0",
            "context_mode": "text_only",
            "thresholds": classifier.ClassifierThresholds().to_dict(),
            "class_labels": ["G00", "G02"],
            "train_data_hash": "abc",
            "train_count": 2,
        },
        "models": {"classifier": model},
    }


def subtype_artifact(component: str, model, labels) -> dict:
    return {
        "artifact_type": "hybrid_embedding_classifier_router",
        "version": 1,
        "metadata": {
            "embedding_model": "fake/encoder",
            "classifier_type": "linear_svc_calibrated",
            "routing_mode": "hybrid",
            "hybrid_component": component,
            "context_mode": "text_only",
            "thresholds": classifier.ClassifierThresholds(
                risky_confidence=0.0,
                risky_margin=0.0,
                non_risky_confidence=0.0,
                per_route={code: classifier.RouteThreshold(confidence=0.0, margin=0.0) for code in labels},
            ).to_dict(),
            "class_labels": list(labels),
            "train_data_hash": "abc",
            "train_count": 2,
        },
        "models": {"classifier": model},
    }


def route_specific_artifacts(probability_by_code: dict[str, list[float]]) -> dict:
    artifacts = {}
    for code in sorted(classifier.RISKY_ROUTE_CODES):
        artifacts[code] = binary_artifact(
            classifier.ROUTE_SPECIFIC_RISKY_DETECTOR,
            TextProbabilityClassifier(["allow", "block"], {code: probability_by_code.get(code, [0.05, 0.95])}, [0.05, 0.95]),
            target_route_code=code,
        )
    return artifacts


def test_binary_stage0_eval_never_emits_g04_when_risky_detector_blocks():
    risky = binary_artifact(
        "risky_action_binary",
        TextProbabilityClassifier(["allow", "block"], {"run": [0.89, 0.11]}, [0.05, 0.95]),
    )
    safe_read = binary_artifact(
        "safe_read_binary",
        TextProbabilityClassifier(["allow", "block"], {}, [0.05, 0.95]),
    )
    fallback = stage0_artifact(TextProbabilityClassifier(["G00", "G02"], {}, [0.95, 0.05]))

    result = binary_eval.evaluate_binary_stage0(
        risky_artifact=risky,
        safe_read_artifact=safe_read,
        fallback_artifact=fallback,
        cases=[case("run", "run tests now", "console.run_command")],
        risky_encoder=TextEncoder(),
        safe_read_encoder=TextEncoder(),
        fallback_encoder=TextEncoder(),
    )

    assert result["metrics"]["stage0_false_risky_actions"] == 0
    assert result["metrics"]["stage0_risky_recall"] == 0.0
    assert result["rows"][0]["stage0_gate"] != "G04"
    assert result["rows"][0]["stage0_block_reason"] == "blocked_by_stage0_risky_detector_low_confidence"


def test_binary_stage0_eval_combines_risky_safe_read_and_fallback():
    risky = binary_artifact(
        "risky_action_binary",
        TextProbabilityClassifier(["allow", "block"], {"run": [0.96, 0.04]}, [0.05, 0.95]),
    )
    safe_read = binary_artifact(
        "safe_read_binary",
        TextProbabilityClassifier(["allow", "block"], {"search": [0.96, 0.04]}, [0.05, 0.95]),
    )
    fallback = stage0_artifact(
        TextProbabilityClassifier(["G00", "G02"], {"ambiguous": [0.05, 0.95]}, [0.95, 0.05])
    )

    result = binary_eval.evaluate_binary_stage0(
        risky_artifact=risky,
        safe_read_artifact=safe_read,
        fallback_artifact=fallback,
        cases=[
            case("run", "run tests now", "console.run_command"),
            case("search", "search project files", "file.search"),
            case("chat", "thinking about commands", "chat.no_action"),
            case("amb", "ambiguous command thing", "ask_clarifying_question", "ambiguous"),
        ],
        risky_encoder=TextEncoder(),
        safe_read_encoder=TextEncoder(),
        fallback_encoder=TextEncoder(),
    )

    assert [row["stage0_gate"] for row in result["rows"]] == ["G04", "G03", "G00", "G02"]
    assert result["metrics"]["stage0_false_risky_actions"] == 0
    assert result["metrics"]["stage0_risky_recall"] == 1.0
    assert result["metrics"]["stage0_safe_read_recall"] == 1.0
    assert "risky_detector" in result["calibration"]


def test_binary_stage0_eval_refuses_holdout_gate():
    with pytest.raises(ValueError, match="Unsupported binary Stage 0 eval gate"):
        binary_eval.cases_for_gate("router_holdout_1000_v3")


def test_route_specific_stage0_emits_g04_only_from_route_detector_and_chooses_hint():
    artifacts = route_specific_artifacts({"R08": [0.96, 0.04], "R07": [0.97, 0.03]})
    safe_read = binary_artifact(
        "safe_read_binary",
        TextProbabilityClassifier(["allow", "block"], {}, [0.05, 0.95]),
    )
    fallback = stage0_artifact(TextProbabilityClassifier(["G00", "G02"], {}, [0.95, 0.05]))

    result = binary_eval.evaluate_route_specific_stage0(
        route_artifacts=artifacts,
        safe_read_artifact=safe_read,
        fallback_artifact=fallback,
        cases=[case("run", "R08 R07", "console.run_command")],
        route_encoders={code: TextEncoder() for code in artifacts},
        safe_read_encoder=TextEncoder(),
        fallback_encoder=TextEncoder(),
    )

    row = result["rows"][0]
    assert row["stage0_gate"] == "G04"
    assert row["stage0_candidate_risky_code"] == "R07"
    assert result["metrics"]["combined_stage0_false_risky_actions"] == 0


def test_strict_hint_consistency_falls_back_to_clarification_on_risky_disagreement():
    artifacts = route_specific_artifacts({"R08": [0.96, 0.04]})
    safe_read = binary_artifact(
        "safe_read_binary",
        TextProbabilityClassifier(["allow", "block"], {}, [0.05, 0.95]),
    )
    fallback = stage0_artifact(TextProbabilityClassifier(["G00", "G02"], {}, [0.95, 0.05]))
    risky_subtype = subtype_artifact(
        "stage1b",
        TextProbabilityClassifier(["R07", "R08"], {}, [0.99, 0.01]),
        ["R07", "R08"],
    )

    result = binary_eval.evaluate_route_specific_stage0(
        route_artifacts=artifacts,
        safe_read_artifact=safe_read,
        fallback_artifact=fallback,
        cases=[case("run", "R08 request", "console.run_command")],
        route_encoders={code: TextEncoder() for code in artifacts},
        safe_read_encoder=TextEncoder(),
        fallback_encoder=TextEncoder(),
        risky_subtype_artifact=risky_subtype,
        risky_subtype_encoder=TextEncoder(),
        hint_consistency_mode="strict_hint_consistency",
    )

    row = result["rows"][0]
    assert row["stage0_candidate_risky_code"] == "R08"
    assert row["actual_route"] == "ask_clarifying_question"
    assert row["fallback_reason"] == "strict_hint_consistency_mismatch"
    assert result["metrics"]["false_direct_actions_total"] == 0


def test_route_specific_sweep_ranking_rejects_combined_false_risky_actions():
    safe = {
        "metrics": {
            "combined_stage0_false_risky_actions": 0,
            "false_direct_actions_total": 0,
            "combined_stage0_risky_recall": 0.4,
            "final_direct_action_recall": 0.4,
            "ambiguous_to_clarification_rate": 1.0,
            "semantic_route_accuracy": 0.5,
        }
    }
    unsafe = {
        "metrics": {
            "combined_stage0_false_risky_actions": 1,
            "false_direct_actions_total": 1,
            "combined_stage0_risky_recall": 1.0,
            "final_direct_action_recall": 1.0,
            "ambiguous_to_clarification_rate": 1.0,
            "semantic_route_accuracy": 1.0,
        }
    }

    assert binary_eval.rank_route_specific_sweep_results([unsafe, safe])[0] is safe
