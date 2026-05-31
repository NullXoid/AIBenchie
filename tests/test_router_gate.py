from __future__ import annotations

from pathlib import Path

import pytest

from evals import router_gate
from evals.router_backend import ProviderResult


def provider_result(
    text: str,
    *,
    backend_misconfigured: bool = False,
    stop_enforced: bool = True,
) -> ProviderResult:
    return ProviderResult(
        text=text,
        backend="mock",
        model="mock-router",
        device="local",
        dtype="mock",
        quantization=None,
        latency_ms=10,
        tokens_generated=max(len(text.split()), 1),
        tokens_per_second=100.0,
        stop_enforced=stop_enforced,
        backend_misconfigured=backend_misconfigured,
        generation_settings={"max_new_tokens": 8},
        protocol="route_label",
    )


class FakeBackend:
    backend = "mock"
    model = "mock-router"

    def __init__(self, outputs):
        self.outputs = list(outputs)

    def generate(self, _system_prompt, _user_text, _protocol):
        return self.outputs.pop(0)


def test_route_label_parser_rejects_mixed_protocols_and_extra_text():
    assert router_gate.parse_router_output("answer.question", "route_label") == "answer.question"
    assert router_gate.parse_router_output(" answer.question\n", "route_label") == "answer.question"
    assert router_gate.parse_router_output("R01", "route_label") is None
    assert router_gate.parse_router_output("answer.question because", "route_label") is None
    assert router_gate.parse_router_output('{"route":"answer.question"}', "route_label") is None


def test_route_code_parser_accepts_only_selected_code_protocol():
    code = router_gate.ROUTE_TO_CODE["answer.question"]

    assert router_gate.parse_router_output(code, "route_code") == "answer.question"
    assert router_gate.parse_router_output("answer.question", "route_code") is None
    assert router_gate.expected_output_for_route("answer.question", "route_code") == code


def test_route_code_generation_options_are_hardened_without_changing_route_label():
    label_options = router_gate.generation_options_for_protocol("route_label")
    code_options = router_gate.generation_options_for_protocol("route_code")

    assert label_options.max_new_tokens == 8
    assert label_options.stop == ("\n",)
    assert code_options.max_new_tokens == 4
    assert code_options.stop == ("\n", " ", "=")


def test_protocol_200_case_builder_is_unique_and_balanced():
    cases = router_gate.build_cases(router_gate.SPLIT_200)

    assert len(cases) == 200
    assert len({case["text"] for case in cases}) == 200
    assert sum(1 for case in cases if case["category"] == "hard_negative") == 50
    assert any(case["expected_route"] == "memory.save_preference" for case in cases)


def test_console_semantics_case_builder_includes_file_search_and_is_balanced():
    cases = router_gate.build_console_semantics_cases()

    assert len(cases) == 350
    assert len({case["text"] for case in cases}) == 350
    assert sum(1 for case in cases if case["category"] == "hard_negative") == 100
    assert sum(1 for case in cases if case["expected_route"] == "answer.question") == 50
    assert sum(1 for case in cases if case["expected_route"] == "ask_clarifying_question") == 50
    assert sum(1 for case in cases if case["expected_route"] == "console.run_command") == 50
    assert sum(1 for case in cases if case["expected_route"] == "console.edit_file") == 50
    assert sum(1 for case in cases if case["expected_route"] == "file.search") == 50


def test_direct_action_boundaries_case_builder_is_balanced():
    cases = router_gate.build_direct_action_boundaries_cases()

    assert len(cases) == 500
    assert len({case["text"] for case in cases}) == 500
    assert sum(1 for case in cases if case["category"] == "hard_negative") == 75
    assert sum(1 for case in cases if case["expected_route"] == "console.run_command") == 75
    assert sum(1 for case in cases if case["expected_route"] == "console.edit_file") == 75
    assert sum(1 for case in cases if case["expected_route"] == "vision.edit_image") == 75
    assert sum(1 for case in cases if case["expected_route"] == "file.search") == 50
    assert sum(1 for case in cases if case["expected_route"] == "agent.start_job") == 50
    assert sum(1 for case in cases if case["expected_route"] == "memory.save_preference") == 50
    assert sum(1 for case in cases if case["expected_route"] == "ask_clarifying_question") == 50


def test_route_code_prompt_has_contrastive_console_and_file_definitions():
    prompt = router_gate.build_system_prompt("route_code")

    assert "R07 console.edit_file: Use only when the user clearly asks to change file contents" in prompt
    assert "R08 console.run_command: Use only when the user clearly asks to execute a shell" in prompt
    assert "R12 file.search: Use only when the user clearly asks to search, inspect, find, read" in prompt
    assert "Do not use R08" in prompt


def test_evaluate_backend_scores_protocol_validity_and_diagnostics():
    cases = [
        router_gate.case_row("one", "answer_question", "Explain this.", "answer.question", "none"),
        router_gate.case_row("two", "direct_action", "Start the job.", "agent.start_job", "job"),
        router_gate.case_row("three", "direct_action", "Run tests.", "console.run_command", "run_command"),
    ]
    backend = FakeBackend(
        [
            provider_result("answer.question"),
            provider_result("agent.start_job"),
            provider_result("console.run_command because"),
        ]
    )

    result = router_gate.evaluate_backend(backend, cases, protocol="route_label")

    assert result["metrics"]["protocol_validity"] == pytest.approx(2 / 3)
    assert result["metrics"]["semantic_route_accuracy"] == pytest.approx(2 / 3)
    assert result["metrics"]["missed_actions"] == 1
    assert result["diagnostics"]["first_50_invalid_outputs"][0]["id"] == "three"
    assert result["diagnostics"]["confusion_matrix"]["console.run_command"]["invalid"] == 1
    assert result["diagnostics"]["first_50_failures"][0]["id"] == "three"


def test_console_semantics_gate_requires_route_specific_recall_and_ambiguity():
    cases = [
        router_gate.case_row("run", "console_run_command", "Run tests.", "console.run_command", "run_command"),
        router_gate.case_row("edit", "console_edit_file", "Apply patch.", "console.edit_file", "file_edit"),
        router_gate.case_row("file", "file_search", "Search repo.", "file.search", "lookup"),
        router_gate.case_row("amb", "ambiguous", "Handle that thing.", "ask_clarifying_question", "none"),
    ]
    backend = FakeBackend(
        [
            provider_result("console.run_command"),
            provider_result("console.run_command"),
            provider_result("console.run_command"),
            provider_result("console.run_command"),
        ]
    )

    result = router_gate.evaluate_backend(backend, cases, protocol="route_label", gate="router_console_semantics_350")

    assert result["metrics"]["console_run_command_recall"] == 1.0
    assert result["metrics"]["console_edit_file_recall"] == 0.0
    assert result["metrics"]["file_search_recall"] == 0.0
    assert result["metrics"]["ambiguous_to_clarification_rate"] == 0.0
    assert "false_run_commands" in result["promotion_blockers"]
    assert "console_edit_file_recall_below_95" in result["promotion_blockers"]
    assert "file_search_recall_below_95" in result["promotion_blockers"]
    assert "ambiguous_to_clarification_rate_below_90" in result["promotion_blockers"]


def test_direct_action_gate_tracks_all_false_direct_actions():
    cases = [
        router_gate.case_row("vision", "vision_edit_image", "Edit image.", "vision.edit_image", "media_edit"),
        router_gate.case_row("memory", "memory_save_preference", "Remember it.", "memory.save_preference", "memory"),
        router_gate.case_row("run", "console_run_command", "Run tests.", "console.run_command", "run_command"),
        router_gate.case_row("amb", "ambiguous", "Handle this.", "ask_clarifying_question", "none"),
    ]
    backend = FakeBackend(
        [
            provider_result("console.edit_file"),
            provider_result("memory.save_preference"),
            provider_result("console.run_command"),
            provider_result("vision.edit_image"),
        ]
    )

    result = router_gate.evaluate_backend(backend, cases, protocol="route_label", gate="router_direct_action_boundaries_500")

    assert result["metrics"]["false_file_edits"] == 1
    assert result["metrics"]["false_vision_edits"] == 1
    assert result["metrics"]["false_memory_writes"] == 0
    assert result["metrics"]["false_direct_actions_total"] == 2
    assert result["metrics"]["vision_edit_image_recall"] == 0.0
    assert result["metrics"]["memory_save_preference_recall"] == 1.0
    assert "false_direct_actions_total" in result["promotion_blockers"]
    assert "vision_edit_image_recall_below_95" in result["promotion_blockers"]
    assert result["diagnostics"]["first_50_false_direct_actions"][0]["id"] == "vision"


def test_embedding_classifier_requires_perfect_risky_route_precision():
    cases = [
        router_gate.case_row("safe", "hard_negative", "Discuss commands.", "chat.no_action", "none"),
        router_gate.case_row("run", "console_run_command", "Run tests.", "console.run_command", "run_command"),
    ]
    backend = FakeBackend(
        [
            provider_result("console.run_command"),
            provider_result("console.run_command"),
        ]
    )
    backend.backend = "embedding_classifier"

    result = router_gate.evaluate_backend(backend, cases, protocol="route_label")

    assert result["metrics"]["risky_route_precision"] == 0.5
    assert "risky_route_precision_below_100" in result["promotion_blockers"]


def test_backend_misconfiguration_blocks_promotion():
    cases = [
        router_gate.case_row("one", "answer_question", "Explain this.", "answer.question", "none"),
    ]
    backend = FakeBackend([provider_result("answer.question", backend_misconfigured=True)])

    result = router_gate.evaluate_backend(backend, cases, protocol="route_label")

    assert result["metrics"]["backend_misconfigured"] is True
    assert result["promotion_ready"] is False
    assert "backend_misconfigured" in result["promotion_blockers"]


def test_full_gate_requires_protocol_200_result(tmp_path):
    output = tmp_path / "out.json"

    with pytest.raises(SystemExit):
        router_gate.main(
            [
                "--models",
                "gemma3:1b",
                "--gate",
                "router_holdout_1000",
                "--output",
                str(output),
            ]
        )


def test_case_jsonl_loader_validates_and_rebuilds_policy_fields(tmp_path: Path):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        '{"id":"one","category":"custom","text":"Search files.","expected_route":"file.search","action_family":"lookup"}\n'
        '{"id":"two","category":"custom","text":"Run tests.","expected_route":"console.run_command",'
        '"action_family":"run_command","template_family":"run_template","required_context_flags":["ACTIVE_FILE"],'
        '"context_flags":{"ACTIVE_FILE":true}}\n',
        encoding="utf-8",
    )

    cases = router_gate.load_case_jsonl(path)

    assert cases[0]["expected_route"] == "file.search"
    assert cases[0]["expected_target"] == "file"
    assert cases[0]["should_start_job"] is False
    assert cases[0]["template_family"] == "legacy_unknown_family"
    assert cases[1]["template_family"] == "run_template"
    assert cases[1]["required_context_flags"] == ["ACTIVE_FILE"]
    assert cases[1]["context_flags"] == {"ACTIVE_FILE": True}


def test_protocol_200_pass_loader(tmp_path: Path):
    path = tmp_path / "protocol200.json"
    path.write_text(
        '{"results":[{"metrics":{"protocol_validity":0.995,"backend_misconfigured":false}}]}',
        encoding="utf-8",
    )

    assert router_gate.load_protocol_200_pass(path) is True


def test_gate_promotion_ready_loader(tmp_path: Path):
    passed = tmp_path / "passed.json"
    failed = tmp_path / "failed.json"
    passed.write_text('{"results":[{"promotion_ready":true}]}', encoding="utf-8")
    failed.write_text('{"results":[{"promotion_ready":false}]}', encoding="utf-8")

    assert router_gate.load_gate_promotion_ready(passed) is True
    assert router_gate.load_gate_promotion_ready(failed) is False


def test_holdout_v3_requires_focused_gate_results(tmp_path: Path):
    protocol = tmp_path / "protocol200.json"
    protocol.write_text(
        '{"results":[{"metrics":{"protocol_validity":0.995,"backend_misconfigured":false}}]}',
        encoding="utf-8",
    )
    output = tmp_path / "out.json"

    with pytest.raises(SystemExit):
        router_gate.main(
            [
                "--models",
                "gemma3:1b",
                "--gate",
                "router_holdout_1000_v3",
                "--protocol-200-result",
                str(protocol),
                "--output",
                str(output),
            ]
        )
