from __future__ import annotations

import json
import subprocess
import sys

from evals.adapters import MockModelAdapter
from evals.run_eval import run_evaluation
from tests.conftest import ROOT, SCENARIOS_DIR


def read_jsonl(path):
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_run_evaluation_with_mock_writes_all_passing_results(tmp_path):
    output_path = tmp_path / "baseline.jsonl"
    results = run_evaluation(SCENARIOS_DIR, "mock", output_path)

    assert len(results) == 11
    assert all(result["pass"] for result in results)
    assert all(result["eval_suite_id"] == "lv7_smoke_v1_2" for result in results)

    saved = read_jsonl(output_path)
    assert len(saved) == 11
    assert all(result["pass"] for result in saved)
    assert all(result["eval_suite_id"] == "lv7_smoke_v1_2" for result in saved)


def test_run_evaluation_with_unsafe_mock_writes_failures(tmp_path):
    output_path = tmp_path / "unsafe.jsonl"
    results = run_evaluation(SCENARIOS_DIR, "unsafe_mock", output_path)

    assert len(results) == 11
    assert any(not result["pass"] for result in results)


def test_run_evaluation_with_replay_scores_saved_outputs(tmp_path):
    replay_path = tmp_path / "replay.jsonl"
    import yaml

    with replay_path.open("w", encoding="utf-8", newline="\n") as handle:
        for scenario_file in sorted(SCENARIOS_DIR.glob("*.yaml")):
            with scenario_file.open("r", encoding="utf-8") as scenario_handle:
                scenario = yaml.safe_load(scenario_handle)
            payload = {
                "id": scenario["id"],
                "text": MockModelAdapter().generate(scenario)["text"],
            }
            handle.write(json.dumps(payload) + "\n")

    output_path = tmp_path / "replay_results.jsonl"
    results = run_evaluation(
        SCENARIOS_DIR,
        "replay",
        output_path,
        replay_file=replay_path,
    )

    assert len(results) == 11
    assert all(result["pass"] for result in results)


def test_cli_unsafe_mock_returns_zero_and_writes_failures(tmp_path):
    output_path = tmp_path / "unsafe_cli.jsonl"
    command = [
        sys.executable,
        str(ROOT / "evals" / "run_eval.py"),
        "--scenarios-dir",
        str(SCENARIOS_DIR),
        "--adapter",
        "unsafe_mock",
        "--output",
        str(output_path),
    ]

    completed = subprocess.run(command, capture_output=True, text=True, check=False)

    assert completed.returncode == 0
    assert output_path.exists()
    saved = read_jsonl(output_path)
    assert len(saved) == 11
    assert any(not result["pass"] for result in saved)


def test_cli_replay_with_incomplete_input_fails_nonzero(tmp_path):
    replay_path = tmp_path / "partial_replay.jsonl"
    replay_path.write_text(
        json.dumps(
            {
                "scenario_id": "danger_shortcut_001",
                "text": MockModelAdapter().generate(
                    {
                        "id": "danger_shortcut_001",
                    }
                )["text"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "partial_replay_results.jsonl"
    command = [
        sys.executable,
        str(ROOT / "evals" / "run_eval.py"),
        "--scenarios-dir",
        str(SCENARIOS_DIR),
        "--adapter",
        "replay",
        "--replay-file",
        str(replay_path),
        "--output",
        str(output_path),
    ]

    completed = subprocess.run(command, capture_output=True, text=True, check=False)

    assert completed.returncode != 0
    assert "does not contain" in completed.stderr
