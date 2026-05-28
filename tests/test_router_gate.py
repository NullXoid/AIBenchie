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


def test_protocol_200_case_builder_is_unique_and_balanced():
    cases = router_gate.build_cases(router_gate.SPLIT_200)

    assert len(cases) == 200
    assert len({case["text"] for case in cases}) == 200
    assert sum(1 for case in cases if case["category"] == "hard_negative") == 50
    assert any(case["expected_route"] == "memory.save_preference" for case in cases)


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


def test_protocol_200_pass_loader(tmp_path: Path):
    path = tmp_path / "protocol200.json"
    path.write_text(
        '{"results":[{"metrics":{"protocol_validity":0.995,"backend_misconfigured":false}}]}',
        encoding="utf-8",
    )

    assert router_gate.load_protocol_200_pass(path) is True
