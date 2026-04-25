from __future__ import annotations

import json

import pytest

from aibenchie.local_ollama import (
    DEFAULT_OLLAMA_URL,
    MAX_PREDICT_TOKENS,
    benchmark_ollama_model,
    format_model_details,
    is_allowed_ollama_url,
    list_ollama_models,
    ollama_json,
)


def test_ollama_url_guard_allows_only_local_http():
    assert is_allowed_ollama_url(DEFAULT_OLLAMA_URL)
    assert is_allowed_ollama_url("http://localhost:11434")
    assert is_allowed_ollama_url("http://[::1]:11434")

    assert not is_allowed_ollama_url("https://localhost:11434")
    assert not is_allowed_ollama_url("http://192.0.2.10:11434")
    assert not is_allowed_ollama_url("http://example.invalid:11434")


def test_ollama_json_rejects_remote_hosts_before_network():
    with pytest.raises(ValueError, match="localhost Ollama"):
        ollama_json("http://example.invalid:11434", "/api/tags")


def test_list_ollama_models_normalizes_bad_payload(monkeypatch):
    def fake_ollama_json(base_url: str, path: str, payload: dict | None = None, timeout: int = 5) -> dict:
        return {"models": "not-a-list"}

    monkeypatch.setattr("aibenchie.local_ollama.ollama_json", fake_ollama_json)
    assert list_ollama_models() == []


def test_benchmark_ollama_model_uses_bounded_non_streaming_request(monkeypatch):
    captured = {}

    def fake_ollama_json(base_url: str, path: str, payload: dict | None = None, timeout: int = 5) -> dict:
        captured["base_url"] = base_url
        captured["path"] = path
        captured["payload"] = json.loads(json.dumps(payload))
        captured["timeout"] = timeout
        return {"response": "local check passed", "eval_count": 3}

    monkeypatch.setattr("aibenchie.local_ollama.ollama_json", fake_ollama_json)
    result = benchmark_ollama_model(DEFAULT_OLLAMA_URL, "tiny-model", "hello" * 200)

    assert captured["path"] == "/api/generate"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["options"]["num_predict"] == MAX_PREDICT_TOKENS
    assert len(captured["payload"]["prompt"]) == 500
    assert result["model"] == "tiny-model"
    assert result["response"] == "local check passed"


def test_format_model_details_keeps_public_safe_model_metadata():
    rows = format_model_details(
        [
            {
                "name": "model-a",
                "size": 1048576,
                "details": {
                    "family": "llama",
                    "parameter_size": "1B",
                    "quantization_level": "Q4",
                },
            }
        ]
    )

    assert rows == [
        {
            "model": "model-a",
            "family": "llama",
            "parameters": "1B",
            "quantization": "Q4",
            "size_mb": 1.0,
        }
    ]
