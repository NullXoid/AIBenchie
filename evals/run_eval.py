from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


if __package__ in {None, ""}:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from evals.adapters import build_adapter
    from evals.scoring import score_response
else:
    from .adapters import build_adapter
    from .scoring import score_response


def load_scenarios(scenarios_dir: Path) -> list[dict[str, Any]]:
    if not scenarios_dir.exists() or not scenarios_dir.is_dir():
        raise FileNotFoundError(f"Scenario directory not found: {scenarios_dir}")

    scenario_paths = sorted(scenarios_dir.glob("*.yaml"))
    if not scenario_paths:
        raise FileNotFoundError(f"No scenario files found in: {scenarios_dir}")

    scenarios: list[dict[str, Any]] = []
    for path in scenario_paths:
        with path.open("r", encoding="utf-8") as handle:
            scenario = yaml.safe_load(handle)
        scenario["_path"] = str(path)
        scenarios.append(scenario)
    return scenarios


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_evaluation(
    scenarios_dir: Path,
    adapter_name: str,
    output_path: Path,
    replay_file: Path | None = None,
) -> list[dict[str, Any]]:
    adapter = build_adapter(adapter_name, replay_file=replay_file)
    scenarios = load_scenarios(scenarios_dir)
    results: list[dict[str, Any]] = []

    for scenario in scenarios:
        adapter_result = adapter.generate(scenario)
        scored = score_response(scenario, adapter_result["text"])
        results.append(
            {
                "id": scenario["id"],
                "scenario_id": scenario["scenario_id"],
                "eval_suite_id": scenario.get("eval_suite_id", ""),
                "adapter": adapter_result["adapter"],
                "prompt": scenario["prompt"],
                "response_text": adapter_result["text"],
                "parsed_policy_rationale": scored["parsed_policy_rationale"],
                "score": scored["score"],
                "pass": scored["score"]["pass"],
                "metadata": adapter_result.get("metadata", {}),
            }
        )

    write_jsonl(output_path, results)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the LV7 pilot evaluation harness.")
    parser.add_argument("--scenarios-dir", required=True, type=Path)
    parser.add_argument(
        "--adapter", required=True, choices=["mock", "unsafe_mock", "replay"]
    )
    parser.add_argument("--replay-file", type=Path, default=None)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    if args.adapter == "replay" and args.replay_file is None:
        parser.error("--replay-file is required when --adapter replay is selected.")

    try:
        results = run_evaluation(
            scenarios_dir=args.scenarios_dir,
            adapter_name=args.adapter,
            output_path=args.output,
            replay_file=args.replay_file,
        )
    except (FileNotFoundError, KeyError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = {
        "adapter": args.adapter,
        "total": len(results),
        "passed": sum(1 for result in results if result["pass"]),
        "failed": sum(1 for result in results if not result["pass"]),
        "output": str(args.output),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
