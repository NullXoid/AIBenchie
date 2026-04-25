from __future__ import annotations

from evals.adapters import MockModelAdapter, UnsafeMockModelAdapter
from evals.scoring import score_response
from tests.conftest import SCENARIOS_DIR


def load_scenario(name: str):
    import yaml

    with (SCENARIOS_DIR / f"{name}.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_scoring_passes_for_mock_output():
    scenario = load_scenario("mape_recovery_001")
    text = MockModelAdapter().generate(scenario)["text"]
    scored = score_response(scenario, text)

    assert scored["score"]["policy_rationale_present"] is True
    assert scored["score"]["mode_match"] is True
    assert scored["score"]["authority_boundary_present"] is True
    assert scored["score"]["safe_next_move_present"] is True
    assert scored["score"]["pass"] is True


def test_scoring_fails_for_unsafe_output():
    scenario = load_scenario("shutdown_conflict_001")
    text = UnsafeMockModelAdapter().generate(scenario)["text"]
    scored = score_response(scenario, text)

    assert scored["score"]["policy_rationale_present"] is False
    assert scored["score"]["mode_match"] is False
    assert scored["score"]["pass"] is False
    assert scored["score"]["notes"] in {
        "missing policy_rationale block",
        "mode mismatch",
    }


def test_scoring_passes_for_low_risk_execute_output():
    scenario = load_scenario("low_risk_readonly_001")
    text = MockModelAdapter().generate(scenario)["text"]
    scored = score_response(scenario, text)

    assert scored["score"]["policy_rationale_present"] is True
    assert scored["score"]["mode_match"] is True
    assert scored["score"]["pass"] is True


def test_scoring_fails_for_overdefensive_low_risk_output():
    scenario = load_scenario("model_invoke_safe_001")
    text = UnsafeMockModelAdapter().generate(scenario)["text"]
    scored = score_response(scenario, text)

    assert scored["score"]["pass"] is False
    assert scored["score"]["notes"] in {
        "missing policy_rationale block",
        "mode mismatch",
        "missing risk_assessment",
    }
