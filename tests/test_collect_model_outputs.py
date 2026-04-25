from __future__ import annotations

import json

import pytest

from evals import collect_model_outputs
from tests.conftest import SCENARIOS_DIR


def read_jsonl(path):
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_build_messages_raw_mode_has_single_user_message():
    messages = collect_model_outputs.build_messages("raw", "Example prompt")

    assert messages == [{"role": "user", "content": "Example prompt"}]


def test_build_messages_lv7_mode_includes_exact_system_prompt_markers():
    messages = collect_model_outputs.build_messages("lv7", "Example prompt")

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "policy_rationale" in messages[0]["content"]
    assert "authority_boundary" in messages[0]["content"]
    assert "Do not self-extend privileges" in messages[0]["content"]


def test_output_jsonl_shape_and_metadata(monkeypatch, tmp_path):
    def fake_request(*args, **kwargs):
        return {"choices": [{"message": {"content": "Collected response"}}]}

    monkeypatch.setattr(
        collect_model_outputs, "request_chat_completion", fake_request
    )

    output_path = tmp_path / "collected.jsonl"
    records = collect_model_outputs.collect_outputs(
        scenarios_dir=SCENARIOS_DIR,
        provider="ollama_openai",
        model="gemma3:1b",
        prompt_mode="raw",
        output_path=output_path,
        base_url="http://localhost:11434/v1",
        temperature=0,
        max_tokens=700,
        timeout_seconds=120,
        overwrite=True,
    )

    assert len(records) == 11
    saved = read_jsonl(output_path)
    first = saved[0]
    assert "scenario_id" in first
    assert "text" in first
    assert first["metadata"]["model"] == "gemma3:1b"
    assert first["metadata"]["provider"] == "ollama_openai"
    assert first["metadata"]["prompt_mode"] == "raw"


def test_scenario_filter_writes_exactly_one_line(monkeypatch, tmp_path):
    def fake_request(*args, **kwargs):
        return {"choices": [{"message": {"content": "Collected response"}}]}

    monkeypatch.setattr(
        collect_model_outputs, "request_chat_completion", fake_request
    )

    output_path = tmp_path / "single.jsonl"
    collect_model_outputs.collect_outputs(
        scenarios_dir=SCENARIOS_DIR,
        provider="ollama_openai",
        model="gemma3:1b",
        prompt_mode="raw",
        output_path=output_path,
        base_url="http://localhost:11434/v1",
        temperature=0,
        max_tokens=700,
        timeout_seconds=120,
        scenario_id="danger_shortcut_001",
        overwrite=True,
    )

    saved = read_jsonl(output_path)
    assert len(saved) == 1
    assert saved[0]["scenario_id"] == "danger_shortcut_001"


def test_existing_output_without_overwrite_fails(monkeypatch, tmp_path):
    output_path = tmp_path / "exists.jsonl"
    output_path.write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError):
        collect_model_outputs.collect_outputs(
            scenarios_dir=SCENARIOS_DIR,
            provider="ollama_openai",
            model="gemma3:1b",
            prompt_mode="raw",
            output_path=output_path,
            base_url="http://localhost:11434/v1",
            temperature=0,
            max_tokens=700,
            timeout_seconds=120,
        )


def test_connection_failure_exits_nonzero(monkeypatch, tmp_path):
    def fake_request(*args, **kwargs):
        raise RuntimeError("Connection failure to model endpoint: refused")

    monkeypatch.setattr(
        collect_model_outputs, "request_chat_completion", fake_request
    )

    output_path = tmp_path / "error.jsonl"
    exit_code = collect_model_outputs.main(
        [
            "--scenarios-dir",
            str(SCENARIOS_DIR),
            "--provider",
            "ollama_openai",
            "--model",
            "gemma3:1b",
            "--prompt-mode",
            "raw",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code != 0
    assert not output_path.exists()


def test_empty_message_content_exits_nonzero(monkeypatch, tmp_path):
    def fake_request(*args, **kwargs):
        return {"choices": [{"message": {"content": ""}}]}

    monkeypatch.setattr(
        collect_model_outputs, "request_chat_completion", fake_request
    )

    output_path = tmp_path / "empty.jsonl"
    exit_code = collect_model_outputs.main(
        [
            "--scenarios-dir",
            str(SCENARIOS_DIR),
            "--provider",
            "ollama_openai",
            "--model",
            "gemma3:1b",
            "--prompt-mode",
            "raw",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code != 0
    assert not output_path.exists()


def test_normalize_base_url_accepts_v1_and_completion_path():
    base, request_url = collect_model_outputs.normalize_base_url(
        "http://localhost:11434/v1"
    )
    assert base == "http://localhost:11434/v1"
    assert request_url == "http://localhost:11434/v1/chat/completions"

    base, request_url = collect_model_outputs.normalize_base_url(
        "http://localhost:11434/v1/chat/completions"
    )
    assert base == "http://localhost:11434/v1"
    assert request_url == "http://localhost:11434/v1/chat/completions"


def test_invalid_base_url_fails():
    with pytest.raises(ValueError):
        collect_model_outputs.normalize_base_url("http://localhost:11434")
