from __future__ import annotations

from evals import router_backend
from evals.router_backend import (
    EmbeddingClassifierRouterBackend,
    EncoderStage0RouterBackend,
    HFTransformersRouterBackend,
    OpenAICompatibleRouterBackend,
    ProviderResult,
    RouterGenerationOptions,
    _apply_stop_sequences,
    parse_backend_model_spec,
)
from training import router_embedding_classifier


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


def test_apply_stop_sequences_trims_at_earliest_configured_stop():
    assert _apply_stop_sequences("R01 answer.question", ("\n", " ", "=")) == "R01"
    assert _apply_stop_sequences("R08=console.run_command", ("\n", " ", "=")) == "R08"
    assert _apply_stop_sequences("R12", ("\n", " ", "=")) == "R12"


def test_backend_model_spec_parsing():
    assert parse_backend_model_spec("classifier:models/classifiers/router.joblib") == (
        "embedding_classifier",
        "models/classifiers/router.joblib",
    )
    assert parse_backend_model_spec("hf:LiquidAI/LFM2-1.2B-Tool") == (
        "hf_transformers",
        "LiquidAI/LFM2-1.2B-Tool",
    )
    assert parse_backend_model_spec("vllm_openai:Salesforce/xLAM-2-1b-fc-r") == (
        "vllm_openai",
        "Salesforce/xLAM-2-1b-fc-r",
    )
    assert parse_backend_model_spec("encoder_stage0:models/encoders/router_stage0") == (
        "encoder_stage0",
        "models/encoders/router_stage0",
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


class FakeRouteCodeTokenizer(FakeTokenizer):
    def decode(self, *_args, **_kwargs):
        return "R01 answer.question"


class FakeModel:
    device = "cpu"

    @classmethod
    def from_pretrained(cls, *_args, **_kwargs):
        return cls()

    def eval(self):
        return None

    def generate(self, **_kwargs):
        return [FakeSequence()]


class FakePeftModel:
    @staticmethod
    def from_pretrained(model, adapter_path):
        model.adapter_path = adapter_path
        return model


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


class FakeClassifierEncoder:
    def __init__(self, _model):
        pass

    def encode(self, *_args, **_kwargs):
        return [[1.0, 0.0]]


class FakeProbabilityClassifier:
    classes_ = ["R08", "R01"]

    @staticmethod
    def predict_proba(_embedding):
        return [[0.97, 0.03]]


def fake_classifier_artifact(_path):
    return {
        "artifact_type": "embedding_classifier_router",
        "version": 1,
        "metadata": {
            "embedding_model": "fake/encoder",
            "classifier_type": "logistic_regression",
            "routing_mode": "flat_15_class",
            "context_mode": "text_only",
            "thresholds": router_embedding_classifier.ClassifierThresholds().to_dict(),
            "class_labels": ["R08", "R01"],
            "route_codes": dict(router_embedding_classifier.ROUTE_CODES),
            "risky_route_codes": sorted(router_embedding_classifier.RISKY_ROUTE_CODES),
            "safe_stage_codes": sorted(router_embedding_classifier.SAFE_STAGE_CODES),
            "train_data_hash": "hash",
            "train_count": 2,
        },
        "models": {"flat": FakeProbabilityClassifier()},
    }


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
    assert result.stop_enforced is True
    assert result.backend_misconfigured is True


def test_hf_backend_enforces_configured_stop_sequences():
    backend = HFTransformersRouterBackend(
        "fake/model",
        options=RouterGenerationOptions(max_new_tokens=4, stop=("\n", " ", "=")),
        torch_module=FakeTorch(),
        auto_tokenizer=FakeRouteCodeTokenizer,
        auto_model=FakeModel,
    )

    result = backend.generate("system", "user", "route_code")

    assert result.text == "R01"
    assert result.stop_enforced is True


def test_hf_backend_loads_peft_adapter_metadata():
    backend = HFTransformersRouterBackend(
        "fake/model",
        options=RouterGenerationOptions(),
        adapter_path="models/adapters/router_lora_r08_boundary_v1",
        torch_module=FakeTorch(),
        auto_tokenizer=FakeTokenizer,
        auto_model=FakeModel,
        peft_model=FakePeftModel,
    )

    result = backend.generate("system", "user", "route_code")

    assert getattr(backend.model_obj, "adapter_path") == "models/adapters/router_lora_r08_boundary_v1"
    assert result.adapter_path == "models/adapters/router_lora_r08_boundary_v1"


def test_embedding_classifier_backend_returns_exact_code_and_metadata():
    backend = EmbeddingClassifierRouterBackend(
        "models/classifiers/router.joblib",
        artifact_loader=fake_classifier_artifact,
        encoder_factory=FakeClassifierEncoder,
    )

    result = backend.generate("ignored", "Run tests now.", "route_code")

    assert result.text == "R08"
    assert result.backend == "embedding_classifier"
    assert result.stop_enforced is True
    assert result.classifier_metadata["embedding_model"] == "fake/encoder"
    assert result.classifier_metadata["last_prediction"]["code"] == "R08"


def test_encoder_stage0_backend_returns_gate_and_metadata():
    def fake_loader(_path):
        return {
            "artifact_type": "encoder_stage0_classifier",
            "metadata": {
                "model_id": "fake/encoder-stage0",
                "context_mode": "text_only",
                "stage0_thresholds": {},
            },
        }

    backend = EncoderStage0RouterBackend(
        "models/encoders/router_stage0/fake",
        artifact_loader=fake_loader,
    )
    backend._predict_encoder_stage0 = lambda _artifact, _text, context_flags=None: router_embedding_classifier.RouterPrediction(
        "G04",
        0.99,
        0.50,
        "G04",
        False,
        "encoder_stage0",
        "stage0",
    )

    result = backend.generate_with_context(
        "ignored",
        "Run tests now.",
        "route_code",
        context_flags={"HAS_IMAGE": "unknown"},
    )

    assert result.text == "G04"
    assert result.backend == "encoder_stage0"
    assert result.stop_enforced is True
    assert result.classifier_metadata["model_id"] == "fake/encoder-stage0"
    assert result.classifier_metadata["last_prediction"]["code"] == "G04"
