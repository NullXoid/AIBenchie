from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


ALLOWED_ROUTES = (
    "chat.no_action",
    "answer.question",
    "ask_clarifying_question",
    "vision.describe_image",
    "vision.ocr_image",
    "vision.edit_image",
    "console.open_ui",
    "console.edit_file",
    "console.run_command",
    "agent.preview_plan",
    "agent.start_job",
    "web.lookup",
    "file.search",
    "memory.save_preference",
    "safety.refuse",
)
ROUTE_CODES = {f"R{index:02d}": route for index, route in enumerate(ALLOWED_ROUTES)}
ROUTE_TO_CODE = {route: code for code, route in ROUTE_CODES.items()}
SAFE_STAGE_CODES = {"R00", "R01", "R02", "R09", "R14"}
SAFE_READ_ROUTE_CODES = {"R03", "R04", "R06", "R11", "R12"}
RISKY_ROUTE_CODES = {"R05", "R07", "R08", "R10", "R13"}
HYBRID_STAGE0_LABELS = ("G00", "G01", "G02", "G03", "G04")
HYBRID_STAGE0_LABEL_TO_NAME = {
    "G00": "non_action_family",
    "G01": "answer_question",
    "G02": "ask_clarifying_question",
    "G03": "safe_read_lookup",
    "G04": "risky_action_candidate",
}
HYBRID_ROUTE_CODE_TO_STAGE0 = {
    "R00": "G00",
    "R09": "G00",
    "R14": "G00",
    "R01": "G01",
    "R02": "G02",
    "R03": "G03",
    "R04": "G03",
    "R06": "G03",
    "R11": "G03",
    "R12": "G03",
    "R05": "G04",
    "R07": "G04",
    "R08": "G04",
    "R10": "G04",
    "R13": "G04",
}
HYBRID_COMPONENT_LABELS = {
    "stage0": set(HYBRID_STAGE0_LABELS),
    "stage1c": SAFE_STAGE_CODES,
    "stage1a": SAFE_READ_ROUTE_CODES,
    "stage1b": RISKY_ROUTE_CODES,
}
ACTION_STAGE_LABEL = "__ACTION_REQUESTED__"
THREE_STAGE_NON_ACTION = "non_action"
THREE_STAGE_ANSWER = "answer_question"
THREE_STAGE_CLARIFY = "ask_clarification"
THREE_STAGE_SAFE_READ = "safe_read_lookup"
THREE_STAGE_RISKY = "risky_action"
THREE_STAGE_SAFE_LABEL_TO_CODE = {
    THREE_STAGE_NON_ACTION: "R00",
    THREE_STAGE_ANSWER: "R01",
    THREE_STAGE_CLARIFY: "R02",
}
SUPPORTED_ROUTING_MODES = {"flat_15_class", "two_stage", "three_stage"}
SUPPORTED_HYBRID_COMPONENTS = {"stage0", "stage1a", "stage1b", "stage1c"}
ROUTE_SPECIFIC_RISKY_DETECTOR = "route_specific_risky"
SUPPORTED_BINARY_DETECTORS = {"risky_action_binary", "safe_read_binary", ROUTE_SPECIFIC_RISKY_DETECTOR}
POSITIVE_BINARY_LABEL = "allow"
NEGATIVE_BINARY_LABEL = "block"
SUPPORTED_CLASSIFIERS = {"logistic_regression", "linear_svc_calibrated"}
SUPPORTED_CONTEXT_MODES = {"text_only", "context_flags_v1"}
CONTEXT_FLAGS_V1 = (
    "HAS_IMAGE",
    "ACTIVE_FILE",
    "LAST_ASSISTANT_OFFERED_PATCH",
    "USER_CONFIRMED_PREVIOUS_ACTION",
    "LAST_ASSISTANT_ASKED_CONFIRMATION",
)
CONTEXT_FLAG_VALUES = {"true", "false", "unknown"}
DEFAULT_TRAIN_JSONL = Path("data/router_direct_action_boundaries_v2/router_lora_train_v2.jsonl")
DEFAULT_OUTPUT_DIR = Path("models/classifiers")


@dataclass(frozen=True)
class RouteThreshold:
    confidence: float
    margin: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def default_per_route_thresholds() -> dict[str, RouteThreshold]:
    return {
        "R03": RouteThreshold(confidence=0.60, margin=0.05),
        "R04": RouteThreshold(confidence=0.60, margin=0.05),
        "R11": RouteThreshold(confidence=0.65, margin=0.08),
        "R12": RouteThreshold(confidence=0.65, margin=0.08),
        "R08": RouteThreshold(confidence=0.90, margin=0.15),
        "R07": RouteThreshold(confidence=0.88, margin=0.12),
        "R05": RouteThreshold(confidence=0.90, margin=0.15),
        "R10": RouteThreshold(confidence=0.92, margin=0.18),
        "R13": RouteThreshold(confidence=0.95, margin=0.20),
    }


@dataclass(frozen=True)
class ClassifierThresholds:
    risky_confidence: float = 0.95
    risky_margin: float = 0.20
    non_risky_confidence: float = 0.50
    per_route: dict[str, RouteThreshold] = field(default_factory=default_per_route_thresholds)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ClassifierThresholds":
        per_route_payload = payload.get("per_route") or {}
        per_route = {
            str(code): RouteThreshold(
                confidence=float(values["confidence"]),
                margin=float(values.get("margin", 0.0)),
            )
            for code, values in per_route_payload.items()
        }
        return cls(
            risky_confidence=float(payload.get("risky_confidence", 0.95)),
            risky_margin=float(payload.get("risky_margin", 0.20)),
            non_risky_confidence=float(payload.get("non_risky_confidence", 0.50)),
            per_route=per_route,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "risky_confidence": self.risky_confidence,
            "risky_margin": self.risky_margin,
            "non_risky_confidence": self.non_risky_confidence,
            "per_route": {code: threshold.to_dict() for code, threshold in self.per_route.items()},
        }


@dataclass(frozen=True)
class RouterClassifierConfig:
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    classifier_type: str = "logistic_regression"
    routing_mode: str = "flat_15_class"
    context_mode: str = "text_only"
    thresholds: ClassifierThresholds = field(default_factory=ClassifierThresholds)
    random_state: int = 42

    def __post_init__(self) -> None:
        if self.routing_mode not in SUPPORTED_ROUTING_MODES:
            raise ValueError(f"Unsupported routing mode: {self.routing_mode}")
        if self.classifier_type not in SUPPORTED_CLASSIFIERS:
            raise ValueError(f"Unsupported classifier_type: {self.classifier_type}")
        if self.context_mode not in SUPPORTED_CONTEXT_MODES:
            raise ValueError(f"Unsupported context_mode: {self.context_mode}")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["thresholds"] = self.thresholds.to_dict()
        return payload


@dataclass(frozen=True)
class HybridClassifierConfig:
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    classifier_type: str = "logistic_regression"
    hybrid_component: str = "stage0"
    context_mode: str = "text_only"
    thresholds: ClassifierThresholds = field(default_factory=ClassifierThresholds)
    random_state: int = 42
    template_family_split_id: str = "unspecified"
    dev_hash: str | None = None
    stage0_thresholds: dict[str, Any] = field(default_factory=dict)
    stage1a_thresholds: dict[str, Any] = field(default_factory=dict)
    stage1b_thresholds: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.hybrid_component not in SUPPORTED_HYBRID_COMPONENTS:
            raise ValueError(f"Unsupported hybrid_component: {self.hybrid_component}")
        if self.classifier_type not in SUPPORTED_CLASSIFIERS:
            raise ValueError(f"Unsupported classifier_type: {self.classifier_type}")
        if self.context_mode not in SUPPORTED_CONTEXT_MODES:
            raise ValueError(f"Unsupported context_mode: {self.context_mode}")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["thresholds"] = self.thresholds.to_dict()
        return payload


@dataclass(frozen=True)
class BinaryDetectorConfig:
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    classifier_type: str = "logistic_regression"
    detector_role: str = "risky_action_binary"
    target_route_code: str | None = None
    context_mode: str = "text_only"
    confidence_threshold: float = 0.95
    margin_threshold: float = 0.0
    random_state: int = 42
    template_family_split_id: str = "unspecified"
    dev_hash: str | None = None
    calibration_summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.detector_role not in SUPPORTED_BINARY_DETECTORS:
            raise ValueError(f"Unsupported detector_role: {self.detector_role}")
        if self.detector_role == ROUTE_SPECIFIC_RISKY_DETECTOR:
            if self.target_route_code not in RISKY_ROUTE_CODES:
                raise ValueError(
                    "route_specific_risky detector requires target_route_code in "
                    f"{sorted(RISKY_ROUTE_CODES)}"
                )
        elif self.target_route_code is not None:
            raise ValueError("target_route_code is only supported for route_specific_risky detectors")
        if self.classifier_type not in SUPPORTED_CLASSIFIERS:
            raise ValueError(f"Unsupported classifier_type: {self.classifier_type}")
        if self.context_mode not in SUPPORTED_CONTEXT_MODES:
            raise ValueError(f"Unsupported context_mode: {self.context_mode}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RouterPrediction:
    code: str
    confidence: float
    margin: float
    raw_code: str
    guarded: bool
    routing_mode: str
    stage1_label: str | None = None
    required_confidence: float = 0.0
    required_margin: float = 0.0
    abstention_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def route_code_for_route(route: str) -> str:
    if route not in ROUTE_TO_CODE:
        raise ValueError(f"Unsupported route: {route}")
    return ROUTE_TO_CODE[route]


def route_for_code(code: str) -> str:
    if code not in ROUTE_CODES:
        raise ValueError(f"Unsupported route code: {code}")
    return ROUTE_CODES[code]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def extract_sft_route_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for record in read_jsonl(path):
        if record.get("text") and record.get("code") in ROUTE_CODES:
            extracted = {
                "id": str(record.get("id") or f"record_{len(records) + 1}"),
                "text": str(record["text"]),
                "code": str(record["code"]),
                "route": ROUTE_CODES[str(record["code"])],
            }
            for key in (
                "context_flags",
                "required_context_flags",
                "template_family",
                "source",
                "training_role",
                "must_not_emit_g04",
            ):
                if key in record:
                    extracted[key] = record[key]
            records.append(extracted)
            continue
        messages = record.get("messages") or []
        user_text = ""
        assistant_text = ""
        for message in messages:
            if message.get("role") == "user":
                user_text = str(message.get("content") or "")
            elif message.get("role") == "assistant":
                assistant_text = str(message.get("content") or "").strip()
        if not user_text or assistant_text not in ROUTE_CODES:
            continue
        extracted: dict[str, Any] = {
            "id": str(record.get("id") or record.get("scenario_id") or f"record_{len(records) + 1}"),
            "text": user_text,
            "code": assistant_text,
            "route": ROUTE_CODES[assistant_text],
        }
        context_flags = record.get("context_flags") or (record.get("metadata") or {}).get("context_flags")
        if isinstance(context_flags, dict):
            extracted["context_flags"] = dict(context_flags)
        if record.get("template_family"):
            extracted["template_family"] = str(record["template_family"])
        if record.get("required_context_flags"):
            extracted["required_context_flags"] = list(record["required_context_flags"])
        records.append(extracted)
    if not records:
        raise ValueError(f"No route-code SFT records found in {path}")
    return records


def train_data_hash(records: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(json.dumps(record, sort_keys=True, ensure_ascii=True).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def format_classifier_text(
    text: str,
    *,
    context_mode: str = "text_only",
    context_flags: dict[str, Any] | None = None,
) -> str:
    if context_mode == "text_only":
        return text
    if context_mode != "context_flags_v1":
        raise ValueError(f"Unsupported context_mode: {context_mode}")
    flags = context_flags or {}
    tokens = []
    for flag in CONTEXT_FLAGS_V1:
        value = normalize_context_flag_value(flags.get(flag, "unknown"))
        tokens.append(f"[{flag}={value}]")
    return f"{' '.join(tokens)}\nUser: {text}"


def normalize_context_flag_value(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip().lower()
    if text in {"1", "yes", "y", "true"}:
        return "true"
    if text in {"0", "no", "n", "false"}:
        return "false"
    if text in {"unknown", "unk", "missing", ""}:
        return "unknown"
    raise ValueError(f"Unsupported context flag value: {value!r}")


def encode_texts(encoder: Any, texts: list[str]) -> Any:
    return encoder.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def _fit_classifier(classifier_type: str, random_state: int, x_train: Any, y_train: list[str]) -> Any:
    if classifier_type == "logistic_regression":
        from sklearn.linear_model import LogisticRegression

        classifier = LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=random_state,
        )
        return classifier.fit(x_train, y_train)
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.svm import LinearSVC

    base = LinearSVC(class_weight="balanced", random_state=random_state)
    classifier = CalibratedClassifierCV(base, cv=3)
    return classifier.fit(x_train, y_train)


def _stage1_label(code: str) -> str:
    return code if code in SAFE_STAGE_CODES else ACTION_STAGE_LABEL


def _three_stage_label(code: str) -> str:
    if code in {"R00", "R09", "R14"}:
        return THREE_STAGE_NON_ACTION
    if code == "R01":
        return THREE_STAGE_ANSWER
    if code == "R02":
        return THREE_STAGE_CLARIFY
    if code in SAFE_READ_ROUTE_CODES:
        return THREE_STAGE_SAFE_READ
    if code in RISKY_ROUTE_CODES:
        return THREE_STAGE_RISKY
    raise ValueError(f"Unsupported route code for three_stage: {code}")


def _record_texts(records: list[dict[str, Any]], config: RouterClassifierConfig) -> list[str]:
    return [
        format_classifier_text(
            str(record["text"]),
            context_mode=config.context_mode,
            context_flags=record.get("context_flags"),
        )
        for record in records
    ]


def train_embedding_classifier(
    records: list[dict[str, Any]],
    config: RouterClassifierConfig,
    *,
    encoder: Any | None = None,
) -> dict[str, Any]:
    if encoder is None:
        from sentence_transformers import SentenceTransformer

        encoder = SentenceTransformer(config.embedding_model)
    texts = _record_texts(records, config)
    x_train = encode_texts(encoder, texts)
    codes = [record["code"] for record in records]
    if config.routing_mode == "flat_15_class":
        classifier = _fit_classifier(config.classifier_type, config.random_state, x_train, codes)
        class_labels = list(classifier.classes_)
        models = {"flat": classifier}
    elif config.routing_mode == "two_stage":
        stage1_labels = [_stage1_label(code) for code in codes]
        stage1_classifier = _fit_classifier(config.classifier_type, config.random_state, x_train, stage1_labels)
        action_indexes = [index for index, code in enumerate(codes) if code not in SAFE_STAGE_CODES]
        if not action_indexes:
            raise ValueError("two_stage classifier requires action-route training records")
        action_texts = [texts[index] for index in action_indexes]
        action_codes = [codes[index] for index in action_indexes]
        action_x = encode_texts(encoder, action_texts)
        stage2_classifier = _fit_classifier(config.classifier_type, config.random_state, action_x, action_codes)
        class_labels = sorted(set(stage1_classifier.classes_) | set(stage2_classifier.classes_))
        models = {"stage1": stage1_classifier, "stage2": stage2_classifier}
    else:
        stage1_labels = [_three_stage_label(code) for code in codes]
        stage1_classifier = _fit_classifier(config.classifier_type, config.random_state, x_train, stage1_labels)
        safe_read_indexes = [index for index, code in enumerate(codes) if code in SAFE_READ_ROUTE_CODES]
        risky_indexes = [index for index, code in enumerate(codes) if code in RISKY_ROUTE_CODES]
        if not safe_read_indexes:
            raise ValueError("three_stage classifier requires safe read/lookup training records")
        if not risky_indexes:
            raise ValueError("three_stage classifier requires risky-route training records")
        safe_read_texts = [texts[index] for index in safe_read_indexes]
        safe_read_codes = [codes[index] for index in safe_read_indexes]
        risky_texts = [texts[index] for index in risky_indexes]
        risky_codes = [codes[index] for index in risky_indexes]
        safe_read_classifier = _fit_classifier(
            config.classifier_type,
            config.random_state,
            encode_texts(encoder, safe_read_texts),
            safe_read_codes,
        )
        risky_classifier = _fit_classifier(
            config.classifier_type,
            config.random_state,
            encode_texts(encoder, risky_texts),
            risky_codes,
        )
        class_labels = sorted(
            set(stage1_classifier.classes_) | set(safe_read_classifier.classes_) | set(risky_classifier.classes_)
        )
        models = {"stage1": stage1_classifier, "safe_read": safe_read_classifier, "risky": risky_classifier}
    return {
        "artifact_type": "embedding_classifier_router",
        "version": 1,
        "metadata": {
            "embedding_model": config.embedding_model,
            "classifier_type": config.classifier_type,
            "routing_mode": config.routing_mode,
            "context_mode": config.context_mode,
            "thresholds": config.thresholds.to_dict(),
            "class_labels": class_labels,
            "route_codes": dict(ROUTE_CODES),
            "risky_route_codes": sorted(RISKY_ROUTE_CODES),
            "safe_read_route_codes": sorted(SAFE_READ_ROUTE_CODES),
            "safe_stage_codes": sorted(SAFE_STAGE_CODES),
            "train_data_hash": train_data_hash(records),
            "train_count": len(records),
            "created_at_unix": int(time.time()),
        },
        "models": models,
    }


def hybrid_label_for_code(code: str, component: str) -> str | None:
    if component == "stage0":
        return HYBRID_ROUTE_CODE_TO_STAGE0.get(code)
    if component == "stage1a":
        return code if code in SAFE_READ_ROUTE_CODES else None
    if component == "stage1b":
        return code if code in RISKY_ROUTE_CODES else None
    if component == "stage1c":
        return code if code in SAFE_STAGE_CODES else None
    raise ValueError(f"Unsupported hybrid component: {component}")


def train_hybrid_classifier(
    records: list[dict[str, Any]],
    config: HybridClassifierConfig,
    *,
    encoder: Any | None = None,
    dev_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if encoder is None:
        from sentence_transformers import SentenceTransformer

        encoder = SentenceTransformer(config.embedding_model)
    labeled_records = []
    labels = []
    for record in records:
        label = hybrid_label_for_code(str(record["code"]), config.hybrid_component)
        if label is None:
            continue
        labeled_records.append(record)
        labels.append(label)
    if not labeled_records:
        raise ValueError(f"No records match hybrid component: {config.hybrid_component}")
    texts = [
        format_classifier_text(
            str(record["text"]),
            context_mode=config.context_mode,
            context_flags=record.get("context_flags"),
        )
        for record in labeled_records
    ]
    classifier = _fit_classifier(config.classifier_type, config.random_state, encode_texts(encoder, texts), labels)
    train_hash = train_data_hash(labeled_records)
    dev_hash = train_data_hash(dev_records or []) if dev_records else config.dev_hash
    component_threshold_key = f"{config.hybrid_component}_thresholds"
    metadata = {
        "embedding_model": config.embedding_model,
        "classifier_type": config.classifier_type,
        "routing_mode": "hybrid",
        "hybrid_component": config.hybrid_component,
        "context_mode": config.context_mode,
        "thresholds": config.thresholds.to_dict(),
        "stage0_thresholds": config.stage0_thresholds,
        "stage1a_thresholds": config.stage1a_thresholds,
        "stage1b_thresholds": config.stage1b_thresholds,
        component_threshold_key: getattr(config, component_threshold_key),
        "class_labels": list(classifier.classes_),
        "allowed_labels": sorted(HYBRID_COMPONENT_LABELS[config.hybrid_component]),
        "route_codes": dict(ROUTE_CODES),
        "stage0_labels": dict(HYBRID_STAGE0_LABEL_TO_NAME),
        "risky_route_codes": sorted(RISKY_ROUTE_CODES),
        "safe_read_route_codes": sorted(SAFE_READ_ROUTE_CODES),
        "train_data_hash": train_hash,
        "train_hash": train_hash,
        "dev_hash": dev_hash,
        "template_family_split_id": config.template_family_split_id,
        "train_count": len(labeled_records),
        "created_at_unix": int(time.time()),
    }
    return {
        "artifact_type": "hybrid_embedding_classifier_router",
        "version": 1,
        "metadata": metadata,
        "models": {"classifier": classifier},
    }


def binary_positive_codes(detector_role: str, target_route_code: str | None = None) -> set[str]:
    if detector_role == "risky_action_binary":
        return set(RISKY_ROUTE_CODES)
    if detector_role == "safe_read_binary":
        return set(SAFE_READ_ROUTE_CODES)
    if detector_role == ROUTE_SPECIFIC_RISKY_DETECTOR:
        if target_route_code not in RISKY_ROUTE_CODES:
            raise ValueError(
                "route_specific_risky detector requires target_route_code in "
                f"{sorted(RISKY_ROUTE_CODES)}"
            )
        return {str(target_route_code)}
    raise ValueError(f"Unsupported detector_role: {detector_role}")


def train_binary_detector(
    records: list[dict[str, Any]],
    config: BinaryDetectorConfig,
    *,
    encoder: Any | None = None,
    dev_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if encoder is None:
        from sentence_transformers import SentenceTransformer

        encoder = SentenceTransformer(config.embedding_model)
    positive_codes = binary_positive_codes(config.detector_role, config.target_route_code)
    labels = [POSITIVE_BINARY_LABEL if str(record["code"]) in positive_codes else NEGATIVE_BINARY_LABEL for record in records]
    if len(set(labels)) < 2:
        raise ValueError(f"{config.detector_role} requires positive and negative records")
    texts = [
        format_classifier_text(
            str(record["text"]),
            context_mode=config.context_mode,
            context_flags=record.get("context_flags"),
        )
        for record in records
    ]
    model = _fit_classifier(config.classifier_type, config.random_state, encode_texts(encoder, texts), labels)
    train_hash = train_data_hash(records)
    calibration_summary = dict(config.calibration_summary)
    if dev_records:
        dev_texts = [
            format_classifier_text(
                str(record["text"]),
                context_mode=config.context_mode,
                context_flags=record.get("context_flags"),
            )
            for record in dev_records
        ]
        dev_embeddings = encode_texts(encoder, dev_texts)
        calibration_rows = []
        for index, record in enumerate(dev_records):
            ranked = _probabilities(model, dev_embeddings[index : index + 1])
            predicted_label, confidence = ranked[0]
            calibration_rows.append(
                {
                    "confidence": confidence,
                    "predicted_label": predicted_label,
                    "actual_positive": str(record["code"]) in positive_codes,
                }
            )
        calibration_summary = {"confidence_buckets": calibration_buckets(calibration_rows)}
    return {
        "artifact_type": "hybrid_binary_detector",
        "version": 1,
        "metadata": {
            "embedding_model": config.embedding_model,
            "classifier_type": config.classifier_type,
            "routing_mode": "hybrid_binary",
            "detector_role": config.detector_role,
            "target_route_code": config.target_route_code,
            "target_route": ROUTE_CODES.get(config.target_route_code) if config.target_route_code else None,
            "context_mode": config.context_mode,
            "detector_thresholds": {
                POSITIVE_BINARY_LABEL: {
                    "confidence": config.confidence_threshold,
                    "margin": config.margin_threshold,
                }
            },
            "class_labels": list(model.classes_),
            "positive_label": POSITIVE_BINARY_LABEL,
            "negative_label": NEGATIVE_BINARY_LABEL,
            "positive_route_codes": sorted(positive_codes),
            "train_data_hash": train_hash,
            "train_hash": train_hash,
            "dev_hash": train_data_hash(dev_records or []) if dev_records else config.dev_hash,
            "template_family_split_id": config.template_family_split_id,
            "calibration_summary": calibration_summary,
            "train_count": len(records),
            "created_at_unix": int(time.time()),
        },
        "models": {"classifier": model},
    }


def _probabilities(classifier: Any, embedding: Any) -> list[tuple[str, float]]:
    probabilities = classifier.predict_proba(embedding)[0]
    return sorted(
        [(str(label), float(probability)) for label, probability in zip(classifier.classes_, probabilities)],
        key=lambda item: item[1],
        reverse=True,
    )


def _top_margin(ranked: list[tuple[str, float]]) -> float:
    if len(ranked) < 2:
        return ranked[0][1] if ranked else 0.0
    return ranked[0][1] - ranked[1][1]


def _threshold_for_code(code: str, thresholds: ClassifierThresholds) -> RouteThreshold:
    if code in thresholds.per_route:
        return thresholds.per_route[code]
    if code in RISKY_ROUTE_CODES:
        return RouteThreshold(confidence=thresholds.risky_confidence, margin=thresholds.risky_margin)
    return RouteThreshold(confidence=thresholds.non_risky_confidence, margin=0.0)


def _abstention_reason(code: str, confidence: float, margin: float, threshold: RouteThreshold) -> str | None:
    if confidence < threshold.confidence:
        return "risky_confidence_below_threshold" if code in RISKY_ROUTE_CODES else "non_risky_confidence_below_threshold"
    if margin < threshold.margin:
        return "risky_margin_below_threshold" if code in RISKY_ROUTE_CODES else "route_margin_below_threshold"
    return None


def threshold_decision(
    code: str,
    confidence: float,
    margin: float,
    thresholds: ClassifierThresholds,
) -> tuple[str, bool, float, float, str | None]:
    threshold = _threshold_for_code(code, thresholds)
    reason = _abstention_reason(code, confidence, margin, threshold)
    if reason is None:
        return code, False, threshold.confidence, threshold.margin, None
    return "R02", True, threshold.confidence, threshold.margin, reason


def apply_threshold_guard(code: str, confidence: float, margin: float, thresholds: ClassifierThresholds) -> tuple[str, bool]:
    final_code, guarded, _required_confidence, _required_margin, _reason = threshold_decision(
        code,
        confidence,
        margin,
        thresholds,
    )
    return final_code, guarded


def _prediction(
    *,
    raw_code: str,
    confidence: float,
    margin: float,
    thresholds: ClassifierThresholds,
    routing_mode: str,
    stage1_label: str | None = None,
) -> RouterPrediction:
    code, guarded, required_confidence, required_margin, reason = threshold_decision(
        raw_code,
        confidence,
        margin,
        thresholds,
    )
    return RouterPrediction(
        code,
        confidence,
        margin,
        raw_code,
        guarded,
        routing_mode,
        stage1_label,
        required_confidence,
        required_margin,
        reason,
    )


def _stage1_blocked_prediction(
    *,
    stage1_label: str,
    confidence: float,
    margin: float,
    thresholds: ClassifierThresholds,
    routing_mode: str,
) -> RouterPrediction:
    return RouterPrediction(
        "R02",
        confidence,
        margin,
        stage1_label,
        True,
        routing_mode,
        stage1_label,
        thresholds.risky_confidence,
        thresholds.risky_margin,
        "stage1_blocks_risky_action",
    )


def _stage1_risky_is_confident(confidence: float, margin: float, thresholds: ClassifierThresholds) -> bool:
    return confidence >= thresholds.risky_confidence and margin >= thresholds.risky_margin


def _thresholds_from_metadata(metadata: dict[str, Any]) -> ClassifierThresholds:
    return ClassifierThresholds.from_dict(dict(metadata.get("thresholds") or {}))


def predict_hybrid_label(
    artifact: dict[str, Any],
    text: str,
    *,
    encoder: Any,
    context_flags: dict[str, Any] | None = None,
) -> RouterPrediction:
    metadata = artifact["metadata"]
    thresholds = _thresholds_from_metadata(metadata)
    component = str(metadata["hybrid_component"])
    formatted_text = format_classifier_text(
        text,
        context_mode=str(metadata.get("context_mode") or "text_only"),
        context_flags=context_flags,
    )
    embedding = encoder.encode([formatted_text], normalize_embeddings=True, show_progress_bar=False)
    ranked = _probabilities(artifact["models"]["classifier"], embedding)
    raw_label, confidence = ranked[0]
    margin = _top_margin(ranked)
    if component == "stage0":
        stage0_thresholds = dict(metadata.get("stage0_thresholds") or {})
        threshold = stage0_thresholds.get(raw_label) if isinstance(stage0_thresholds.get(raw_label), dict) else None
        if threshold is not None:
            required_confidence = float(threshold.get("confidence", 0.0))
            required_margin = float(threshold.get("margin", 0.0))
            if confidence < required_confidence:
                return RouterPrediction(
                    "G02",
                    confidence,
                    margin,
                    raw_label,
                    True,
                    "hybrid",
                    component,
                    required_confidence,
                    required_margin,
                    "stage0_confidence_below_threshold",
                )
            if margin < required_margin:
                return RouterPrediction(
                    "G02",
                    confidence,
                    margin,
                    raw_label,
                    True,
                    "hybrid",
                    component,
                    required_confidence,
                    required_margin,
                    "stage0_margin_below_threshold",
                )
        return RouterPrediction(
            raw_label,
            confidence,
            margin,
            raw_label,
            False,
            "hybrid",
            component,
            0.0,
            0.0,
            None,
        )
    code, guarded, required_confidence, required_margin, reason = threshold_decision(
        raw_label,
        confidence,
        margin,
        thresholds,
    )
    return RouterPrediction(
        code,
        confidence,
        margin,
        raw_label,
        guarded,
        "hybrid",
        component,
        required_confidence,
        required_margin,
        reason,
    )


def predict_binary_detector(
    artifact: dict[str, Any],
    text: str,
    *,
    encoder: Any,
    context_flags: dict[str, Any] | None = None,
) -> RouterPrediction:
    metadata = artifact["metadata"]
    formatted_text = format_classifier_text(
        text,
        context_mode=str(metadata.get("context_mode") or "text_only"),
        context_flags=context_flags,
    )
    embedding = encoder.encode([formatted_text], normalize_embeddings=True, show_progress_bar=False)
    ranked = _probabilities(artifact["models"]["classifier"], embedding)
    raw_label, confidence = ranked[0]
    margin = _top_margin(ranked)
    threshold = (metadata.get("detector_thresholds") or {}).get(POSITIVE_BINARY_LABEL) or {}
    required_confidence = float(threshold.get("confidence", 0.0))
    required_margin = float(threshold.get("margin", 0.0))
    if raw_label == POSITIVE_BINARY_LABEL:
        if confidence < required_confidence:
            return RouterPrediction(
                NEGATIVE_BINARY_LABEL,
                confidence,
                margin,
                raw_label,
                True,
                "hybrid_binary",
                str(metadata["detector_role"]),
                required_confidence,
                required_margin,
                "binary_confidence_below_threshold",
            )
        if margin < required_margin:
            return RouterPrediction(
                NEGATIVE_BINARY_LABEL,
                confidence,
                margin,
                raw_label,
                True,
                "hybrid_binary",
                str(metadata["detector_role"]),
                required_confidence,
                required_margin,
                "binary_margin_below_threshold",
            )
    return RouterPrediction(
        raw_label,
        confidence,
        margin,
        raw_label,
        False,
        "hybrid_binary",
        str(metadata["detector_role"]),
        required_confidence,
        required_margin,
        None,
    )


def combined_binary_stage0_gate(
    *,
    risky_prediction: RouterPrediction,
    safe_read_prediction: RouterPrediction,
    fallback_gate: str,
) -> str:
    if risky_prediction.code == POSITIVE_BINARY_LABEL and not risky_prediction.guarded:
        return "G04"
    if safe_read_prediction.code == POSITIVE_BINARY_LABEL and not safe_read_prediction.guarded:
        return "G03"
    return fallback_gate if fallback_gate in {"G00", "G01", "G02"} else "G02"


def calibration_buckets(
    predictions: list[dict[str, Any]],
    *,
    positive_label: str = POSITIVE_BINARY_LABEL,
    bucket_size: float = 0.1,
) -> list[dict[str, Any]]:
    buckets: dict[int, dict[str, Any]] = {}
    for prediction in predictions:
        confidence = float(prediction["confidence"])
        bucket_index = min(int(confidence / bucket_size), int(1.0 / bucket_size) - 1)
        bucket = buckets.setdefault(
            bucket_index,
            {
                "bucket_min": round(bucket_index * bucket_size, 3),
                "bucket_max": round((bucket_index + 1) * bucket_size, 3),
                "count": 0,
                "predicted_positive": 0,
                "true_positive": 0,
                "actual_positive": 0,
            },
        )
        predicted_positive = prediction["predicted_label"] == positive_label
        actual_positive = bool(prediction["actual_positive"])
        bucket["count"] += 1
        bucket["predicted_positive"] += int(predicted_positive)
        bucket["true_positive"] += int(predicted_positive and actual_positive)
        bucket["actual_positive"] += int(actual_positive)
    summaries = []
    for bucket in sorted(buckets.values(), key=lambda item: item["bucket_min"]):
        predicted_positive = int(bucket["predicted_positive"])
        actual_positive = int(bucket["actual_positive"])
        summaries.append(
            {
                **bucket,
                "precision": bucket["true_positive"] / predicted_positive if predicted_positive else 1.0,
                "recall": bucket["true_positive"] / actual_positive if actual_positive else 0.0,
            }
        )
    return summaries


def predict_route_code(
    artifact: dict[str, Any],
    text: str,
    *,
    encoder: Any,
    context_flags: dict[str, Any] | None = None,
) -> RouterPrediction:
    metadata = artifact["metadata"]
    thresholds = _thresholds_from_metadata(metadata)
    routing_mode = str(metadata["routing_mode"])
    formatted_text = format_classifier_text(
        text,
        context_mode=str(metadata.get("context_mode") or "text_only"),
        context_flags=context_flags,
    )
    embedding = encoder.encode([formatted_text], normalize_embeddings=True, show_progress_bar=False)
    if routing_mode == "flat_15_class":
        ranked = _probabilities(artifact["models"]["flat"], embedding)
        raw_code, confidence = ranked[0]
        return _prediction(
            raw_code=raw_code,
            confidence=confidence,
            margin=_top_margin(ranked),
            thresholds=thresholds,
            routing_mode=routing_mode,
        )
    stage1_ranked = _probabilities(artifact["models"]["stage1"], embedding)
    stage1_label, stage1_confidence = stage1_ranked[0]
    stage1_margin = _top_margin(stage1_ranked)
    if routing_mode == "two_stage":
        if stage1_label != ACTION_STAGE_LABEL:
            return _prediction(
                raw_code=stage1_label,
                confidence=stage1_confidence,
                margin=stage1_margin,
                thresholds=thresholds,
                routing_mode=routing_mode,
                stage1_label=stage1_label,
            )
        stage2_ranked = _probabilities(artifact["models"]["stage2"], embedding)
        raw_code, confidence = stage2_ranked[0]
        return _prediction(
            raw_code=raw_code,
            confidence=confidence,
            margin=_top_margin(stage2_ranked),
            thresholds=thresholds,
            routing_mode=routing_mode,
            stage1_label=stage1_label,
        )
    if routing_mode != "three_stage":
        raise ValueError(f"Unsupported routing_mode in artifact: {routing_mode}")
    if stage1_label in THREE_STAGE_SAFE_LABEL_TO_CODE:
        raw_code = THREE_STAGE_SAFE_LABEL_TO_CODE[stage1_label]
        return _prediction(
            raw_code=raw_code,
            confidence=stage1_confidence,
            margin=stage1_margin,
            thresholds=thresholds,
            routing_mode=routing_mode,
            stage1_label=stage1_label,
        )
    if stage1_label == THREE_STAGE_SAFE_READ:
        stage2_ranked = _probabilities(artifact["models"]["safe_read"], embedding)
        raw_code, confidence = stage2_ranked[0]
        return _prediction(
            raw_code=raw_code,
            confidence=confidence,
            margin=_top_margin(stage2_ranked),
            thresholds=thresholds,
            routing_mode=routing_mode,
            stage1_label=stage1_label,
        )
    if stage1_label == THREE_STAGE_RISKY:
        if not _stage1_risky_is_confident(stage1_confidence, stage1_margin, thresholds):
            return _stage1_blocked_prediction(
                stage1_label=stage1_label,
                confidence=stage1_confidence,
                margin=stage1_margin,
                thresholds=thresholds,
                routing_mode=routing_mode,
            )
        stage2_ranked = _probabilities(artifact["models"]["risky"], embedding)
        raw_code, confidence = stage2_ranked[0]
        return _prediction(
            raw_code=raw_code,
            confidence=confidence,
            margin=_top_margin(stage2_ranked),
            thresholds=thresholds,
            routing_mode=routing_mode,
            stage1_label=stage1_label,
        )
    raise ValueError(f"Unsupported three_stage label: {stage1_label}")


def apply_thresholds_to_artifact(
    artifact: dict[str, Any],
    thresholds: ClassifierThresholds,
) -> dict[str, Any]:
    copied = {
        **artifact,
        "metadata": {
            **dict(artifact.get("metadata") or {}),
            "thresholds": thresholds.to_dict(),
        },
    }
    copied["models"] = artifact["models"]
    return copied


def save_artifact(artifact: dict[str, Any], path: Path) -> None:
    import joblib

    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)


def load_artifact(path: Path) -> dict[str, Any]:
    import joblib

    artifact = joblib.load(path)
    if artifact.get("artifact_type") not in {
        "embedding_classifier_router",
        "hybrid_embedding_classifier_router",
        "hybrid_binary_detector",
    }:
        raise ValueError(f"{path} is not an embedding classifier router artifact")
    return artifact


def default_artifact_path(config: RouterClassifierConfig) -> Path:
    model_slug = config.embedding_model.replace("/", "__").replace("-", "_").replace(".", "_")
    return DEFAULT_OUTPUT_DIR / f"router_embedding_{model_slug}_{config.routing_mode}_{config.classifier_type}.joblib"


def default_hybrid_artifact_path(config: HybridClassifierConfig) -> Path:
    model_slug = config.embedding_model.replace("/", "__").replace("-", "_").replace(".", "_")
    return DEFAULT_OUTPUT_DIR / (
        f"router_hybrid_{model_slug}_{config.hybrid_component}_{config.classifier_type}_{config.context_mode}.joblib"
    )


def default_binary_artifact_path(config: BinaryDetectorConfig) -> Path:
    model_slug = config.embedding_model.replace("/", "__").replace("-", "_").replace(".", "_")
    detector_slug = (
        f"{config.detector_role}_{str(config.target_route_code).lower()}"
        if config.detector_role == ROUTE_SPECIFIC_RISKY_DETECTOR
        else config.detector_role
    )
    return DEFAULT_OUTPUT_DIR / (
        f"router_hybrid_binary_{model_slug}_{detector_slug}_{config.classifier_type}_{config.context_mode}.joblib"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train a NullXoid route-code embedding classifier router.")
    parser.add_argument("--train-jsonl", type=Path, default=DEFAULT_TRAIN_JSONL)
    parser.add_argument("--dev-jsonl", type=Path)
    parser.add_argument("--embedding-model", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--classifier", choices=sorted(SUPPORTED_CLASSIFIERS), default="logistic_regression")
    parser.add_argument("--routing-mode", choices=sorted(SUPPORTED_ROUTING_MODES), default="flat_15_class")
    parser.add_argument("--hybrid-component", choices=sorted(SUPPORTED_HYBRID_COMPONENTS))
    parser.add_argument("--binary-detector", choices=sorted(SUPPORTED_BINARY_DETECTORS))
    parser.add_argument("--target-route-code", choices=sorted(RISKY_ROUTE_CODES))
    parser.add_argument("--context-mode", choices=sorted(SUPPORTED_CONTEXT_MODES), default="text_only")
    parser.add_argument("--template-family-split-id", default="unspecified")
    parser.add_argument("--risky-confidence", type=float, default=0.95)
    parser.add_argument("--risky-margin", type=float, default=0.20)
    parser.add_argument("--non-risky-confidence", type=float, default=0.50)
    parser.add_argument("--stage0-g04-confidence", type=float)
    parser.add_argument("--stage0-g04-margin", type=float)
    parser.add_argument("--stage0-g03-confidence", type=float)
    parser.add_argument("--stage0-g03-margin", type=float)
    parser.add_argument("--binary-confidence", type=float, default=0.95)
    parser.add_argument("--binary-margin", type=float, default=0.0)
    parser.add_argument("--no-per-route-defaults", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    thresholds = ClassifierThresholds(
        risky_confidence=args.risky_confidence,
        risky_margin=args.risky_margin,
        non_risky_confidence=args.non_risky_confidence,
        per_route={} if args.no_per_route_defaults else default_per_route_thresholds(),
    )
    records = extract_sft_route_records(args.train_jsonl)
    dev_records = extract_sft_route_records(args.dev_jsonl) if args.dev_jsonl else None
    stage0_thresholds: dict[str, Any] = {}
    if args.stage0_g04_confidence is not None or args.stage0_g04_margin is not None:
        stage0_thresholds["G04"] = {
            "confidence": float(args.stage0_g04_confidence if args.stage0_g04_confidence is not None else 0.0),
            "margin": float(args.stage0_g04_margin if args.stage0_g04_margin is not None else 0.0),
        }
    if args.stage0_g03_confidence is not None or args.stage0_g03_margin is not None:
        stage0_thresholds["G03"] = {
            "confidence": float(args.stage0_g03_confidence if args.stage0_g03_confidence is not None else 0.0),
            "margin": float(args.stage0_g03_margin if args.stage0_g03_margin is not None else 0.0),
        }
    if args.binary_detector:
        binary_config = BinaryDetectorConfig(
            embedding_model=args.embedding_model,
            classifier_type=args.classifier,
            detector_role=args.binary_detector,
            target_route_code=args.target_route_code,
            context_mode=args.context_mode,
            confidence_threshold=args.binary_confidence,
            margin_threshold=args.binary_margin,
            template_family_split_id=args.template_family_split_id,
        )
        artifact = train_binary_detector(records, binary_config, dev_records=dev_records)
        output = args.output or default_binary_artifact_path(binary_config)
    elif args.hybrid_component:
        hybrid_config = HybridClassifierConfig(
            embedding_model=args.embedding_model,
            classifier_type=args.classifier,
            hybrid_component=args.hybrid_component,
            context_mode=args.context_mode,
            thresholds=thresholds,
            template_family_split_id=args.template_family_split_id,
            stage0_thresholds=stage0_thresholds,
        )
        artifact = train_hybrid_classifier(records, hybrid_config, dev_records=dev_records)
        output = args.output or default_hybrid_artifact_path(hybrid_config)
    else:
        config = RouterClassifierConfig(
            embedding_model=args.embedding_model,
            classifier_type=args.classifier,
            routing_mode=args.routing_mode,
            context_mode=args.context_mode,
            thresholds=thresholds,
        )
        artifact = train_embedding_classifier(records, config)
        output = args.output or default_artifact_path(config)
    save_artifact(artifact, output)
    print(
        json.dumps(
            {
                "artifact": str(output),
                "embedding_model": artifact["metadata"]["embedding_model"],
                "classifier_type": artifact["metadata"]["classifier_type"],
                "routing_mode": artifact["metadata"]["routing_mode"],
                "hybrid_component": artifact["metadata"].get("hybrid_component"),
                "detector_role": artifact["metadata"].get("detector_role"),
                "target_route_code": artifact["metadata"].get("target_route_code"),
                "context_mode": artifact["metadata"]["context_mode"],
                "train_count": artifact["metadata"]["train_count"],
                "train_data_hash": artifact["metadata"]["train_data_hash"],
                "dev_hash": artifact["metadata"].get("dev_hash"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
