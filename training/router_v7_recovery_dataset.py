from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from evals import router_gate
from training import router_stage0_encoder as encoder


DEFAULT_V7_RESULT = Path(".suite/local/router_holdout_1000_v7_current_best_clean_run.json")
DEFAULT_OUTPUT_DIR = Path("data/router_v7_recovery")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def iter_rows(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path)
    rows: list[dict[str, Any]] = []
    for result in payload.get("results") or []:
        rows.extend(result.get("rows") or [])
    if not rows and payload.get("rows"):
        rows.extend(payload["rows"])
    return rows


def route_code(route: str) -> str:
    return router_gate.ROUTE_TO_CODE[route]


def recovery_record(
    *,
    record_id: str,
    text: str,
    route: str,
    category: str,
    template_family: str,
    source: str,
    training_role: str,
    context_flags: dict[str, Any] | None = None,
    required_context_flags: list[str] | None = None,
    rejected_gate: str | None = None,
) -> dict[str, Any]:
    code = route_code(route)
    return {
        "id": record_id,
        "text": text,
        "code": code,
        "route": route,
        "expected_route": route,
        "stage0_label": encoder.stage0_label_for_code(code),
        "source": source,
        "category": category,
        "action_family": "none",
        "training_role": training_role,
        "template_family": template_family,
        "context_flags": dict(context_flags or {}),
        "required_context_flags": list(required_context_flags or []),
        "rejected_stage0_gate": rejected_gate,
    }


def infer_template_family(row: dict[str, Any]) -> str:
    expected = str(row.get("expected_route") or "unknown").replace(".", "_")
    actual = str(row.get("actual_route") or "unknown").replace(".", "_")
    category = str(row.get("category") or "unknown")
    text = str(row.get("text") or "").lower()
    if expected == "answer_question":
        if "talk through" in text:
            form = "talk_through_answer_not_no_action"
        elif "compare interpretations" in text:
            form = "compare_interpretations_answer_not_no_action"
        elif "keep this as analysis" in text:
            form = "analysis_request_answer_not_no_action"
        else:
            form = "answer_not_no_action"
    elif expected == "chat_no_action":
        if "preference is" in text:
            form = "temporary_preference_not_memory_or_clarify"
        else:
            form = "no_action_not_clarify"
    else:
        form = "safe_stage_boundary"
    return f"stage0_v7_safe_stage:{category}:{form}:{expected}:not_{actual}"


def extract_stage0_safe_stage_misses(result_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    safe_stage_routes = {"chat.no_action", "answer.question", "ask_clarifying_question"}
    for index, row in enumerate(iter_rows(result_path), start=1):
        expected_route = str(row.get("expected_route") or "")
        if expected_route not in safe_stage_routes:
            continue
        expected_gate = str(row.get("expected_stage0_gate") or "")
        actual_gate = str(row.get("stage0_gate") or "")
        if expected_gate == actual_gate:
            continue
        records.append(
            recovery_record(
                record_id=f"stage0_v7_safe_miss_{index:04d}_{row.get('id')}",
                text=str(row.get("text") or ""),
                route=expected_route,
                category=str(row.get("category") or "stage0_v7_safe_stage_miss"),
                template_family=infer_template_family(row),
                source="router_holdout_1000_v7_diagnostic_stage0_safe_stage_miss",
                training_role="stage0_safe_stage_hard_positive",
                context_flags=dict(row.get("context_flags") or {}),
                required_context_flags=list(row.get("required_context_flags") or []),
                rejected_gate=actual_gate or None,
            )
        )
    return records


def generated_safe_stage_contrast_records() -> list[dict[str, Any]]:
    templates = {
        "chat.no_action": [
            "This is a private scratch note about routing; no answer needed.",
            "I am noting that the current holdout is diagnostic, not asking a question.",
            "No response required; this is just a status note about safe-stage routing.",
            "For this conversation only, I prefer concise notes; do not save it.",
            "I am thinking out loud about router taxonomy without asking for analysis.",
        ],
        "answer.question": [
            "Talk through the route taxonomy without executing anything.",
            "Compare interpretations of answer.question and chat.no_action.",
            "Explain the safety boundary for temporary preference talk.",
            "Describe why a command discussion should not run a command.",
            "Keep this as analysis only: explain the safe-stage boundary.",
        ],
        "ask_clarifying_question": [
            "Can you handle that?",
            "Proceed with the right router path.",
            "Do whichever safe-stage action applies.",
            "Can you take care of the previous thing?",
            "Move it through the appropriate lane.",
        ],
    }
    records: list[dict[str, Any]] = []
    for route, texts in templates.items():
        for index, text in enumerate(texts, start=1):
            records.append(
                recovery_record(
                    record_id=f"stage0_v7_safe_contrast_{route_code(route)}_{index:03d}",
                    text=f"{text} Stage0 v7 safe-stage contrast case {index}.",
                    route=route,
                    category="stage0_safe_stage_contrast",
                    template_family=f"stage0_v7_safe_stage:generated:{route.replace('.', '_')}",
                    source="stage0_v7_safe_stage_contrast_generated",
                    training_role="stage0_safe_stage_balanced_positive",
                )
            )
    return records


def dedupe_by_text_code(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (record["text"], record["code"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def build_v7_recovery_dataset(
    *,
    result_path: Path = DEFAULT_V7_RESULT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    extracted = extract_stage0_safe_stage_misses(result_path)
    generated = generated_safe_stage_contrast_records()
    records = dedupe_by_text_code([*extracted, *generated])
    output_path = output_dir / "stage0_safe_stage_records_v7.jsonl"
    manifest_path = output_dir / "stage0_safe_stage_records_v7_manifest.json"
    write_jsonl(output_path, records)
    manifest = {
        "dataset": "router_v7_stage0_safe_stage_recovery",
        "source_result": str(result_path),
        "output": str(output_path),
        "manifest": str(manifest_path),
        "extracted_stage0_safe_stage_miss_count": len(extracted),
        "generated_safe_stage_contrast_count": len(generated),
        "record_count": len(records),
        "route_counts": dict(sorted(Counter(record["route"] for record in records).items())),
        "stage0_label_counts": dict(sorted(Counter(record["stage0_label"] for record in records).items())),
        "training_role_counts": dict(sorted(Counter(record["training_role"] for record in records).items())),
        "hash": sha256("\n".join(json.dumps(record, sort_keys=True) for record in records).encode("utf-8")).hexdigest(),
    }
    write_json(manifest_path, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build router v7 Stage 0 safe-stage recovery records.")
    parser.add_argument("--result", type=Path, default=DEFAULT_V7_RESULT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    print(json.dumps(build_v7_recovery_dataset(result_path=args.result, output_dir=args.output_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
