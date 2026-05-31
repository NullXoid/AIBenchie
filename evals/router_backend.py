from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol


SUPPORTED_BACKENDS = {
    "embedding_classifier",
    "encoder_stage0",
    "ollama",
    "hf_transformers",
    "vllm_openai",
    "sglang_openai",
    "llama_cpp_openai",
}
OPENAI_COMPATIBLE_BACKENDS = {"vllm_openai", "sglang_openai", "llama_cpp_openai"}
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


@dataclass(frozen=True)
class RouterGenerationOptions:
    temperature: float = 0.0
    top_p: float = 1.0
    max_new_tokens: int = 8
    stream: bool = False
    stop: tuple[str, ...] = ("\n",)
    thinking_disabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["stop"] = list(self.stop)
        return payload


@dataclass(frozen=True)
class ProviderResult:
    text: str
    backend: str
    model: str
    device: str
    dtype: str
    quantization: str | None
    latency_ms: int
    tokens_generated: int
    tokens_per_second: float
    stop_enforced: bool
    error: str | None = None
    backend_misconfigured: bool = False
    cuda_available: bool | None = None
    expected_cuda: bool = False
    gpu_name: str | None = None
    model_load_time_ms: int | None = None
    max_vram_allocated_mb: float | None = None
    max_vram_reserved_mb: float | None = None
    generation_settings: dict[str, Any] = field(default_factory=dict)
    protocol: str | None = None
    adapter_path: str | None = None
    classifier_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RouterBackend(Protocol):
    backend: str
    model: str

    def generate(self, system_prompt: str, user_text: str, protocol: str) -> ProviderResult:
        ...


def normalize_backend(value: str) -> str:
    backend = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "hf": "hf_transformers",
        "huggingface": "hf_transformers",
        "transformers": "hf_transformers",
        "vllm": "vllm_openai",
        "sglang": "sglang_openai",
        "llamacpp": "llama_cpp_openai",
        "llama.cpp": "llama_cpp_openai",
        "classifier": "embedding_classifier",
        "embedding": "embedding_classifier",
        "embedding_classifier_router": "embedding_classifier",
        "stage0_encoder": "encoder_stage0",
        "encoder": "encoder_stage0",
        "encoder_stage0_classifier": "encoder_stage0",
    }
    backend = aliases.get(backend, backend)
    if backend not in SUPPORTED_BACKENDS:
        raise ValueError(f"Unsupported router backend: {value}")
    return backend


def parse_backend_model_spec(spec: str, default_backend: str = "ollama") -> tuple[str, str]:
    text = str(spec or "").strip()
    if ":" not in text:
        return normalize_backend(default_backend), text
    prefix, model = text.split(":", 1)
    try:
        backend = normalize_backend(prefix)
    except ValueError:
        return normalize_backend(default_backend), text
    return backend, model


def _http_json(url: str, payload: dict[str, Any], timeout_seconds: int, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Connection failure to {url}: {exc}") from exc


def _tokens_per_second(tokens_generated: int, latency_ms: int) -> float:
    if latency_ms <= 0:
        return 0.0
    return round(tokens_generated / (latency_ms / 1000.0), 3)


def _apply_stop_sequences(text: str, stop: tuple[str, ...]) -> str:
    if not stop:
        return text
    cut_index: int | None = None
    for sequence in stop:
        if not sequence:
            continue
        index = text.find(sequence)
        if index >= 0 and (cut_index is None or index < cut_index):
            cut_index = index
    if cut_index is None:
        return text
    return text[:cut_index]


class OllamaRouterBackend:
    backend = "ollama"

    def __init__(
        self,
        model: str,
        options: RouterGenerationOptions | None = None,
        base_url: str = DEFAULT_OLLAMA_URL,
        timeout_seconds: int = 90,
    ) -> None:
        self.model = model
        self.options = options or RouterGenerationOptions()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(self, system_prompt: str, user_text: str, protocol: str) -> ProviderResult:
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_text,
            "stream": False,
            "options": {
                "temperature": self.options.temperature,
                "top_p": self.options.top_p,
                "num_predict": self.options.max_new_tokens,
                "stop": list(self.options.stop),
            },
        }
        if self.options.thinking_disabled:
            payload["think"] = False
        started = time.perf_counter()
        try:
            body = _http_json(f"{self.base_url}/api/generate", payload, self.timeout_seconds)
            text = str(body.get("response") or "")
            tokens = int(body.get("eval_count") or max(len(text.split()), 0))
            error = None
        except Exception as exc:
            text = ""
            tokens = 0
            error = str(exc)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return ProviderResult(
            text=text,
            backend=self.backend,
            model=self.model,
            device="local",
            dtype="ollama",
            quantization=None,
            latency_ms=latency_ms,
            tokens_generated=tokens,
            tokens_per_second=_tokens_per_second(tokens, latency_ms),
            stop_enforced=bool(self.options.stop),
            error=error,
            generation_settings=self.options.to_dict(),
            protocol=protocol,
        )


class OpenAICompatibleRouterBackend:
    def __init__(
        self,
        backend: str,
        model: str,
        options: RouterGenerationOptions | None = None,
        base_url: str = "http://127.0.0.1:8000/v1",
        api_key: str = "local",
        timeout_seconds: int = 90,
    ) -> None:
        self.backend = normalize_backend(backend)
        if self.backend not in OPENAI_COMPATIBLE_BACKENDS:
            raise ValueError(f"{backend} is not an OpenAI-compatible router backend")
        self.model = model
        self.options = options or RouterGenerationOptions()
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def generate(self, system_prompt: str, user_text: str, protocol: str) -> ProviderResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "temperature": self.options.temperature,
            "top_p": self.options.top_p,
            "max_tokens": self.options.max_new_tokens,
            "stream": False,
            "stop": list(self.options.stop),
        }
        started = time.perf_counter()
        try:
            body = _http_json(
                f"{self.base_url}/chat/completions",
                payload,
                self.timeout_seconds,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            text = str(body["choices"][0]["message"].get("content") or "")
            usage = body.get("usage") or {}
            tokens = int(usage.get("completion_tokens") or max(len(text.split()), 0))
            error = None
        except Exception as exc:
            text = ""
            tokens = 0
            error = str(exc)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return ProviderResult(
            text=text,
            backend=self.backend,
            model=self.model,
            device="local",
            dtype="openai_compatible",
            quantization=None,
            latency_ms=latency_ms,
            tokens_generated=tokens,
            tokens_per_second=_tokens_per_second(tokens, latency_ms),
            stop_enforced=bool(self.options.stop),
            error=error,
            generation_settings=self.options.to_dict(),
            protocol=protocol,
        )


class HFTransformersRouterBackend:
    backend = "hf_transformers"

    def __init__(
        self,
        model: str,
        options: RouterGenerationOptions | None = None,
        *,
        expected_cuda: bool = False,
        adapter_path: str | None = None,
        torch_module: Any | None = None,
        auto_tokenizer: Any | None = None,
        auto_model: Any | None = None,
        peft_model: Any | None = None,
    ) -> None:
        self.model = model
        self.options = options or RouterGenerationOptions()
        self.expected_cuda = expected_cuda
        self.adapter_path = adapter_path
        started = time.perf_counter()
        if torch_module is None or auto_tokenizer is None or auto_model is None:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer

            torch_module = torch
            auto_tokenizer = AutoTokenizer
            auto_model = AutoModelForCausalLM
            peft_model = PeftModel
        self.torch = torch_module
        self.cuda_available = bool(self.torch.cuda.is_available())
        self.dtype = "float16" if self.cuda_available else "float32"
        torch_dtype = self.torch.float16 if self.cuda_available else self.torch.float32
        self.tokenizer = auto_tokenizer.from_pretrained(model, trust_remote_code=True)
        try:
            model_obj = auto_model.from_pretrained(
                model,
                dtype=torch_dtype,
                device_map="auto",
                trust_remote_code=True,
            )
        except TypeError:
            model_obj = auto_model.from_pretrained(
                model,
                torch_dtype=torch_dtype,
                device_map="auto",
                trust_remote_code=True,
            )
        if adapter_path:
            if peft_model is None:
                from peft import PeftModel

                peft_model = PeftModel
            model_obj = peft_model.from_pretrained(model_obj, adapter_path)
        self.model_obj = model_obj
        if hasattr(self.model_obj, "eval"):
            self.model_obj.eval()
        self.model_load_time_ms = int((time.perf_counter() - started) * 1000)

    def _device(self) -> str:
        device = getattr(self.model_obj, "device", None)
        if device is not None:
            return str(device)
        hf_device_map = getattr(self.model_obj, "hf_device_map", None)
        if isinstance(hf_device_map, dict) and hf_device_map:
            return ",".join(sorted({str(value) for value in hf_device_map.values()}))
        return "cuda" if self.cuda_available else "cpu"

    def _gpu_name(self) -> str | None:
        if not self.cuda_available:
            return None
        try:
            return str(self.torch.cuda.get_device_name(0))
        except Exception:
            return None

    def _vram_mb(self, attr: str) -> float | None:
        if not self.cuda_available:
            return None
        try:
            return round(float(getattr(self.torch.cuda, attr)(0)) / 1024 / 1024, 2)
        except Exception:
            return None

    def _prompt(self, system_prompt: str, user_text: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
        try:
            return self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=not self.options.thinking_disabled,
            )
        except TypeError:
            try:
                return self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            except Exception:
                pass
        except Exception:
            pass
        return f"{system_prompt}\n\nUser: {user_text}\nAssistant:"

    def generate(self, system_prompt: str, user_text: str, protocol: str) -> ProviderResult:
        prompt = self._prompt(system_prompt, user_text)
        if self.cuda_available:
            try:
                self.torch.cuda.reset_peak_memory_stats()
            except Exception:
                pass
        started = time.perf_counter()
        try:
            inputs = self.tokenizer(prompt, return_tensors="pt")
            model_device = getattr(self.model_obj, "device", None)
            if model_device is not None:
                inputs = {
                    key: value.to(model_device) if hasattr(value, "to") else value
                    for key, value in inputs.items()
                }
            with self.torch.inference_mode():
                output_ids = self.model_obj.generate(
                    **inputs,
                    max_new_tokens=self.options.max_new_tokens,
                    do_sample=False,
                    pad_token_id=getattr(self.tokenizer, "eos_token_id", None),
                )
            prompt_len = inputs["input_ids"].shape[-1]
            generated_ids = output_ids[0][prompt_len:]
            decoded = str(self.tokenizer.decode(generated_ids, skip_special_tokens=True))
            text = _apply_stop_sequences(decoded, self.options.stop)
            tokens = int(getattr(generated_ids, "shape", [len(text.split())])[-1])
            error = None
        except Exception as exc:
            text = ""
            tokens = 0
            error = str(exc)
        latency_ms = int((time.perf_counter() - started) * 1000)
        device = self._device()
        return ProviderResult(
            text=text,
            backend=self.backend,
            model=self.model,
            device=device,
            dtype=self.dtype,
            quantization=None,
            latency_ms=latency_ms,
            tokens_generated=tokens,
            tokens_per_second=_tokens_per_second(tokens, latency_ms),
            stop_enforced=bool(self.options.stop),
            error=error,
            backend_misconfigured=bool(self.expected_cuda and "cuda" not in device.lower()),
            cuda_available=self.cuda_available,
            expected_cuda=self.expected_cuda,
            gpu_name=self._gpu_name(),
            model_load_time_ms=self.model_load_time_ms,
            max_vram_allocated_mb=self._vram_mb("max_memory_allocated"),
            max_vram_reserved_mb=self._vram_mb("max_memory_reserved"),
            generation_settings=self.options.to_dict(),
            protocol=protocol,
            adapter_path=self.adapter_path,
        )


class EmbeddingClassifierRouterBackend:
    backend = "embedding_classifier"

    def __init__(
        self,
        model: str,
        *,
        artifact_loader: Any | None = None,
        encoder_factory: Any | None = None,
    ) -> None:
        from training import router_embedding_classifier

        self.model = model
        self.artifact_path = Path(model)
        loader = artifact_loader or router_embedding_classifier.load_artifact
        started = time.perf_counter()
        self.artifact = loader(self.artifact_path)
        metadata = self.artifact["metadata"]
        if encoder_factory is None:
            from sentence_transformers import SentenceTransformer

            encoder_factory = SentenceTransformer
        self.encoder = encoder_factory(metadata["embedding_model"])
        self.model_load_time_ms = int((time.perf_counter() - started) * 1000)
        self._predict_route_code = router_embedding_classifier.predict_route_code
        self._predict_hybrid_label = router_embedding_classifier.predict_hybrid_label

    def generate_with_context(
        self,
        system_prompt: str,
        user_text: str,
        protocol: str,
        *,
        context_flags: dict[str, Any] | None = None,
    ) -> ProviderResult:
        started = time.perf_counter()
        try:
            if self.artifact.get("artifact_type") == "hybrid_embedding_classifier_router":
                prediction = self._predict_hybrid_label(
                    self.artifact,
                    user_text,
                    encoder=self.encoder,
                    context_flags=context_flags,
                )
            else:
                prediction = self._predict_route_code(
                    self.artifact,
                    user_text,
                    encoder=self.encoder,
                    context_flags=context_flags,
                )
            text = prediction.code
            error = None
            prediction_payload = prediction.to_dict()
        except Exception as exc:
            text = ""
            error = str(exc)
            prediction_payload = {}
        latency_ms = int((time.perf_counter() - started) * 1000)
        metadata = dict(self.artifact.get("metadata") or {})
        if prediction_payload:
            metadata["last_prediction"] = prediction_payload
        return ProviderResult(
            text=text,
            backend=self.backend,
            model=self.model,
            device="local",
            dtype="embedding_classifier",
            quantization=None,
            latency_ms=latency_ms,
            tokens_generated=1 if text else 0,
            tokens_per_second=_tokens_per_second(1 if text else 0, latency_ms),
            stop_enforced=True,
            error=error,
            model_load_time_ms=self.model_load_time_ms,
            generation_settings={
                "deterministic": True,
                "protocol": protocol,
                "system_prompt_ignored": True,
            },
            protocol=protocol,
            classifier_metadata=metadata,
        )

    def generate(self, system_prompt: str, user_text: str, protocol: str) -> ProviderResult:
        return self.generate_with_context(system_prompt, user_text, protocol)


class EncoderStage0RouterBackend:
    backend = "encoder_stage0"

    def __init__(
        self,
        model: str,
        *,
        artifact_loader: Any | None = None,
    ) -> None:
        from training import router_stage0_encoder

        self.model = model
        self.artifact_path = Path(model)
        loader = artifact_loader or router_stage0_encoder.load_encoder_stage0_artifact
        started = time.perf_counter()
        self.artifact = loader(self.artifact_path)
        self.model_load_time_ms = int((time.perf_counter() - started) * 1000)
        self._predict_encoder_stage0 = router_stage0_encoder.predict_encoder_stage0

    def generate_with_context(
        self,
        system_prompt: str,
        user_text: str,
        protocol: str,
        *,
        context_flags: dict[str, Any] | None = None,
    ) -> ProviderResult:
        started = time.perf_counter()
        try:
            prediction = self._predict_encoder_stage0(self.artifact, user_text, context_flags=context_flags)
            text = prediction.code
            error = None
            prediction_payload = prediction.to_dict()
        except Exception as exc:
            text = ""
            error = str(exc)
            prediction_payload = {}
        latency_ms = int((time.perf_counter() - started) * 1000)
        metadata = dict(self.artifact.get("metadata") or {})
        if prediction_payload:
            metadata["last_prediction"] = prediction_payload
        return ProviderResult(
            text=text,
            backend=self.backend,
            model=self.model,
            device="local",
            dtype="encoder_stage0",
            quantization=None,
            latency_ms=latency_ms,
            tokens_generated=1 if text else 0,
            tokens_per_second=_tokens_per_second(1 if text else 0, latency_ms),
            stop_enforced=True,
            error=error,
            model_load_time_ms=self.model_load_time_ms,
            generation_settings={
                "deterministic": True,
                "protocol": protocol,
                "system_prompt_ignored": True,
            },
            protocol=protocol,
            classifier_metadata=metadata,
        )

    def generate(self, system_prompt: str, user_text: str, protocol: str) -> ProviderResult:
        return self.generate_with_context(system_prompt, user_text, protocol)


def build_router_backend(
    backend: str,
    model: str,
    *,
    options: RouterGenerationOptions | None = None,
    base_url: str | None = None,
    api_key: str = "local",
    timeout_seconds: int = 90,
    expected_cuda: bool = False,
    adapter_path: str | None = None,
) -> RouterBackend:
    normalized = normalize_backend(backend)
    if normalized == "embedding_classifier":
        return EmbeddingClassifierRouterBackend(model)
    if normalized == "encoder_stage0":
        return EncoderStage0RouterBackend(model)
    if normalized == "ollama":
        return OllamaRouterBackend(
            model,
            options=options,
            base_url=base_url or DEFAULT_OLLAMA_URL,
            timeout_seconds=timeout_seconds,
        )
    if normalized == "hf_transformers":
        return HFTransformersRouterBackend(
            model,
            options=options,
            expected_cuda=expected_cuda,
            adapter_path=adapter_path,
        )
    return OpenAICompatibleRouterBackend(
        normalized,
        model,
        options=options,
        base_url=base_url or "http://127.0.0.1:8000/v1",
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )
