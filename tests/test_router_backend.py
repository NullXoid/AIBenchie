from __future__ import annotations

from evals import router_backend
from evals.router_backend import (
    HFTransformersRouterBackend,
    OpenAICompatibleRouterBackend,
    ProviderResult,
    RouterGenerationOptions,
    parse_backend_model_spec,
)


def test_router_generation_options_are_deterministic():
    options = RouterGenerationOptions()

    assert options.to_dict() == {
        "temperature": 0.0,
        "top_p": 1.0,
        "max_new_tokens": 8,
        "stream": False,
        "stop": ["\n"],
        "thinking_disabled": True,
    }


def test_provider_result_serializes_common_shape():
    result = ProviderResult(
        text="answer.question",
        backend="hf_transformers",
        model="LiquidAI/LFM2-1.2B-Tool",
        device="cuda",
        dtype="float16",
        quantization=None,
        latency_ms=123,
        tokens_generated=3,
        tokens_per_second=24.3,
        stop_enforced=True,
    )

    payload = result.to_dict()

    assert payload["text"] == "answer.question"
    assert payload["backend"] == "hf_transformers"
    assert payload["backend_misconfigured"] is False
    assert payload["stop_enforced"] is True


def test_backend_model_spec_parsing():
    assert parse_backend_model_spec("hf:LiquidAI/LFM2-1.2B-Tool") == (
        "hf_transformers",
        "LiquidAI/LFM2-1.2B-Tool",
    )
    assert parse_backend_model_spec("vllm_openai:Salesforce/xLAM-2-1b-fc-r") == (
        "vllm_openai",
        "Salesforce/xLAM-2-1b-fc-r",
    )
    assert parse_backend_model_spec("gemma3:1b") == ("ollama", "gemma3:1b")


def test_openai_backend_sends_router_generation_settings(monkeypatch):
    calls = []

    def fake_http_json(url, payload, timeout_seconds, headers=None):
        calls.append((url, payload, timeout_seconds, headers))
        return {
            "choices": [{"message": {"content": "answer.question"}}],
            "usage": {"completion_tokens": 2},
        }

    monkeypatch.setattr(router_backend, "_http_json", fake_http_json)
    backend = OpenAICompatibleRouterBackend(
        "vllm_openai",
        "router-model",
        options=RouterGenerationOptions(),
        base_url="http://127.0.0.1:8001/v1",
    )

    result = backend.generate("system", "user", "route_label")

    payload = calls[0][1]
    assert payload["temperature"] == 0.0
    assert payload["top_p"] == 1.0
    assert payload["max_tokens"] == 8
    assert payload["stream"] is False
    assert payload["stop"] == ["\n"]
    assert result.stop_enforced is True
    assert result.tokens_generated == 2


class FakeTensor:
    def __init__(self, length: int) -> None:
        self.shape = (1, length)

    def to(self, _device):
        return self


class FakeGeneratedIds:
    shape = (2,)


class FakeSequence:
    def __getitem__(self, item):
        if isinstance(item, slice):
            return FakeGeneratedIds()
        return 0


class FakeTokenizer:
    eos_token_id = 0

    @classmethod
    def from_pretrained(cls, *_args, **_kwargs):
        return cls()

    def apply_chat_template(self, *_args, **_kwargs):
        return "templated"

    def __call__(self, *_args, **_kwargs):
        return {"input_ids": FakeTensor(3)}

    def decode(self, *_args, **_kwargs):
        return "answer.question"


class FakeModel:
    device = "cpu"

    @classmethod
    def from_pretrained(cls, *_args, **_kwargs):
        return cls()

    def eval(self):
        return None

    def generate(self, **_kwargs):
        return [FakeSequence()]


class FakeInferenceMode:
    def __enter__(self):
        return None

    def __exit__(self, *_args):
        return False


class FakeCuda:
    @staticmethod
    def is_available():
        return False


class FakeTorch:
    cuda = FakeCuda()
    float16 = "float16"
    float32 = "float32"

    @staticmethod
    def inference_mode():
        return FakeInferenceMode()


def test_hf_expected_cuda_cpu_marks_backend_misconfigured():
    backend = HFTransformersRouterBackend(
        "fake/model",
        options=RouterGenerationOptions(),
        expected_cuda=True,
        torch_module=FakeTorch(),
        auto_tokenizer=FakeTokenizer,
        auto_model=FakeModel,
    )

    result = backend.generate("system", "user", "route_label")

    assert result.text == "answer.question"
    assert result.device == "cpu"
    assert result.stop_enforced is False
    assert result.backend_misconfigured is True
