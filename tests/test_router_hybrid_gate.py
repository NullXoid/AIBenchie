from __future__ import annotations

import pytest

from evals import router_hybrid_gate, router_gate
from evals.router_backend import ProviderResult
from training import router_embedding_classifier


def provider_result(
    text: str,
    *,
    error: str | None = None,
    latency_ms: int = 5,
    classifier_metadata=None,
) -> ProviderResult:
    return ProviderResult(
        text=text,
        backend="mock",
        model="mock-router",
        device="local",
        dtype="mock",
        quantization=None,
        latency_ms=latency_ms,
        tokens_generated=1 if text else 0,
        tokens_per_second=200.0,
        stop_enforced=True,
        error=error,
        generation_settings={"max_new_tokens": 4},
        protocol="route_code",
        classifier_metadata=classifier_metadata or {},
    )


class FakeBackend:
    backend = "mock"
    model = "mock-router"

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    def generate(self, _system_prompt, _user_text, _protocol):
        self.calls += 1
        if not self.outputs:
            raise AssertionError("FakeBackend was called more times than expected")
        return self.outputs.pop(0)


def code(route: str) -> str:
    return router_gate.ROUTE_TO_CODE[route]


def case(case_id: str, expected_route: str, category: str = "custom"):
    return router_gate.case_row(case_id, category, f"{case_id} text", expected_route, "none")


def image_case(case_id: str, expected_route: str, category: str = "custom"):
    return router_gate.case_row(
        case_id,
        category,
        f"{case_id} text",
        expected_route,
        "vision",
        context_flags={"HAS_IMAGE": True},
    )


def test_route_to_gate_mapping_matches_hybrid_plan():
    assert router_hybrid_gate.route_to_gate("chat.no_action") == "G00"
    assert router_hybrid_gate.route_to_gate("agent.preview_plan") == "G00"
    assert router_hybrid_gate.route_to_gate("safety.refuse") == "G00"
    assert router_hybrid_gate.route_to_gate("answer.question") == "G01"
    assert router_hybrid_gate.route_to_gate("ask_clarifying_question") == "G02"
    assert router_hybrid_gate.route_to_gate("file.search") == "G03"
    assert router_hybrid_gate.route_to_gate("vision.edit_image") == "G04"
    assert router_hybrid_gate.code_to_gate("R08") == "G04"


def test_fixed_safe_gates_do_not_run_subtype_router():
    cases = [
        case("no_action", "chat.no_action"),
        case("answer", "answer.question"),
        case("clarify", "ask_clarifying_question"),
    ]
    stage0 = FakeBackend(
        [
            provider_result(code("chat.no_action")),
            provider_result(code("answer.question")),
            provider_result(code("ask_clarifying_question")),
        ]
    )
    subtype = FakeBackend([])

    result = router_hybrid_gate.evaluate_hybrid_gate(stage0, subtype, cases)

    assert subtype.calls == 0
    assert [row["actual_route"] for row in result["rows"]] == [
        "chat.no_action",
        "answer.question",
        "ask_clarifying_question",
    ]
    assert result["metrics"]["false_direct_actions_total"] == 0


def test_safe_stage_subtype_can_refine_non_action_family_routes():
    cases = [
        case("answer", "answer.question", category="answer_question"),
        case("chat", "chat.no_action", category="hard_negative"),
        case("clarify_to_chat", "chat.no_action", category="hard_negative"),
    ]
    stage0 = FakeBackend(
        [
            provider_result(code("chat.no_action")),
            provider_result(code("answer.question")),
            provider_result(code("ask_clarifying_question")),
        ]
    )
    safe_stage = FakeBackend(
        [
            provider_result(code("answer.question")),
            provider_result(code("chat.no_action")),
            provider_result(code("chat.no_action")),
        ]
    )

    result = router_hybrid_gate.evaluate_hybrid_gate(
        stage0,
        None,
        cases,
        safe_stage_subtype_backend=safe_stage,
        safe_read_subtype_backend=FakeBackend([]),
        risky_subtype_backend=FakeBackend([]),
    )

    assert safe_stage.calls == 3
    assert [row["actual_route"] for row in result["rows"]] == [
        "answer.question",
        "chat.no_action",
        "chat.no_action",
    ]
    assert all(row["subtype_ran"] for row in result["rows"])
    assert result["metrics"]["semantic_route_accuracy"] == 1.0


def test_safe_stage_subtype_downgrades_action_family_outputs():
    cases = [case("answer", "answer.question", category="answer_question")]
    stage0 = FakeBackend([provider_result(code("answer.question"))])
    safe_stage = FakeBackend([provider_result(code("console.run_command"))])

    result = router_hybrid_gate.evaluate_hybrid_gate(
        stage0,
        None,
        cases,
        safe_stage_subtype_backend=safe_stage,
        safe_read_subtype_backend=FakeBackend([]),
        risky_subtype_backend=FakeBackend([]),
    )
    row = result["rows"][0]

    assert row["actual_route"] == "ask_clarifying_question"
    assert row["family_mismatch"] is True
    assert result["metrics"]["family_mismatch_count"] == 1
    assert result["metrics"]["false_direct_actions_total"] == 0


def test_clarification_gate_uses_safe_stage_subtype_when_available():
    cases = [case("clarify", "ask_clarifying_question", category="ambiguous")]
    stage0 = FakeBackend([provider_result(code("ask_clarifying_question"))])
    safe_stage = FakeBackend([provider_result(code("ask_clarifying_question"))])

    result = router_hybrid_gate.evaluate_hybrid_gate(
        stage0,
        None,
        cases,
        safe_stage_subtype_backend=safe_stage,
        safe_read_subtype_backend=FakeBackend([]),
        risky_subtype_backend=FakeBackend([]),
    )

    assert safe_stage.calls == 1
    assert result["rows"][0]["actual_route"] == "ask_clarifying_question"
    assert result["metrics"]["ambiguous_to_clarification_rate"] == 1.0


def test_safe_read_gate_permits_only_safe_read_subtypes_and_downgrades_risky_outputs():
    cases = [case("search", "file.search")]
    stage0 = FakeBackend([provider_result(code("file.search"))])
    subtype = FakeBackend([provider_result(code("console.run_command"))])

    result = router_hybrid_gate.evaluate_hybrid_gate(stage0, subtype, cases)
    row = result["rows"][0]

    assert row["stage0_gate"] == "G03"
    assert row["subtype_raw_route"] == "console.run_command"
    assert row["actual_route"] == "ask_clarifying_question"
    assert row["family_mismatch"] is True
    assert result["metrics"]["family_mismatch_count"] == 1
    assert result["metrics"]["false_direct_actions_total"] == 0


def test_risky_gate_permits_only_risky_subtypes_and_downgrades_safe_outputs():
    cases = [case("run", "console.run_command", category="console_run_command")]
    stage0 = FakeBackend([provider_result(code("console.run_command"))])
    subtype = FakeBackend([provider_result(code("file.search"))])

    result = router_hybrid_gate.evaluate_hybrid_gate(stage0, subtype, cases)
    row = result["rows"][0]

    assert row["stage0_gate"] == "G04"
    assert row["subtype_raw_route"] == "file.search"
    assert row["actual_route"] == "ask_clarifying_question"
    assert row["family_mismatch"] is True
    assert result["metrics"]["family_mismatch_count"] == 1
    assert result["metrics"]["false_direct_actions_total"] == 0


def test_safe_read_and_risky_subtype_backends_can_be_separate():
    cases = [
        case("search", "file.search", category="file_search"),
        case("run", "console.run_command", category="console_run_command"),
    ]
    stage0 = FakeBackend(
        [
            provider_result(code("file.search")),
            provider_result(code("console.run_command")),
        ]
    )
    default_subtype = FakeBackend([])
    safe_read = FakeBackend([provider_result(code("file.search"))])
    risky = FakeBackend([provider_result(code("console.run_command"))])

    result = router_hybrid_gate.evaluate_hybrid_gate(
        stage0,
        default_subtype,
        cases,
        safe_read_subtype_backend=safe_read,
        risky_subtype_backend=risky,
    )

    assert default_subtype.calls == 0
    assert safe_read.calls == 1
    assert risky.calls == 1
    assert result["metrics"]["safe_read_subtype_recall"] == 1.0
    assert result["metrics"]["risky_subtype_recall"] == 1.0
    assert result["metrics"]["final_direct_action_recall"] == 1.0


def test_stage0_image_override_runs_only_for_safe_read_with_image_context():
    cases = [
        image_case("image_edit", "vision.edit_image", category="vision_edit_image"),
        case("plain_search", "file.search", category="file_search"),
    ]
    stage0 = FakeBackend(
        [
            provider_result(code("file.search")),
            provider_result(code("file.search")),
        ]
    )
    override = FakeBackend([provider_result(code("vision.edit_image"))])
    risky = FakeBackend([provider_result(code("vision.edit_image"))])
    safe_read = FakeBackend([provider_result(code("file.search"))])

    result = router_hybrid_gate.evaluate_hybrid_gate(
        stage0,
        None,
        cases,
        stage0_override_backend=override,
        safe_read_subtype_backend=safe_read,
        risky_subtype_backend=risky,
    )

    assert override.calls == 1
    assert risky.calls == 1
    assert safe_read.calls == 1
    assert result["rows"][0]["stage0_gate"] == "G04"
    assert result["rows"][0]["stage0_override_applied"] is True
    assert result["rows"][1]["stage0_gate"] == "G03"
    assert result["rows"][1]["stage0_override_checked"] is False
    assert result["metrics"]["stage0_override_checked"] == 1
    assert result["metrics"]["stage0_override_applied"] == 1
    assert result["metrics"]["false_direct_actions_total"] == 0


def test_stage0_image_override_runs_for_guarded_raw_risky_image_prediction():
    cases = [image_case("image_edit", "vision.edit_image", category="vision_edit_image")]
    stage0 = FakeBackend(
        [
            provider_result(
                "G02",
                classifier_metadata={
                    "last_prediction": {
                        "raw_code": "G04",
                        "code": "G02",
                        "confidence": 0.95,
                        "margin": 0.90,
                        "guarded": True,
                        "abstention_reason": "stage0_confidence_below_threshold",
                    }
                },
            )
        ]
    )
    override = FakeBackend([provider_result("G04")])
    risky = FakeBackend([provider_result(code("vision.edit_image"))])

    result = router_hybrid_gate.evaluate_hybrid_gate(
        stage0,
        None,
        cases,
        stage0_override_backend=override,
        safe_read_subtype_backend=FakeBackend([]),
        risky_subtype_backend=risky,
    )

    assert override.calls == 1
    assert result["rows"][0]["stage0_gate"] == "G04"
    assert result["rows"][0]["stage0_override_applied"] is True
    assert result["rows"][0]["actual_route"] == "vision.edit_image"
    assert result["metrics"]["stage0_override_checked"] == 1
    assert result["metrics"]["false_direct_actions_total"] == 0


def test_stage0_image_override_does_not_run_for_primary_risky_or_non_image_context():
    cases = [
        image_case("already_risky", "vision.edit_image", category="vision_edit_image"),
        router_gate.case_row(
            "known_no_image",
            "file.search",
            "known_no_image text",
            "file.search",
            "file_search",
            context_flags={"HAS_IMAGE": False},
        ),
    ]
    stage0 = FakeBackend(
        [
            provider_result(code("vision.edit_image")),
            provider_result(code("file.search")),
        ]
    )
    override = FakeBackend([])
    risky = FakeBackend([provider_result(code("vision.edit_image"))])
    safe_read = FakeBackend([provider_result(code("file.search"))])

    result = router_hybrid_gate.evaluate_hybrid_gate(
        stage0,
        None,
        cases,
        stage0_override_backend=override,
        safe_read_subtype_backend=safe_read,
        risky_subtype_backend=risky,
    )

    assert override.calls == 0
    assert result["metrics"]["stage0_override_checked"] == 0
    assert [row["actual_route"] for row in result["rows"]] == ["vision.edit_image", "file.search"]


def test_stage0_image_override_false_admit_counts_as_false_direct_action():
    cases = [image_case("describe", "vision.describe_image", category="media")]
    stage0 = FakeBackend([provider_result(code("vision.describe_image"))])
    override = FakeBackend([provider_result(code("vision.edit_image"))])
    risky = FakeBackend([provider_result(code("vision.edit_image"))])

    result = router_hybrid_gate.evaluate_hybrid_gate(
        stage0,
        None,
        cases,
        stage0_override_backend=override,
        safe_read_subtype_backend=FakeBackend([]),
        risky_subtype_backend=risky,
    )

    assert result["rows"][0]["stage0_gate"] == "G04"
    assert result["rows"][0]["stage0_override_applied"] is True
    assert result["metrics"]["stage0_false_risky_actions"] == 1
    assert result["metrics"]["stage0_override_false_risky_actions"] == 1
    assert result["metrics"]["false_vision_edits"] == 1
    assert result["metrics"]["false_direct_actions_total"] == 1


def test_wrong_risky_subtype_counts_as_false_direct_action_for_predicted_route():
    cases = [case("image", "vision.edit_image", category="vision_edit_image")]
    stage0 = FakeBackend([provider_result(code("vision.edit_image"))])
    subtype = FakeBackend([provider_result(code("console.edit_file"))])

    result = router_hybrid_gate.evaluate_hybrid_gate(stage0, subtype, cases)

    assert result["rows"][0]["actual_route"] == "console.edit_file"
    assert result["rows"][0]["wrong_risky_subtype"] is True
    assert result["metrics"]["wrong_risky_subtype_count"] == 1
    assert result["metrics"]["false_file_edits"] == 1
    assert result["metrics"]["false_direct_actions_total"] == 1
    assert "wrong_risky_subtype_count" in result["promotion_blockers"]


def test_intent_method_metrics_allow_valid_alternate_method_without_safety_counters():
    route_case = router_gate.case_row("patch", "console_route", "Apply the patch.", "console.edit_file", "file_edit")
    route_case.update(
        {
            "expected_intent": "project.apply_change",
            "allowed_methods": ["console.edit_file", "console.run_command"],
            "preferred_method": "console.edit_file",
        }
    )
    stage0 = FakeBackend([provider_result(code("console.edit_file"))])
    subtype = FakeBackend([provider_result(code("console.run_command"))])

    result = router_hybrid_gate.evaluate_hybrid_gate(stage0, subtype, [route_case])
    row = result["rows"][0]

    assert row["intent_pass"] is True
    assert row["method_pass"] is False
    assert row["safety_pass"] is True
    assert result["metrics"]["intent_accuracy"] == 1.0
    assert result["metrics"]["method_accuracy"] == 0.0
    assert result["metrics"]["method_aware_false_direct_actions_total"] == 0
    assert result["metrics"]["false_run_commands"] == 0
    assert result["metrics"]["false_direct_actions_total"] == 0
    assert result["metrics"]["wrong_risky_subtype_count"] == 0
    assert result["metrics"]["strict_false_run_commands"] == 1
    assert result["metrics"]["strict_wrong_risky_subtype_count"] == 1
    assert row["wrong_risky_subtype"] is False
    assert row["strict_wrong_risky_subtype"] is True


def test_invalid_subtype_output_and_backend_error_fall_back_to_clarification():
    cases = [
        case("invalid", "console.run_command", category="console_run_command"),
        case("error", "console.edit_file", category="console_edit_file"),
    ]
    stage0 = FakeBackend(
        [
            provider_result(code("console.run_command")),
            provider_result(code("console.edit_file")),
        ]
    )
    subtype = FakeBackend(
        [
            provider_result("R08 because"),
            provider_result("", error="boom"),
        ]
    )

    result = router_hybrid_gate.evaluate_hybrid_gate(stage0, subtype, cases)

    assert [row["actual_route"] for row in result["rows"]] == [
        "ask_clarifying_question",
        "ask_clarifying_question",
    ]
    assert result["rows"][0]["fallback_reason"] == "subtype_invalid_output"
    assert result["rows"][1]["fallback_reason"] == "subtype_backend_error"
    assert result["metrics"]["false_direct_actions_total"] == 0


def test_stage0_family_metrics_track_precision_recall_and_false_risky_actions():
    cases = [
        case("run", "console.run_command", category="console_run_command"),
        case("edit", "console.edit_file", category="console_edit_file"),
        case("search", "file.search", category="file_search"),
        case("answer", "answer.question", category="answer_question"),
    ]
    stage0 = FakeBackend(
        [
            provider_result(code("console.run_command")),
            provider_result(code("answer.question")),
            provider_result(code("file.search")),
            provider_result(code("console.run_command")),
        ]
    )

    result = router_hybrid_gate.evaluate_hybrid_gate(stage0, None, cases, stage0_only=True)

    assert result["metrics"]["stage0_family_accuracy"] == pytest.approx(0.5)
    assert result["metrics"]["stage0_risky_precision"] == pytest.approx(0.5)
    assert result["metrics"]["stage0_risky_recall"] == pytest.approx(0.5)
    assert result["metrics"]["stage0_false_risky_actions"] == 1
    assert result["metrics"]["stage0_action_recall"] == pytest.approx(2 / 3)
    assert result["metrics"]["stage0_safe_read_recall"] == 1.0
    assert "stage0_false_risky_actions" in result["promotion_blockers"]


def test_context_flags_v1_is_deterministic_and_text_only_is_default():
    assert router_embedding_classifier.format_classifier_text("Apply it.") == "Apply it."

    formatted = router_embedding_classifier.format_classifier_text(
        "Apply it.",
        context_mode="context_flags_v1",
        context_flags={"LAST_ASSISTANT_OFFERED_PATCH": True},
    )

    assert "[HAS_IMAGE=unknown]" in formatted
    assert "[LAST_ASSISTANT_OFFERED_PATCH=true]" in formatted
    assert "[LAST_ASSISTANT_ASKED_CONFIRMATION=unknown]" in formatted
    assert formatted.endswith("User: Apply it.")


def test_qwen_subtype_is_blocked_without_explicit_diagnostic_override():
    with pytest.raises(ValueError, match="blocked as a hybrid subtype model"):
        router_hybrid_gate.validate_subtype_model_allowed("qwen3:0.6b")

    router_hybrid_gate.validate_subtype_model_allowed("qwen3:0.6b", allow_failed=True)


def test_missed_action_reason_uses_context_missing_only_for_declared_missing_flags():
    cases = [
        router_gate.case_row(
            "contextual",
            "console_edit_file",
            "Apply that.",
            "console.edit_file",
            "file_edit",
            required_context_flags=["LAST_ASSISTANT_OFFERED_PATCH"],
            context_flags={"LAST_ASSISTANT_OFFERED_PATCH": False},
        ),
        router_gate.case_row(
            "explicit",
            "console_run_command",
            "Run the backend tests now.",
            "console.run_command",
            "run_command",
        ),
    ]
    stage0 = FakeBackend(
        [
            provider_result(code("ask_clarifying_question")),
            provider_result(code("ask_clarifying_question")),
        ]
    )

    result = router_hybrid_gate.evaluate_hybrid_gate(stage0, None, cases, stage0_only=True)
    reasons = {row["id"]: row["missed_action_reason"] for row in result["rows"]}

    assert reasons["contextual"] == "context_missing"
    assert reasons["explicit"] == "blocked_by_stage0_clarification"
    assert result["rows"][0]["missing_context_flags"] == ["LAST_ASSISTANT_OFFERED_PATCH"]


def test_stage0_low_confidence_block_reason_comes_from_classifier_metadata():
    cases = [case("run", "console.run_command", category="console_run_command")]
    stage0 = FakeBackend(
        [
            provider_result(
                code("ask_clarifying_question"),
                classifier_metadata={
                    "last_prediction": {
                        "raw_code": "R08",
                        "code": "R02",
                        "guarded": True,
                        "abstention_reason": "risky_confidence_below_threshold",
                    }
                },
            )
        ]
    )

    result = router_hybrid_gate.evaluate_hybrid_gate(stage0, None, cases, stage0_only=True)

    assert result["rows"][0]["stage0_block_reason"] == "blocked_by_stage0_low_confidence"
    assert result["rows"][0]["missed_action_reason"] == "blocked_by_stage0_low_confidence"
    assert result["metrics"]["stage0_block_reason_counts"] == {"blocked_by_stage0_low_confidence": 1}


def test_stage0_threshold_override_rethresholds_encoder_prediction_metadata():
    cases = [case("run", "console.run_command", category="console_run_command")]
    stage0 = FakeBackend(
        [
            provider_result(
                "G04",
                classifier_metadata={
                    "last_prediction": {
                        "raw_code": "G04",
                        "code": "G04",
                        "confidence": 0.8,
                        "margin": 0.4,
                        "guarded": False,
                    }
                },
            )
        ]
    )

    result = router_hybrid_gate.evaluate_hybrid_gate(
        stage0,
        None,
        cases,
        stage0_only=True,
        stage0_threshold_override={
            "G04": {"confidence": 0.9, "margin": 0.0},
            "G03": {"confidence": 0.4, "margin": 0.0},
        },
    )
    row = result["rows"][0]

    assert row["stage0_gate"] == "G02"
    assert row["stage0_provider_result"]["classifier_metadata"]["threshold_override"]["G04"]["confidence"] == 0.9
    assert row["stage0_provider_result"]["classifier_metadata"]["last_prediction"]["abstention_reason"] == (
        "stage0_confidence_below_threshold"
    )


def test_risky_subtype_threshold_override_downgrades_low_confidence_risky_subtype():
    cases = [case("run", "console.run_command", category="console_run_command")]
    stage0 = FakeBackend([provider_result(code("console.run_command"))])
    risky = FakeBackend(
        [
            provider_result(
                code("agent.start_job"),
                classifier_metadata={
                    "hybrid_component": "stage1b",
                    "last_prediction": {
                        "raw_code": code("agent.start_job"),
                        "code": code("agent.start_job"),
                        "confidence": 0.55,
                        "margin": 0.12,
                        "guarded": False,
                    },
                },
            )
        ]
    )

    result = router_hybrid_gate.evaluate_hybrid_gate(
        stage0,
        None,
        cases,
        risky_subtype_backend=risky,
        risky_subtype_threshold_override={"*": {"confidence": 0.6, "margin": 0.0}},
    )
    row = result["rows"][0]

    assert row["subtype_raw_route"] == "ask_clarifying_question"
    assert row["actual_route"] == "ask_clarifying_question"
    assert row["family_mismatch"] is True
    assert row["missed_action_reason"] == "threshold_too_strict"
    assert result["metrics"]["false_direct_actions_total"] == 0
    assert row["subtype_provider_result"]["classifier_metadata"]["stage1b_threshold_override"]["*"]["confidence"] == 0.6
