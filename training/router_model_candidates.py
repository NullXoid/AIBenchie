from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import yaml


PRODUCTION_PATH = "production_friendly"
PRIVATE_EXPERIMENTAL_PATH = "private_experimental"

LICENSE_PRODUCTION_REVIEWED = "production_reviewed"
LICENSE_CUSTOM = "custom_license"
LICENSE_PRIVATE_EXPERIMENTAL = "private_experimental_only"

SERVING_NOT_STARTED = "not_started"
SERVING_PROVEN = "proven"

SUPPORTED_LICENSE_CLASSES = {
    LICENSE_PRODUCTION_REVIEWED,
    LICENSE_CUSTOM,
    LICENSE_PRIVATE_EXPERIMENTAL,
}
TRAINING_SFT_LORA = "sft_lora"
TRAINING_EMBEDDING_CLASSIFIER = "embedding_classifier"

RECOVERY_ACTIVE = "active"
RECOVERY_DIAGNOSTIC_ONLY = "diagnostic_only"

SUPPORTED_BACKENDS = {"embedding_classifier", "hf_peft", "ollama_adapter", "vllm_openai", "sglang_openai"}
SUPPORTED_TRAINING_KINDS = {TRAINING_SFT_LORA, TRAINING_EMBEDDING_CLASSIFIER}
SUPPORTED_SERVING_PARITY = {SERVING_NOT_STARTED, SERVING_PROVEN}
SUPPORTED_RECOVERY_STATUSES = {RECOVERY_ACTIVE, RECOVERY_DIAGNOSTIC_ONLY}

ROUTE_CODE_GENERATION = {
    "temperature": 0.0,
    "top_p": 1.0,
    "max_new_tokens": 4,
    "stream": False,
    "stop": ["\n", " ", "="],
    "thinking_disabled": True,
}

DIRECT_ACTION_DATASET = "data/router_direct_action_boundaries_v2/router_lora_train_v2.jsonl"
DIRECT_ACTION_PREPARED_DATASET = "data/router_direct_action_boundaries_v2/router_lora_train_ready_v2.jsonl"
DIRECT_ACTION_DPO_DATASET = "data/router_direct_action_boundaries_v2/router_lora_dpo_pairs_v2.jsonl"

COMMON_TARGET_MODULES = (
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
)


@dataclass(frozen=True)
class RouterCandidate:
    id: str
    display_name: str
    model_id: str
    candidate_path: str
    evaluation_order: int
    license_class: str
    license_name: str
    intended_backend: str
    training_kind: str = TRAINING_SFT_LORA
    recovery_status: str = RECOVERY_ACTIVE
    serving_parity_status: str = SERVING_NOT_STARTED
    wrapper_drift_policy: str = "strict_protocol_failure"
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.candidate_path not in {PRODUCTION_PATH, PRIVATE_EXPERIMENTAL_PATH}:
            raise ValueError(f"Unsupported candidate_path for {self.id}: {self.candidate_path}")
        if self.license_class not in SUPPORTED_LICENSE_CLASSES:
            raise ValueError(f"Unsupported license_class for {self.id}: {self.license_class}")
        if self.intended_backend not in SUPPORTED_BACKENDS:
            raise ValueError(f"Unsupported intended_backend for {self.id}: {self.intended_backend}")
        if self.training_kind not in SUPPORTED_TRAINING_KINDS:
            raise ValueError(f"Unsupported training_kind for {self.id}: {self.training_kind}")
        if self.recovery_status not in SUPPORTED_RECOVERY_STATUSES:
            raise ValueError(f"Unsupported recovery_status for {self.id}: {self.recovery_status}")
        if self.serving_parity_status not in SUPPORTED_SERVING_PARITY:
            raise ValueError(f"Unsupported serving_parity_status for {self.id}: {self.serving_parity_status}")

    def with_serving_parity(self, status: str) -> "RouterCandidate":
        return replace(self, serving_parity_status=status)

    def metadata(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["notes"] = list(self.notes)
        return payload

    def shadow_mode_blockers(
        self,
        *,
        focused_gates_passed: bool,
        holdout_v3_passed: bool,
    ) -> list[str]:
        blockers: list[str] = []
        if self.recovery_status != RECOVERY_ACTIVE:
            blockers.append("candidate_not_active_for_promotion")
        if self.candidate_path != PRODUCTION_PATH:
            blockers.append("candidate_path_private_experimental")
        if self.license_class != LICENSE_PRODUCTION_REVIEWED:
            blockers.append("license_not_production_reviewed")
        if self.serving_parity_status != SERVING_PROVEN:
            blockers.append("serving_parity_not_proven")
        if not focused_gates_passed:
            blockers.append("focused_gates_not_passed")
        if not holdout_v3_passed:
            blockers.append("holdout_v3_not_passed")
        return blockers

    def shadow_mode_eligible(
        self,
        *,
        focused_gates_passed: bool,
        holdout_v3_passed: bool,
    ) -> bool:
        return not self.shadow_mode_blockers(
            focused_gates_passed=focused_gates_passed,
            holdout_v3_passed=holdout_v3_passed,
        )


def candidate_catalog() -> tuple[RouterCandidate, ...]:
    return (
        RouterCandidate(
            id="embedding_classifier_router",
            display_name="Embedding Classifier Router",
            model_id="sentence-transformers/all-MiniLM-L6-v2",
            candidate_path=PRODUCTION_PATH,
            evaluation_order=0,
            license_class=LICENSE_PRODUCTION_REVIEWED,
            license_name="Apache-2.0 primary embedding, MIT BGE alternative",
            intended_backend="embedding_classifier",
            training_kind=TRAINING_EMBEDDING_CLASSIFIER,
            notes=(
                "Co-primary candidate for fast route_code intent routing.",
                "Train flat_15_class and two_stage classifiers before any LLM fallback promotion.",
                "Generated classifier artifacts stay under ignored local model paths.",
            ),
        ),
        RouterCandidate(
            id="granite_4_0_micro",
            display_name="IBM Granite 4.0 Micro",
            model_id="ibm-granite/granite-4.0-micro",
            candidate_path=PRODUCTION_PATH,
            evaluation_order=4,
            license_class=LICENSE_PRODUCTION_REVIEWED,
            license_name="Apache-2.0",
            intended_backend="hf_peft",
            recovery_status=RECOVERY_DIAGNOSTIC_ONLY,
            notes=(
                "Stopped as a promotable candidate after false job starts and memory writes.",
                "Archive false job/memory examples for future training data.",
                "HF/vLLM/SGLang serving parity is still required before shadow mode.",
            ),
        ),
        RouterCandidate(
            id="llama_3_2_3b_instruct",
            display_name="Meta Llama 3.2 3B Instruct",
            model_id="meta-llama/Llama-3.2-3B-Instruct",
            candidate_path=PRODUCTION_PATH,
            evaluation_order=2,
            license_class=LICENSE_CUSTOM,
            license_name="Llama 3.2 Community License",
            intended_backend="ollama_adapter",
            notes=(
                "Use after access and license requirements are reviewed.",
                "Ollama adapter parity is required before shadow mode.",
            ),
        ),
        RouterCandidate(
            id="lfm2_5_1_2b_instruct",
            display_name="LiquidAI LFM2.5 1.2B Instruct",
            model_id="LiquidAI/LFM2.5-1.2B-Instruct",
            candidate_path=PRODUCTION_PATH,
            evaluation_order=3,
            license_class=LICENSE_CUSTOM,
            license_name="LFM 1.0",
            intended_backend="hf_peft",
            notes=(
                "Fast lane candidate after route-code protocol validity is clean.",
                "Tool-call wrapper drift must remain a protocol failure.",
            ),
        ),
        RouterCandidate(
            id="hammer2_1_1_5b",
            display_name="Hammer2.1 1.5B",
            model_id="MadeAgents/Hammer2.1-1.5b",
            candidate_path=PRIVATE_EXPERIMENTAL_PATH,
            evaluation_order=5,
            license_class=LICENSE_PRIVATE_EXPERIMENTAL,
            license_name="cc-by-nc-4.0",
            intended_backend="hf_peft",
            notes=(
                "Private action-router benchmark only until license review clears usage.",
                "Function-call wrappers are scored as protocol failures in route_code mode.",
            ),
        ),
        RouterCandidate(
            id="xlam_2_1b_fc_r",
            display_name="xLAM-2 1B Function Calling",
            model_id="Salesforce/xLAM-2-1b-fc-r",
            candidate_path=PRIVATE_EXPERIMENTAL_PATH,
            evaluation_order=6,
            license_class=LICENSE_PRIVATE_EXPERIMENTAL,
            license_name="license review required",
            intended_backend="hf_peft",
            notes=(
                "Private action-router benchmark only until license review clears usage.",
                "Test the 3B xLAM only if this 1B candidate is close but not enough.",
            ),
        ),
        RouterCandidate(
            id="xlam_2_3b_fc_r",
            display_name="xLAM-2 3B Function Calling",
            model_id="Salesforce/xLAM-2-3b-fc-r",
            candidate_path=PRIVATE_EXPERIMENTAL_PATH,
            evaluation_order=7,
            license_class=LICENSE_PRIVATE_EXPERIMENTAL,
            license_name="license review required",
            intended_backend="hf_peft",
            notes=(
                "Private follow-up only if xLAM-2 1B is close but not enough.",
                "Do not production-promote without license review.",
            ),
        ),
    )


def candidate_by_id(candidate_id: str) -> RouterCandidate:
    normalized = str(candidate_id or "").strip()
    for candidate in candidate_catalog():
        if candidate.id == normalized:
            return candidate
    raise KeyError(f"Unknown router candidate: {candidate_id}")


def ordered_candidates(path: str | None = None) -> list[RouterCandidate]:
    candidates = list(candidate_catalog())
    if path is not None:
        candidates = [candidate for candidate in candidates if candidate.candidate_path == path]
    return sorted(candidates, key=lambda candidate: candidate.evaluation_order)


def _report_stem(candidate: RouterCandidate) -> str:
    return candidate.id.upper()


def candidate_training_config(candidate_or_id: RouterCandidate | str) -> dict[str, Any]:
    candidate = candidate_by_id(candidate_or_id) if isinstance(candidate_or_id, str) else candidate_or_id
    if candidate.training_kind != TRAINING_SFT_LORA:
        raise ValueError(f"{candidate.id} does not use the QLoRA SFT training config path")
    label = f"router_model_recovery_{candidate.id}"
    report_stem = _report_stem(candidate)
    return {
        "stage": "router_model_recovery_sft",
        "repo_wsl_path": ".",
        "wsl_distro": "Ubuntu-24.04",
        "allow_native_windows": True,
        "venv_path": "~/.venvs/lv7-sft",
        "hf_home": "~/.cache/huggingface",
        "transformers_cache": "~/.cache/huggingface/transformers",
        "dataset": DIRECT_ACTION_DATASET,
        "prepared_dataset": DIRECT_ACTION_PREPARED_DATASET,
        "dpo_dataset_unused": DIRECT_ACTION_DPO_DATASET,
        "base_model": candidate.model_id,
        "quantization": "4bit_nf4",
        "save_adapter_only": True,
        "output_dir": f"models/adapters/{label}/",
        "plan_report": f"reports/training/ROUTER_MODEL_RECOVERY_{report_stem}_PLAN.md",
        "base_eval_outputs": f"reports/training/{label}_base_outputs.jsonl",
        "base_eval_results": f"reports/training/{label}_base_results.jsonl",
        "qwen_base_eval_outputs": f"reports/training/{label}_base_outputs.jsonl",
        "qwen_base_eval_results": f"reports/training/{label}_base_results.jsonl",
        "comparison_runs": [],
        "current_label": label,
        "analysis_title": f"{candidate.display_name} Router Model Recovery Analysis",
        "run_config": f"reports/training/{label}_run_config.json",
        "train_log": f"reports/training/{label}_train_log.jsonl",
        "adapter_eval_outputs": f"reports/training/{label}_adapter_outputs.jsonl",
        "adapter_eval_results": f"reports/training/{label}_adapter_results.jsonl",
        "analysis_report": f"reports/training/ROUTER_MODEL_RECOVERY_{report_stem}_ANALYSIS.md",
        "adapter_run_type": label,
        "max_steps": 260,
        "learning_rate": 1.0e-4,
        "per_device_train_batch_size": 1,
        "gradient_accumulation_steps": 8,
        "max_seq_length": 768,
        "lora_r": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.05,
        "target_modules": list(COMMON_TARGET_MODULES),
        "eval_suite_id": "nullxoid_router_model_recovery",
        "eval_prompt_mode": "route_code",
        "min_vram_gb": 16,
        "seed": 42,
        "data_seed": 42,
        "candidate": candidate.metadata(),
        "router_protocol": {
            "protocol": "route_code",
            "generation": dict(ROUTE_CODE_GENERATION),
            "gates": [
                "router_protocol_200",
                "router_console_semantics_350",
                "router_direct_action_boundaries_500",
                "router_holdout_1000_v3",
            ],
            "wrapper_drift_policy": candidate.wrapper_drift_policy,
            "promotion_rules": {
                "focused_gates_required": True,
                "holdout_v3_required": True,
                "serving_parity_required": True,
                "false_direct_actions_total": 0,
                "protocol_validity_min": 0.995,
                "direct_action_recall_min": 0.98,
                "hard_negative_recall_min": 0.98,
                "shadow_mode_before_control": True,
            },
        },
    }


def write_candidate_training_config(candidate_or_id: RouterCandidate | str, output_dir: Path) -> Path:
    candidate = candidate_by_id(candidate_or_id) if isinstance(candidate_or_id, str) else candidate_or_id
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"qlora_router_model_recovery_{candidate.id}.yaml"
    path.write_text(
        yaml.safe_dump(candidate_training_config(candidate), sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return path


def write_all_candidate_training_configs(output_dir: Path) -> list[Path]:
    return [
        write_candidate_training_config(candidate, output_dir)
        for candidate in ordered_candidates()
        if candidate.training_kind == TRAINING_SFT_LORA
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write NullXoid router model recovery candidate configs.")
    parser.add_argument("--output-dir", type=Path, default=Path("training/router_model_recovery_configs"))
    args = parser.parse_args(argv)
    paths = write_all_candidate_training_configs(args.output_dir)
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
