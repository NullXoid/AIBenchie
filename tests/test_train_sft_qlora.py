from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import ROOT, SFT_MESSAGES_V1_9
from training import prepare_sft_dataset, train_sft_qlora


def read_jsonl(path):
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class FakeTokenizer:
    pad_token_id = 0
    eos_token = "<eos>"
    pad_token = "<pad>"

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
        rendered = []
        for message in messages:
            rendered.append(f"<{message['role']}>{message['content']}</{message['role']}>")
        if add_generation_prompt:
            rendered.append("<assistant>")
        text = "".join(rendered)
        if tokenize:
            return [ord(ch) for ch in text]
        return text

    def __call__(self, text, truncation=False, max_length=None, add_special_tokens=False, return_tensors=None):
        ids = [ord(ch) for ch in text]
        if truncation and max_length is not None:
            ids = ids[:max_length]
        payload = {"input_ids": ids, "attention_mask": [1] * len(ids)}
        if return_tensors == "pt":
            import torch

            return {
                "input_ids": torch.tensor([ids], dtype=torch.long),
                "attention_mask": torch.tensor([[1] * len(ids)], dtype=torch.long),
            }
        return payload


def test_prepare_sft_dataset_writes_inspectable_output(tmp_path):
    output_path = tmp_path / "sft_train_ready.jsonl"
    summary = prepare_sft_dataset.prepare_sft_dataset(SFT_MESSAGES_V1_9, output_path)

    records = read_jsonl(output_path)
    assert summary["count"] == 257
    assert len(records) == 257
    first = records[0]
    assert first["id"]
    assert first["scenario_id"]
    assert first["messages"][0]["role"] == "user"
    assert first["messages"][1]["role"] == "assistant"
    assert "policy_rationale:" in first["text"]
    assert "assistant:" in first["text"]


def test_tokenize_with_assistant_mask_masks_prompt_tokens():
    messages = [
        {"role": "user", "content": "Prompt"},
        {"role": "assistant", "content": "Answer"},
    ]
    tokenized = train_sft_qlora.tokenize_with_assistant_mask(
        tokenizer=FakeTokenizer(),
        messages=messages,
        max_seq_length=1024,
    )

    assert len(tokenized["input_ids"]) == len(tokenized["labels"])
    assert tokenized["labels"][0] == -100
    assert any(label != -100 for label in tokenized["labels"])


def test_resolve_probe_status_prefers_mount_then_pip_then_cuda():
    probe = {
        "repo_reachable": False,
        "pip_available": False,
        "venv_available": False,
        "cuda_available": False,
        "bnb_import_ready": False,
        "bnb_4bit_ready": False,
        "model_load_ready": False,
    }
    assert train_sft_qlora.resolve_probe_status(probe, min_vram_gb=16) == train_sft_qlora.BLOCKED_WSL_MOUNT

    probe["repo_reachable"] = True
    assert train_sft_qlora.resolve_probe_status(probe, min_vram_gb=16) == train_sft_qlora.BLOCKED_NO_PIP

    probe["pip_available"] = True
    probe["venv_available"] = True
    probe["vram_mib"] = 24 * 1024
    assert train_sft_qlora.resolve_probe_status(probe, min_vram_gb=16) == train_sft_qlora.BLOCKED_NO_CUDA


def test_build_replay_record_includes_required_metadata():
    record = train_sft_qlora.build_replay_record(
        scenario_id="danger_shortcut_001",
        text="response",
        model="Qwen/Qwen2.5-1.5B-Instruct",
        base_model="Qwen/Qwen2.5-1.5B-Instruct",
        adapter_path="models/adapters/lv7_sft_smoke_v1_0_2/",
        run_type="v1_0_2_token_targeted_sft_patch",
        eval_suite_id="lv7_smoke_v1_2",
    )

    assert record["scenario_id"] == "danger_shortcut_001"
    assert record["metadata"]["prompt_mode"] == "raw"
    assert record["metadata"]["run_type"] == "v1_0_2_token_targeted_sft_patch"
    assert record["metadata"]["eval_suite_id"] == "lv7_smoke_v1_2"
    assert record["metadata"]["adapter_path"] == "models/adapters/lv7_sft_smoke_v1_0_2/"


def test_full_mode_stops_cleanly_on_probe_failure():
    sequence = []

    def probe():
        sequence.append("probe")
        return train_sft_qlora.StepResult(
            ok=False,
            status=train_sft_qlora.BLOCKED_WSL_MOUNT,
            summary={},
        )

    def eval_base():
        sequence.append("eval_base")
        return train_sft_qlora.StepResult(ok=True, status=train_sft_qlora.READY_FOR_WSL2_SMOKE, summary={})

    result = train_sft_qlora.run_full_pipeline(
        probe_fn=probe,
        eval_base_fn=eval_base,
        train_fn=eval_base,
        eval_adapter_fn=eval_base,
    )

    assert result.status == train_sft_qlora.BLOCKED_WSL_MOUNT
    assert sequence == ["probe"]


def test_full_mode_stops_cleanly_on_base_eval_failure():
    sequence = []

    def probe():
        sequence.append("probe")
        return train_sft_qlora.StepResult(
            ok=True,
            status=train_sft_qlora.READY_FOR_WSL2_SMOKE,
            summary={},
        )

    def eval_base():
        sequence.append("eval_base")
        return train_sft_qlora.StepResult(ok=False, status=train_sft_qlora.BLOCKED_MODEL_LOAD, summary={})

    def train():
        sequence.append("train")
        return train_sft_qlora.StepResult(ok=True, status=train_sft_qlora.READY_FOR_WSL2_SMOKE, summary={})

    result = train_sft_qlora.run_full_pipeline(
        probe_fn=probe,
        eval_base_fn=eval_base,
        train_fn=train,
        eval_adapter_fn=train,
    )

    assert result.status == train_sft_qlora.BLOCKED_MODEL_LOAD
    assert sequence == ["probe", "eval_base"]


def test_full_mode_stops_cleanly_on_train_failure():
    sequence = []

    def probe():
        sequence.append("probe")
        return train_sft_qlora.StepResult(
            ok=True,
            status=train_sft_qlora.READY_FOR_WSL2_SMOKE,
            summary={},
        )

    def eval_base():
        sequence.append("eval_base")
        return train_sft_qlora.StepResult(
            ok=True,
            status=train_sft_qlora.READY_FOR_WSL2_SMOKE,
            summary={},
        )

    def train():
        sequence.append("train")
        return train_sft_qlora.StepResult(ok=False, status=train_sft_qlora.BLOCKED_BNB_4BIT, summary={})

    result = train_sft_qlora.run_full_pipeline(
        probe_fn=probe,
        eval_base_fn=eval_base,
        train_fn=train,
        eval_adapter_fn=eval_base,
    )

    assert result.status == train_sft_qlora.BLOCKED_BNB_4BIT
    assert sequence == ["probe", "eval_base", "train"]


def test_gitignore_covers_venv_and_adapter_paths():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert ".venvs/" in gitignore
    assert "models/adapters/lv7_sft_smoke/" in gitignore
    assert "models/adapters/lv7_sft_smoke_v0_6/" in gitignore
    assert "models/adapters/lv7_sft_smoke_v0_7/" in gitignore
    assert "models/adapters/lv7_sft_smoke_v0_8/" in gitignore
    assert "models/adapters/lv7_sft_smoke_v1_0/" in gitignore
    assert "models/adapters/lv7_sft_smoke_v1_0_2/" in gitignore
    assert "models/adapters/lv7_sft_smoke_v1_0_3/" in gitignore
    assert "models/adapters/lv7_sft_smoke_v1_0_5/" in gitignore
    assert "models/adapters/lv7_sft_shared_contract_v1_3_6_2/" in gitignore


def test_load_config_defaults_to_v1_0_5_paths():
    config = train_sft_qlora.load_config(ROOT / "training" / "qlora_smoke_config.yaml")

    assert config["dataset"] == "data/pilot_v1_9/sft_messages.jsonl"
    assert config["prepared_dataset"] == "data/pilot_v1_9/sft_train_ready.jsonl"
    assert config["output_dir"] == "models/adapters/lv7_sft_smoke_v1_0_5/"
    assert config["adapter_eval_outputs"] == "reports/training/v1_0_5_exact_eval_outputs.jsonl"
    assert config["adapter_eval_results"] == "reports/training/v1_0_5_exact_eval_results.jsonl"
    assert config["analysis_report"] == "reports/training/V1_0_5_TINY_LEXICAL_SFT_ANALYSIS.md"
    assert config["comparison_runs"][0]["results"] == "reports/training/sft_smoke_eval_results.jsonl"
    assert config["comparison_runs"][1]["results"] == "reports/training/v0_6_sft_eval_results.jsonl"
    assert config["comparison_runs"][2]["results"] == "reports/training/v0_7_sft_eval_results.jsonl"
    assert config["comparison_runs"][3]["results"] == "reports/training/v0_8_sft_eval_results.jsonl"
    assert config["comparison_runs"][4]["results"] == "reports/training/v1_0_exact_eval_results.jsonl"
    assert config["comparison_runs"][5]["results"] == "reports/training/v1_0_2_exact_eval_results.jsonl"
    assert config["comparison_runs"][6]["results"] == "reports/training/v1_0_3_exact_eval_results.jsonl"
    assert config["seed"] == 42
    assert config["data_seed"] == 42
    assert config["starting_adapter"] == ""


def test_initialize_trainable_model_preserves_old_behavior_without_starting_adapter():
    captured = {}

    class FakeBaseModel:
        def __init__(self):
            self.config = type("Config", (), {"use_cache": True})()

    def fake_prepare_model_for_kbit_training(model):
        captured["prepared"] = True
        return model

    def fake_lora_config(**kwargs):
        captured["lora_kwargs"] = kwargs
        return {"fake_lora_config": kwargs}

    def fake_get_peft_model(model, lora_config):
        captured["used_get_peft_model"] = True
        captured["passed_lora_config"] = lora_config
        return {"wrapped": model, "lora": lora_config}

    config = train_sft_qlora.load_config(ROOT / "training" / "qlora_smoke_config.yaml")
    model, starting_adapter_path = train_sft_qlora.initialize_trainable_model(
        FakeBaseModel(),
        config=config,
        imports={
            "prepare_model_for_kbit_training": fake_prepare_model_for_kbit_training,
            "LoraConfig": fake_lora_config,
            "get_peft_model": fake_get_peft_model,
            "PeftModel": object(),
        },
    )

    assert captured["prepared"] is True
    assert captured["used_get_peft_model"] is True
    assert captured["lora_kwargs"]["r"] == config["lora_r"]
    assert captured["lora_kwargs"]["lora_alpha"] == config["lora_alpha"]
    assert captured["lora_kwargs"]["lora_dropout"] == config["lora_dropout"]
    assert captured["lora_kwargs"]["target_modules"] == config["target_modules"]
    assert starting_adapter_path == ""
    assert model["wrapped"].config.use_cache is False


def test_initialize_trainable_model_loads_starting_adapter_when_present(tmp_path):
    adapter_dir = tmp_path / "starting_adapter"
    adapter_dir.mkdir(parents=True)
    config = train_sft_qlora.load_config(ROOT / "training" / "qlora_smoke_config.yaml")
    adapter_config = {
        "r": config["lora_r"],
        "lora_alpha": config["lora_alpha"],
        "lora_dropout": config["lora_dropout"],
        "target_modules": config["target_modules"],
        "base_model_name_or_path": config["base_model"],
    }
    (adapter_dir / "adapter_config.json").write_text(
        json.dumps(adapter_config),
        encoding="utf-8",
    )

    class FakeLoadedModel:
        def __init__(self):
            self.config = type("Config", (), {"use_cache": True})()
            self.trained = False

        def train(self):
            self.trained = True

    calls = {}

    def fake_prepare_model_for_kbit_training(model):
        calls["prepared"] = True
        return model

    class FakePeftModel:
        @staticmethod
        def from_pretrained(model, adapter_path, **kwargs):
            calls["adapter_path"] = adapter_path
            calls["kwargs"] = kwargs
            loaded = FakeLoadedModel()
            loaded.config = model.config
            return loaded

    config["starting_adapter"] = str(adapter_dir)

    model, starting_adapter_path = train_sft_qlora.initialize_trainable_model(
        FakeLoadedModel(),
        config=config,
        imports={
            "prepare_model_for_kbit_training": fake_prepare_model_for_kbit_training,
            "PeftModel": FakePeftModel,
            "get_peft_model": lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("get_peft_model should not be used when starting_adapter is present")
            ),
            "LoraConfig": object(),
        },
    )

    assert calls["prepared"] is True
    assert calls["adapter_path"] == str(Path(adapter_dir))
    assert calls["kwargs"] == {"is_trainable": True}
    assert starting_adapter_path == str(Path(adapter_dir))
    assert model.trained is True
    assert model.config.use_cache is False


def test_build_training_arguments_passes_seed_defaults():
    captured = {}

    class FakeTrainingArguments:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    config = train_sft_qlora.load_config(ROOT / "training" / "qlora_smoke_config.yaml")
    train_sft_qlora.build_training_arguments(
        config=config,
        imports={"TrainingArguments": FakeTrainingArguments},
        output_dir=ROOT / "models" / "adapters" / "lv7_sft_smoke_v1_0_5",
    )

    assert captured["seed"] == 42
    assert captured["data_seed"] == 42
