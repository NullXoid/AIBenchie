from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
MAX_PROMPT_CHARS = 500
MAX_PREDICT_TOKENS = 128
REQUEST_TIMEOUT_SECONDS = 45
ALLOWED_LOCAL_OLLAMA_HOSTS = {"127.0.0.1", "localhost", "::1"}


def is_allowed_ollama_url(base_url: str) -> bool:
    parsed = urllib.parse.urlparse(base_url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "http" and host in ALLOWED_LOCAL_OLLAMA_HOSTS


def ollama_json(base_url: str, path: str, payload: dict | None = None, timeout: int = 5) -> dict:
    if not is_allowed_ollama_url(base_url):
        raise ValueError("AIBenchie only probes localhost Ollama. Use a local runner or NullBridge adapter for remote backends.")

    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    data = None
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"

    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/json")
    if payload is not None:
        request.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def list_ollama_models(base_url: str = DEFAULT_OLLAMA_URL) -> list[dict]:
    data = ollama_json(base_url, "/api/tags")
    models = data.get("models", [])
    return models if isinstance(models, list) else []


def model_name(model: dict) -> str:
    return str(model.get("name") or model.get("model") or "")


def format_model_details(models: list[dict]) -> list[dict]:
    rows = []
    for item in models:
        details = item.get("details") or {}
        rows.append(
            {
                "model": model_name(item),
                "family": details.get("family", ""),
                "parameters": details.get("parameter_size", ""),
                "quantization": details.get("quantization_level", ""),
                "size_mb": round(int(item.get("size") or 0) / 1024 / 1024, 1),
            }
        )
    return rows


def benchmark_ollama_model(base_url: str, model: str, prompt: str) -> dict:
    prompt = prompt.strip()[:MAX_PROMPT_CHARS]
    if not model:
        raise ValueError("Select a model before running a benchmark.")
    if not prompt:
        raise ValueError("Enter a short prompt before running a benchmark.")

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": MAX_PREDICT_TOKENS,
        },
    }
    started = time.perf_counter()
    data = ollama_json(base_url, "/api/generate", payload=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    elapsed = max(time.perf_counter() - started, 0.001)
    output = str(data.get("response") or "")
    eval_count = int(data.get("eval_count") or max(len(output.split()), 1))
    return {
        "model": model,
        "elapsed_seconds": round(elapsed, 2),
        "tokens": eval_count,
        "tokens_per_second": round(eval_count / elapsed, 2),
        "response": output,
    }
