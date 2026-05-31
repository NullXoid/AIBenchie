from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from training import router_embedding_classifier as classifier


class PrefixEncoder:
    def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
        rows = []
        for text in texts:
            code = str(text).split()[0]
            index = int(code[1:]) if code.startswith("R") and code[1:].isdigit() else 0
            row = np.zeros(len(classifier.ROUTE_CODES), dtype=float)
            row[index] = 1.0
            rows.append(row)
        return np.array(rows)


class FixedProbabilityClassifier:
    def __init__(self, classes, probabilities):
        self.classes_ = np.array(classes)
        self._probabilities = np.array([probabilities], dtype=float)

    def predict_proba(self, _embedding):
        return self._probabilities


def artifact_for(mode: str, models: dict, thresholds=None) -> dict:
    return {
        "artifact_type": "embedding_classifier_router",
        "version": 1,
        "metadata": {
            "embedding_model": "fake/encoder",
            "classifier_type": "logistic_regression",
            "routing_mode": mode,
            "context_mode": "text_only",
            "thresholds": (thresholds or classifier.ClassifierThresholds()).to_dict(),
            "class_labels": ["R00", "R01", "R02", "R08"],
            "route_codes": dict(classifier.ROUTE_CODES),
            "risky_route_codes": sorted(classifier.RISKY_ROUTE_CODES),
            "safe_stage_codes": sorted(classifier.SAFE_STAGE_CODES),
            "train_data_hash": "abc",
            "train_count": 4,
        },
        "models": models,
    }


def test_extract_sft_route_records_reads_user_text_and_route_code(tmp_path: Path):
    path = tmp_path / "train.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "one",
                "messages": [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "Run tests now."},
                    {"role": "assistant", "content": "R08"},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    records = classifier.extract_sft_route_records(path)

    assert records == [
        {
            "id": "one",
            "text": "Run tests now.",
            "code": "R08",
            "route": "console.run_command",
        }
    ]
    assert len(classifier.train_data_hash(records)) == 64


def test_train_embedding_classifier_artifact_metadata_and_labels():
    records = []
    for code in classifier.ROUTE_CODES:
        for index in range(2):
            records.append(
                {
                    "id": f"{code}_{index}",
                    "text": f"{code} example {index}",
                    "code": code,
                    "route": classifier.route_for_code(code),
                }
            )
    config = classifier.RouterClassifierConfig(embedding_model="fake/encoder")

    artifact = classifier.train_embedding_classifier(records, config, encoder=PrefixEncoder())

    assert artifact["artifact_type"] == "embedding_classifier_router"
    assert artifact["metadata"]["embedding_model"] == "fake/encoder"
    assert artifact["metadata"]["routing_mode"] == "flat_15_class"
    assert artifact["metadata"]["context_mode"] == "text_only"
    assert artifact["metadata"]["thresholds"]["risky_confidence"] == 0.95
    assert set(artifact["metadata"]["class_labels"]) == set(classifier.ROUTE_CODES)


def test_train_hybrid_stage0_artifact_metadata_and_hashes():
    records = []
    for code in classifier.ROUTE_CODES:
        for index in range(2):
            records.append(
                {
                    "id": f"{code}_{index}",
                    "text": f"{code} example {index}",
                    "code": code,
                    "route": classifier.route_for_code(code),
                    "template_family": f"family_{code}",
                }
            )
    config = classifier.HybridClassifierConfig(
        embedding_model="fake/encoder",
        classifier_type="logistic_regression",
        hybrid_component="stage0",
        template_family_split_id="split_v1",
        stage0_thresholds={"G04": {"confidence": 0.9, "margin": 0.1}},
    )

    artifact = classifier.train_hybrid_classifier(records, config, encoder=PrefixEncoder(), dev_records=records[:4])

    assert artifact["artifact_type"] == "hybrid_embedding_classifier_router"
    assert artifact["metadata"]["routing_mode"] == "hybrid"
    assert artifact["metadata"]["hybrid_component"] == "stage0"
    assert artifact["metadata"]["template_family_split_id"] == "split_v1"
    assert artifact["metadata"]["stage0_thresholds"]["G04"]["confidence"] == 0.9
    assert artifact["metadata"]["train_hash"] == artifact["metadata"]["train_data_hash"]
    assert artifact["metadata"]["dev_hash"] == classifier.train_data_hash(records[:4])
    assert set(artifact["metadata"]["class_labels"]) == set(classifier.HYBRID_STAGE0_LABELS)


def test_train_hybrid_subtype_artifact_filters_to_allowed_labels():
    records = []
    for code in classifier.ROUTE_CODES:
        for index in range(2):
            records.append(
                {
                    "id": f"{code}_{index}",
                    "text": f"{code} example {index}",
                    "code": code,
                    "route": classifier.route_for_code(code),
                }
            )

    stage1a = classifier.train_hybrid_classifier(
        records,
        classifier.HybridClassifierConfig(
            embedding_model="fake/encoder",
            classifier_type="logistic_regression",
            hybrid_component="stage1a",
        ),
        encoder=PrefixEncoder(),
    )
    stage1b = classifier.train_hybrid_classifier(
        records,
        classifier.HybridClassifierConfig(
            embedding_model="fake/encoder",
            classifier_type="logistic_regression",
            hybrid_component="stage1b",
        ),
        encoder=PrefixEncoder(),
    )

    assert set(stage1a["metadata"]["class_labels"]) == classifier.SAFE_READ_ROUTE_CODES
    assert set(stage1b["metadata"]["class_labels"]) == classifier.RISKY_ROUTE_CODES


def test_train_binary_detector_artifact_metadata_and_thresholds():
    records = []
    for code in classifier.ROUTE_CODES:
        for index in range(2):
            records.append(
                {
                    "id": f"{code}_{index}",
                    "text": f"{code} example {index}",
                    "code": code,
                    "route": classifier.route_for_code(code),
                }
            )
    config = classifier.BinaryDetectorConfig(
        embedding_model="fake/encoder",
        classifier_type="logistic_regression",
        detector_role="risky_action_binary",
        confidence_threshold=0.91,
        margin_threshold=0.12,
        template_family_split_id="split_v1",
        calibration_summary={"confidence_buckets": {}},
    )

    artifact = classifier.train_binary_detector(records, config, encoder=PrefixEncoder(), dev_records=records[:4])

    assert artifact["artifact_type"] == "hybrid_binary_detector"
    assert artifact["metadata"]["detector_role"] == "risky_action_binary"
    assert artifact["metadata"]["detector_thresholds"]["allow"] == {"confidence": 0.91, "margin": 0.12}
    assert set(artifact["metadata"]["positive_route_codes"]) == classifier.RISKY_ROUTE_CODES
    assert artifact["metadata"]["template_family_split_id"] == "split_v1"
    assert artifact["metadata"]["dev_hash"] == classifier.train_data_hash(records[:4])
    assert "confidence_buckets" in artifact["metadata"]["calibration_summary"]


def test_route_specific_binary_detector_requires_valid_risky_target():
    with pytest.raises(ValueError, match="target_route_code"):
        classifier.BinaryDetectorConfig(detector_role=classifier.ROUTE_SPECIFIC_RISKY_DETECTOR)

    with pytest.raises(ValueError, match="target_route_code"):
        classifier.BinaryDetectorConfig(
            detector_role=classifier.ROUTE_SPECIFIC_RISKY_DETECTOR,
            target_route_code="R12",
        )

    config = classifier.BinaryDetectorConfig(
        detector_role=classifier.ROUTE_SPECIFIC_RISKY_DETECTOR,
        target_route_code="R08",
    )

    assert classifier.binary_positive_codes(config.detector_role, config.target_route_code) == {"R08"}


def test_train_route_specific_binary_detector_records_target_metadata():
    records = []
    for code in classifier.ROUTE_CODES:
        records.append(
            {
                "id": code,
                "text": f"{code} example",
                "code": code,
                "route": classifier.route_for_code(code),
            }
        )

    artifact = classifier.train_binary_detector(
        records,
        classifier.BinaryDetectorConfig(
            embedding_model="fake/encoder",
            classifier_type="logistic_regression",
            detector_role=classifier.ROUTE_SPECIFIC_RISKY_DETECTOR,
            target_route_code="R08",
        ),
        encoder=PrefixEncoder(),
    )

    assert artifact["metadata"]["detector_role"] == classifier.ROUTE_SPECIFIC_RISKY_DETECTOR
    assert artifact["metadata"]["target_route_code"] == "R08"
    assert artifact["metadata"]["target_route"] == "console.run_command"
    assert artifact["metadata"]["positive_route_codes"] == ["R08"]


def test_predict_hybrid_label_returns_gate_or_route_label():
    stage0_artifact = {
        "artifact_type": "hybrid_embedding_classifier_router",
        "version": 1,
        "metadata": {
            "embedding_model": "fake/encoder",
            "classifier_type": "logistic_regression",
            "routing_mode": "hybrid",
            "hybrid_component": "stage0",
            "context_mode": "text_only",
            "thresholds": classifier.ClassifierThresholds().to_dict(),
            "class_labels": ["G04", "G01"],
            "train_data_hash": "abc",
            "train_count": 2,
        },
        "models": {"classifier": FixedProbabilityClassifier(["G04", "G01"], [0.90, 0.10])},
    }
    stage1b_artifact = {
        "artifact_type": "hybrid_embedding_classifier_router",
        "version": 1,
        "metadata": {
            "embedding_model": "fake/encoder",
            "classifier_type": "logistic_regression",
            "routing_mode": "hybrid",
            "hybrid_component": "stage1b",
            "context_mode": "text_only",
            "thresholds": classifier.ClassifierThresholds(
                per_route={"R08": classifier.RouteThreshold(confidence=0.80, margin=0.05)}
            ).to_dict(),
            "class_labels": ["R08", "R07"],
            "train_data_hash": "abc",
            "train_count": 2,
        },
        "models": {"classifier": FixedProbabilityClassifier(["R08", "R07"], [0.90, 0.10])},
    }

    stage0_prediction = classifier.predict_hybrid_label(stage0_artifact, "anything", encoder=PrefixEncoder())
    stage1b_prediction = classifier.predict_hybrid_label(stage1b_artifact, "anything", encoder=PrefixEncoder())

    assert stage0_prediction.code == "G04"
    assert stage0_prediction.raw_code == "G04"
    assert stage1b_prediction.code == "R08"
    assert stage1b_prediction.raw_code == "R08"


def test_predict_hybrid_stage0_applies_saved_gate_thresholds():
    artifact = {
        "artifact_type": "hybrid_embedding_classifier_router",
        "version": 1,
        "metadata": {
            "embedding_model": "fake/encoder",
            "classifier_type": "logistic_regression",
            "routing_mode": "hybrid",
            "hybrid_component": "stage0",
            "context_mode": "text_only",
            "thresholds": classifier.ClassifierThresholds().to_dict(),
            "stage0_thresholds": {"G04": {"confidence": 0.95, "margin": 0.20}},
            "class_labels": ["G04", "G01"],
            "train_data_hash": "abc",
            "train_count": 2,
        },
        "models": {"classifier": FixedProbabilityClassifier(["G04", "G01"], [0.90, 0.10])},
    }

    prediction = classifier.predict_hybrid_label(artifact, "anything", encoder=PrefixEncoder())

    assert prediction.code == "G02"
    assert prediction.raw_code == "G04"
    assert prediction.guarded is True
    assert prediction.abstention_reason == "stage0_confidence_below_threshold"


def test_binary_detector_policy_blocks_g04_unless_risky_detector_passes():
    blocked_risky = classifier.RouterPrediction(
        "block",
        0.94,
        0.30,
        "allow",
        True,
        "hybrid_binary",
        "risky_action_binary",
        0.95,
        0.0,
        "binary_confidence_below_threshold",
    )
    allowed_risky = classifier.RouterPrediction("allow", 0.96, 0.30, "allow", False, "hybrid_binary")
    allowed_safe_read = classifier.RouterPrediction("allow", 0.96, 0.30, "allow", False, "hybrid_binary")

    assert classifier.combined_binary_stage0_gate(
        risky_prediction=blocked_risky,
        safe_read_prediction=allowed_safe_read,
        fallback_gate="G00",
    ) == "G03"
    assert classifier.combined_binary_stage0_gate(
        risky_prediction=allowed_risky,
        safe_read_prediction=allowed_safe_read,
        fallback_gate="G00",
    ) == "G04"


def test_calibration_buckets_report_precision_and_recall():
    buckets = classifier.calibration_buckets(
        [
            {"confidence": 0.95, "predicted_label": "allow", "actual_positive": True},
            {"confidence": 0.92, "predicted_label": "allow", "actual_positive": False},
            {"confidence": 0.45, "predicted_label": "block", "actual_positive": True},
        ]
    )
    high = next(bucket for bucket in buckets if bucket["bucket_min"] == 0.9)

    assert high["predicted_positive"] == 2
    assert high["true_positive"] == 1
    assert high["precision"] == 0.5


def test_risky_threshold_guard_downgrades_low_confidence_or_margin_to_clarification():
    thresholds = classifier.ClassifierThresholds(risky_confidence=0.95, risky_margin=0.20, per_route={})

    assert classifier.apply_threshold_guard("R08", 0.94, 0.50, thresholds) == ("R02", True)
    assert classifier.apply_threshold_guard("R08", 0.96, 0.10, thresholds) == ("R02", True)
    assert classifier.apply_threshold_guard("R08", 0.96, 0.25, thresholds) == ("R08", False)


def test_low_confidence_non_risky_prediction_becomes_clarification():
    thresholds = classifier.ClassifierThresholds(non_risky_confidence=0.50, per_route={})

    assert classifier.apply_threshold_guard("R01", 0.49, 0.40, thresholds) == ("R02", True)
    assert classifier.apply_threshold_guard("R01", 0.50, 0.00, thresholds) == ("R01", False)


def test_per_route_threshold_overrides_global_threshold_and_records_reason():
    thresholds = classifier.ClassifierThresholds(
        risky_confidence=0.95,
        risky_margin=0.20,
        per_route={"R08": classifier.RouteThreshold(confidence=0.90, margin=0.15)},
    )

    accepted = classifier.threshold_decision("R08", 0.91, 0.16, thresholds)
    rejected = classifier.threshold_decision("R08", 0.89, 0.16, thresholds)

    assert accepted == ("R08", False, 0.90, 0.15, None)
    assert rejected == ("R02", True, 0.90, 0.15, "risky_confidence_below_threshold")


def test_safe_read_route_threshold_uses_margin():
    thresholds = classifier.ClassifierThresholds(
        non_risky_confidence=0.35,
        per_route={"R12": classifier.RouteThreshold(confidence=0.65, margin=0.08)},
    )

    assert classifier.threshold_decision("R12", 0.70, 0.04, thresholds) == (
        "R02",
        True,
        0.65,
        0.08,
        "route_margin_below_threshold",
    )


def test_context_flags_v1_formats_deterministic_metadata_without_inference():
    formatted = classifier.format_classifier_text(
        "Apply that.",
        context_mode="context_flags_v1",
        context_flags={"HAS_IMAGE": True, "ACTIVE_FILE": False, "LAST_ASSISTANT_OFFERED_PATCH": "unknown"},
    )

    assert formatted.startswith(
        "[HAS_IMAGE=true] [ACTIVE_FILE=false] [LAST_ASSISTANT_OFFERED_PATCH=unknown] "
        "[USER_CONFIRMED_PREVIOUS_ACTION=unknown] [LAST_ASSISTANT_ASKED_CONFIRMATION=unknown]"
    )
    assert formatted.endswith("User: Apply that.")


def test_context_flag_normalization_rejects_unknown_values():
    assert classifier.normalize_context_flag_value(True) == "true"
    assert classifier.normalize_context_flag_value(False) == "false"
    assert classifier.normalize_context_flag_value(None) == "unknown"
    assert classifier.normalize_context_flag_value("yes") == "true"
    assert classifier.normalize_context_flag_value("missing") == "unknown"
    try:
        classifier.normalize_context_flag_value("sometimes")
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported context flag value should raise")


def test_flat_classifier_prediction_returns_exact_route_code():
    artifact = artifact_for(
        "flat_15_class",
        {"flat": FixedProbabilityClassifier(["R08", "R01"], [0.97, 0.03])},
    )

    prediction = classifier.predict_route_code(artifact, "anything", encoder=PrefixEncoder())

    assert prediction.code == "R08"
    assert prediction.raw_code == "R08"
    assert prediction.guarded is False
    assert prediction.required_confidence == 0.90
    assert prediction.required_margin == 0.15
    assert prediction.abstention_reason is None


def test_two_stage_classifier_uses_safe_stage_before_action_subtype():
    safe_artifact = artifact_for(
        "two_stage",
        {
            "stage1": FixedProbabilityClassifier([classifier.ACTION_STAGE_LABEL, "R00"], [0.04, 0.96]),
            "stage2": FixedProbabilityClassifier(["R07", "R08"], [0.96, 0.04]),
        },
    )
    action_artifact = artifact_for(
        "two_stage",
        {
            "stage1": FixedProbabilityClassifier([classifier.ACTION_STAGE_LABEL, "R00"], [0.99, 0.01]),
            "stage2": FixedProbabilityClassifier(["R07", "R08"], [0.97, 0.03]),
        },
    )

    assert classifier.predict_route_code(safe_artifact, "anything", encoder=PrefixEncoder()).code == "R00"
    assert classifier.predict_route_code(action_artifact, "anything", encoder=PrefixEncoder()).code == "R07"


def test_three_stage_routes_safe_read_and_blocks_unconfident_risky_action():
    safe_read_artifact = artifact_for(
        "three_stage",
        {
            "stage1": FixedProbabilityClassifier(
                [
                    classifier.THREE_STAGE_SAFE_READ,
                    classifier.THREE_STAGE_RISKY,
                ],
                [0.96, 0.04],
            ),
            "safe_read": FixedProbabilityClassifier(["R12", "R11"], [0.90, 0.10]),
            "risky": FixedProbabilityClassifier(["R08", "R07"], [0.99, 0.01]),
        },
    )
    blocked_risky_artifact = artifact_for(
        "three_stage",
        {
            "stage1": FixedProbabilityClassifier(
                [
                    classifier.THREE_STAGE_RISKY,
                    classifier.THREE_STAGE_SAFE_READ,
                ],
                [0.80, 0.20],
            ),
            "safe_read": FixedProbabilityClassifier(["R12", "R11"], [0.90, 0.10]),
            "risky": FixedProbabilityClassifier(["R08", "R07"], [0.99, 0.01]),
        },
    )

    safe_read = classifier.predict_route_code(safe_read_artifact, "anything", encoder=PrefixEncoder())
    blocked = classifier.predict_route_code(blocked_risky_artifact, "anything", encoder=PrefixEncoder())

    assert safe_read.code == "R12"
    assert safe_read.stage1_label == classifier.THREE_STAGE_SAFE_READ
    assert blocked.code == "R02"
    assert blocked.raw_code == classifier.THREE_STAGE_RISKY
    assert blocked.abstention_reason == "stage1_blocks_risky_action"
