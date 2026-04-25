from __future__ import annotations

import json

import pytest

from evals.adapters import FileReplayAdapter, MockModelAdapter, UnsafeMockModelAdapter
from tests.conftest import SCENARIOS_DIR


def load_scenario(name: str):
    import yaml

    with (SCENARIOS_DIR / f"{name}.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_mock_adapter_returns_rationale_formatted_output():
    scenario = load_scenario("danger_shortcut_001")
    result = MockModelAdapter().generate(scenario)

    assert result["adapter"] == "mock"
    assert result["text"].startswith("policy_rationale:\n")


def test_unsafe_mock_adapter_returns_intentionally_unsafe_output():
    scenario = load_scenario("danger_shortcut_001")
    result = UnsafeMockModelAdapter().generate(scenario)

    assert result["adapter"] == "unsafe_mock"
    assert "Deploying now" in result["text"]


def test_file_replay_adapter_loads_by_scenario_id(tmp_path):
    replay_path = tmp_path / "replay.jsonl"
    payload = {
        "scenario_id": "gs_001_danger_shortcut",
        "text": "policy_rationale:\n  mode: challenge\n  risk_assessment: x\n  authority_boundary: y\n  safe_next_move: z\n\nresponse:\nexample",
        "metadata": {"source": "replay"},
    }
    replay_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    adapter = FileReplayAdapter(replay_path)
    scenario = load_scenario("danger_shortcut_001")
    result = adapter.generate(scenario)

    assert result["adapter"] == "replay"
    assert result["metadata"]["source"] == "replay"


def test_file_replay_adapter_errors_when_missing(tmp_path):
    replay_path = tmp_path / "replay.jsonl"
    replay_path.write_text("", encoding="utf-8")

    adapter = FileReplayAdapter(replay_path)
    scenario = load_scenario("danger_shortcut_001")

    with pytest.raises(KeyError):
        adapter.generate(scenario)
