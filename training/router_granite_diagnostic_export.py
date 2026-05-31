from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_GRANITE_RESULT_PATHS = (
    Path(".suite/local/router_protocol_200_granite_4_0_micro_route_code_baseline.json"),
    Path(".suite/local/router_console_semantics_350_granite_4_0_micro_baseline.json"),
    Path(".suite/local/router_direct_action_boundaries_500_granite_4_0_micro_baseline.json"),
    Path(".suite/local/router_protocol_200_granite_4_0_micro_route_code_adapter.json"),
    Path(".suite/local/router_console_semantics_350_granite_4_0_micro_adapter.json"),
    Path(".suite/local/router_direct_action_boundaries_500_granite_4_0_micro_adapter.json"),
)


def _load_result(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload.get("results") or []
    if not results:
        raise ValueError(f"{path} contains no router results")
    result = results[0]
    return {
        "path": str(path),
        "gate": result["gate"],
        "model": result["model"],
        "backend": result["backend"],
        "protocol": result["protocol"],
        "promotion_ready": bool(result["promotion_ready"]),
        "promotion_blockers": list(result.get("promotion_blockers") or []),
        "metrics": dict(result.get("metrics") or {}),
        "diagnostics": dict(result.get("diagnostics") or {}),
    }


def _compact_example(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "category": row.get("category"),
        "expected_route": row.get("expected_route"),
        "actual_route": row.get("actual_route"),
        "raw": row.get("raw"),
        "text": row.get("text"),
    }


def build_granite_diagnostic_archive(result_paths: list[Path]) -> dict[str, Any]:
    loaded = [_load_result(path) for path in result_paths if path.exists()]
    if not loaded:
        raise ValueError("No Granite result files were available to archive")
    false_job_examples: list[dict[str, Any]] = []
    false_memory_examples: list[dict[str, Any]] = []
    result_summaries = []
    for result in loaded:
        diagnostics = result["diagnostics"]
        false_job_examples.extend(_compact_example(row) for row in diagnostics.get("first_50_false_job_starts", []))
        false_memory_examples.extend(_compact_example(row) for row in diagnostics.get("first_50_false_memory_writes", []))
        metrics = result["metrics"]
        result_summaries.append(
            {
                "path": result["path"],
                "gate": result["gate"],
                "promotion_ready": result["promotion_ready"],
                "promotion_blockers": result["promotion_blockers"],
                "protocol_validity": metrics.get("protocol_validity"),
                "semantic_route_accuracy": metrics.get("semantic_route_accuracy"),
                "false_direct_actions_total": metrics.get("false_direct_actions_total"),
                "false_job_starts": metrics.get("false_job_starts"),
                "false_memory_writes": metrics.get("false_memory_writes"),
            }
        )
    return {
        "candidate": "granite_4_0_micro",
        "status": "diagnostic_only_failed_safety_gate",
        "promotable": False,
        "shadow_mode_eligible": False,
        "dpo_cleanup_recommended": False,
        "dpo_cleanup_reason": "false_direct_actions_total exceeded cleanup threshold and included false job starts or memory writes",
        "results": result_summaries,
        "training_candidates": {
            "false_job_start_examples": false_job_examples,
            "false_memory_write_examples": false_memory_examples,
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive Granite router recovery diagnostics.")
    parser.add_argument("--result", type=Path, action="append", dest="results")
    parser.add_argument("--output", type=Path, default=Path(".suite/local/granite_4_0_micro_diagnostic_archive.json"))
    args = parser.parse_args(argv)
    archive = build_granite_diagnostic_archive(args.results or list(DEFAULT_GRANITE_RESULT_PATHS))
    write_json(args.output, archive)
    print(json.dumps({"output": str(args.output), "promotable": archive["promotable"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
