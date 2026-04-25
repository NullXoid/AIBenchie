from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


if __package__ in {None, ""}:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    import sys

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from evals.run_eval import load_scenarios
    from training import train_sft_qlora
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    from evals.run_eval import load_scenarios
    from . import train_sft_qlora


DEFAULT_CONFIG = PROJECT_ROOT / "training" / "qlora_smoke_config.yaml"
DEFAULT_HOLDOUT_DIR = PROJECT_ROOT / "evals" / "holdout" / "paraphrase_v0"
DEFAULT_HOLDOUT_OUTPUT = PROJECT_ROOT / "reports" / "training" / "v0_9_holdout_outputs.jsonl"
DEFAULT_HOLDOUT_RESULTS = PROJECT_ROOT / "reports" / "training" / "v0_9_holdout_results.jsonl"


def enrich_replay_records(
    outputs: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for scenario, output in zip(scenarios, outputs):
        payload = dict(output)
        metadata = dict(payload.get("metadata", {}))
        metadata["base_scenario_id"] = scenario.get("base_scenario_id", scenario["id"])
        metadata["original_scenario_id"] = scenario.get(
            "original_scenario_id",
            scenario.get("scenario_id", scenario["id"]),
        )
        if "paraphrase_index" in scenario:
            metadata["paraphrase_index"] = scenario["paraphrase_index"]
        payload["id"] = scenario["id"]
        payload["scenario_id"] = scenario["id"]
        payload["metadata"] = metadata
        enriched.append(payload)
    return enriched


def infer_eval_suite_id(scenarios: list[dict[str, Any]]) -> str:
    suite_ids = {scenario.get("eval_suite_id", "") for scenario in scenarios}
    if len(suite_ids) != 1:
        raise ValueError(f"Expected one eval suite id, found: {sorted(suite_ids)}")
    return next(iter(suite_ids))


def evaluate_adapter_suite(
    *,
    config_path: Path,
    scenarios_dir: Path,
    output_path: Path,
    results_output_path: Path,
    run_type: str,
    adapter_path: Path | None = None,
    base_model: str | None = None,
    eval_suite_id: str | None = None,
    max_new_tokens: int = 256,
) -> dict[str, Any]:
    config = train_sft_qlora.load_config(config_path)
    imports = train_sft_qlora.import_training_stack()
    train_sft_qlora.apply_seed(config, imports)
    resolved_base_model = base_model or config["base_model"]
    resolved_adapter_path = train_sft_qlora.resolve_project_path(
        adapter_path or config["output_dir"]
    )
    tokenizer, model = train_sft_qlora.load_minimal_model(
        {**config, "base_model": resolved_base_model},
        imports,
    )
    model = imports["PeftModel"].from_pretrained(model, str(resolved_adapter_path))
    scenarios = load_scenarios(scenarios_dir)
    resolved_eval_suite_id = eval_suite_id or infer_eval_suite_id(scenarios)
    outputs = train_sft_qlora.generate_for_scenarios(
        tokenizer=tokenizer,
        model=model,
        scenarios=scenarios,
        base_model=resolved_base_model,
        adapter_path=str(resolved_adapter_path),
        run_type=run_type,
        eval_suite_id=resolved_eval_suite_id,
        max_new_tokens=max_new_tokens,
    )
    replay_records = enrich_replay_records(outputs, scenarios)
    train_sft_qlora.write_jsonl(output_path, replay_records)
    scored = train_sft_qlora.score_replay_outputs(
        scenarios_dir=scenarios_dir,
        replay_path=output_path,
        output_path=results_output_path,
    )
    return {
        "output_path": str(output_path),
        "results_output_path": str(results_output_path),
        "eval_suite_id": resolved_eval_suite_id,
        "run_type": run_type,
        "adapter_path": str(resolved_adapter_path),
        "base_model": resolved_base_model,
        **scored.summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the frozen v0.8 adapter on an arbitrary scenario suite through replay."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--scenarios-dir", type=Path, default=DEFAULT_HOLDOUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_HOLDOUT_OUTPUT)
    parser.add_argument("--results-output", type=Path, default=DEFAULT_HOLDOUT_RESULTS)
    parser.add_argument("--run-type", default="v0_9_holdout_eval")
    parser.add_argument("--adapter-path", type=Path, default=None)
    parser.add_argument("--base-model", default=None)
    parser.add_argument("--eval-suite-id", default=None)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    args = parser.parse_args(argv)

    summary = evaluate_adapter_suite(
        config_path=args.config,
        scenarios_dir=args.scenarios_dir,
        output_path=args.output,
        results_output_path=args.results_output,
        run_type=args.run_type,
        adapter_path=args.adapter_path,
        base_model=args.base_model,
        eval_suite_id=args.eval_suite_id,
        max_new_tokens=args.max_new_tokens,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
