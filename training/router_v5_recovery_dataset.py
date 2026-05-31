from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from evals import router_gate, router_hybrid_gate
from training import router_embedding_classifier as classifier
from training import router_stage0_encoder as encoder
from training import router_stage1_subtype_dataset as subtype_dataset


DEFAULT_V5_RESULT = Path(".suite/local/router_holdout_1000_v5_deberta_stage0_v3_modernbert_stage1a_v3_stage1c_v2_stage1b_v2_clean.json")
DEFAULT_STAGE0_OUTPUT = Path("data/router_v5_recovery/stage0_hard_records_v5.jsonl")
DEFAULT_STAGE1_BASE_DIR = Path("data/router_stage1_subtype_v3")
DEFAULT_STAGE1_OUTPUT_DIR = Path("data/router_stage1_subtype_v4")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def iter_result_rows(paths: Iterable[Path]) -> Iterable[dict[str, Any]]:
    for path in paths:
        payload = read_json(path)
        results = payload.get("results")
        if isinstance(results, dict):
            result_items = [results]
        elif isinstance(results, list):
            result_items = [item for item in results if isinstance(item, dict)]
        else:
            result_items = [payload] if isinstance(payload.get("rows"), list) else []
        for result in result_items:
            yield from result.get("rows") or []


def route_code(route: str) -> str:
    return router_gate.ROUTE_TO_CODE[route]


def stage0_record(
    *,
    record_id: str,
    text: str,
    expected_route: str,
    source: str,
    training_role: str,
    template_family: str,
    category: str,
    action_family: str,
    must_not_emit_g04: bool = False,
    context_flags: dict[str, Any] | None = None,
    required_context_flags: list[str] | None = None,
    rejected_route: str | None = None,
) -> dict[str, Any]:
    code = route_code(expected_route)
    return {
        "id": record_id,
        "text": text,
        "code": code,
        "route": expected_route,
        "stage0_label": encoder.stage0_label_for_code(code),
        "source": source,
        "category": category,
        "action_family": action_family,
        "training_role": training_role,
        "template_family": template_family,
        "must_not_emit_g04": must_not_emit_g04,
        "context_flags": dict(context_flags or {}),
        "required_context_flags": list(required_context_flags or []),
        "rejected_route": rejected_route,
        "rejected_code": None if rejected_route is None else route_code(rejected_route),
    }


def stage0_family_for_row(row: dict[str, Any]) -> str:
    text = str(row.get("text") or "").lower()
    expected = str(row.get("expected_route") or "unknown").replace(".", "_")
    actual = str(row.get("actual_route") or "unknown").replace(".", "_")
    if "handle whichever router path applies" in text:
        topic = "ambiguous_whichever_path"
    elif "pls exec fresh holdout gate" in text:
        topic = "messy_exec_holdout_gate"
    else:
        topic = "stage0_boundary"
    return f"stage0_v5_recovery:{topic}:{expected}:not_{actual}"


def extract_stage0_recovery_records(result_paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(iter_result_rows(result_paths), start=1):
        expected_gate = str(row.get("expected_stage0_gate") or "")
        actual_gate = str(row.get("stage0_gate") or "")
        expected_route = str(row.get("expected_route") or "")
        actual_route = str(row.get("actual_route") or "")
        if actual_gate == "G04" and expected_gate != "G04":
            records.append(
                stage0_record(
                    record_id=f"stage0_v5_false_risky_{index:04d}_{row.get('id')}",
                    text=str(row.get("text") or ""),
                    expected_route=expected_route,
                    source="router_holdout_1000_v5_diagnostic_stage0_false_risky",
                    training_role="v5_must_not_emit_g04",
                    template_family=stage0_family_for_row(row),
                    category=str(row.get("category") or "stage0_false_risky"),
                    action_family=str(row.get("action_family") or "none"),
                    must_not_emit_g04=True,
                    context_flags=dict(row.get("context_flags") or {}),
                    required_context_flags=list(row.get("required_context_flags") or []),
                    rejected_route=actual_route if actual_route in router_gate.ROUTE_TO_CODE else None,
                )
            )
        elif expected_gate == "G04" and actual_gate != "G04":
            records.append(
                stage0_record(
                    record_id=f"stage0_v5_missed_risky_{index:04d}_{row.get('id')}",
                    text=str(row.get("text") or ""),
                    expected_route=expected_route,
                    source="router_holdout_1000_v5_diagnostic_stage0_missed_risky",
                    training_role="v5_risky_hard_positive",
                    template_family=stage0_family_for_row(row),
                    category=str(row.get("category") or "stage0_missed_risky"),
                    action_family=str(row.get("action_family") or subtype_dataset.action_family_for_route(expected_route)),
                    must_not_emit_g04=False,
                    context_flags=dict(row.get("context_flags") or {}),
                    required_context_flags=list(row.get("required_context_flags") or []),
                    rejected_route=actual_route if actual_route in router_gate.ROUTE_TO_CODE else None,
                )
            )
    records.extend(generated_stage0_v5_records())
    return subtype_dataset.dedupe_by_text_code(records)


def generated_stage0_v5_records() -> list[dict[str, Any]]:
    generated: list[dict[str, Any]] = []
    ambiguous = [
        "Handle whichever router path applies.",
        "Use whichever action lane seems right.",
        "Put this through the route that fits.",
        "Take care of the router path somehow.",
        "Send this through whatever action path is appropriate.",
    ]
    for index, text in enumerate(ambiguous, start=1):
        generated.append(
            stage0_record(
                record_id=f"stage0_v5_generated_ambiguous_{index:03d}",
                text=f"{text} V5 recovery ambiguous case {index}.",
                expected_route="ask_clarifying_question",
                source="stage0_v5_recovery_generated",
                training_role="v5_must_not_emit_g04",
                template_family="stage0_v5_recovery:generated:ambiguous_whichever_path:ask_clarifying_question",
                category="ambiguous",
                action_family="none",
                must_not_emit_g04=True,
            )
        )
    unconfirmed_followups = [
        ("Yes, do it.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}, 1),
        ("Do it.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}, 4),
        ("Go ahead.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}, 6),
        ("Proceed.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}, 8),
        ("Make it happen.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}, 9),
        ("Yes, do it.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "false", "USER_CONFIRMED_PREVIOUS_ACTION": "false"}, 11),
        ("Do that now.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "false", "USER_CONFIRMED_PREVIOUS_ACTION": "false"}, 13),
        ("Proceed with that.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "false", "USER_CONFIRMED_PREVIOUS_ACTION": "false"}, 14),
        ("Go ahead with it.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "false", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}, 17),
        ("Handle it now.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "false"}, 18),
    ]
    for index, (text, flags, family_index) in enumerate(unconfirmed_followups, start=1):
        generated.append(
            stage0_record(
                record_id=f"stage0_v5_generated_unconfirmed_followup_{index:03d}",
                text=f"{text} V5 recovery unconfirmed follow-up case {index}.",
                expected_route="ask_clarifying_question",
                source="stage0_v5_recovery_generated",
                training_role="v5_must_not_emit_g04",
                template_family=f"stage0_v5_recovery:generated:unconfirmed_do_it_negative:{family_index}",
                category="context_dependent_case",
                action_family="none",
                must_not_emit_g04=True,
                context_flags=flags,
            )
        )
    run_texts = [
        "pls exec fresh holdout gate",
        "please execute the fresh holdout gate",
        "run the fresh holdout gate now",
        "exec the clean router holdout command",
        "pls run the hybrid holdout gate",
    ]
    for index, text in enumerate(run_texts, start=1):
        generated.append(
            stage0_record(
                record_id=f"stage0_v5_generated_run_{index:03d}",
                text=f"{text} V5 recovery run case {index}.",
                expected_route="console.run_command",
                source="stage0_v5_recovery_generated",
                training_role="v5_risky_hard_positive",
                template_family="stage0_v5_recovery:generated:messy_exec_holdout_gate:console_run_command",
                category="messy_voice_typo",
                action_family="run_command",
            )
        )
    return generated


def infer_stage1b_v5_template_family(row: dict[str, Any]) -> str:
    text = str(row.get("text") or "").lower()
    expected = str(row.get("expected_route") or "unknown").replace(".", "_")
    actual = str(row.get("actual_route") or "unknown").replace(".", "_")
    if "safe-lane subtype source" in text:
        topic = "edit_safe_lane_source"
    elif "route-gate evaluation test" in text:
        topic = "patch_route_gate_test"
    elif "remember concise router updates" in text:
        topic = "messy_memory_save"
    elif "fresh holdout gate" in text:
        topic = "messy_run_holdout_gate"
    else:
        topic = "risky_subtype_boundary"
    return f"stage1b_v5_recovery:{topic}:{expected}:not_{actual}"


def extract_stage1b_recovery_records(result_paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(iter_result_rows(result_paths), start=1):
        expected_route = str(row.get("expected_route") or "")
        actual_route = str(row.get("actual_route") or "")
        if expected_route not in router_hybrid_gate.RISKY_ROUTES or actual_route == expected_route:
            continue
        if str(row.get("expected_stage0_gate") or "") != "G04":
            continue
        records.append(
            subtype_dataset.stage1_record(
                record_id=f"stage1b_v5_miss_{index:04d}_{row.get('id')}",
                text=str(row.get("text") or ""),
                expected_route=expected_route,
                category=str(row.get("category") or "stage1b_v5_risky_miss"),
                action_family=str(row.get("action_family") or subtype_dataset.action_family_for_route(expected_route)),
                template_family=infer_stage1b_v5_template_family(row),
                source="router_holdout_1000_v5_diagnostic_risky_subtype_miss",
                training_role="stage1b_v5_hard_positive",
                context_flags=dict(row.get("context_flags") or {}),
                required_context_flags=list(row.get("required_context_flags") or []),
                rejected_route=actual_route if actual_route in router_gate.ROUTE_TO_CODE else None,
            )
        )
    records.extend(generated_stage1b_v5_records())
    return subtype_dataset.dedupe_by_text_code(records)


def generated_stage1b_v5_records() -> list[dict[str, Any]]:
    templates = {
        "console.edit_file": [
            "Edit the safe-lane subtype source file.",
            "Patch the route-gate evaluation test.",
            "Modify the risky subtype training file.",
            "Update the local router source file.",
            "Apply the patch to the route-gate test file.",
        ],
        "console.run_command": [
            "pls exec fresh holdout gate",
            "execute the hybrid gate command now",
            "run the fresh holdout gate now",
            "run the local pytest command for hybrid gates",
            "execute the PowerShell command that checks router files",
        ],
        "memory.save_preference": [
            "remember concise router updates pls",
            "remember that I prefer concise router updates",
            "save my preference for clean holdout first",
            "remember concise safety reports",
            "save that I prefer short router summaries",
        ],
        "agent.start_job": [
            "start a background job to review routing artifacts",
            "launch the long-running safe-lane analysis task",
            "begin a broader agent review of the router corpus",
        ],
        "vision.edit_image": [
            "edit this screenshot to hide the username",
            "blur the background of the uploaded image",
            "retouch the image and remove private text",
        ],
    }
    records: list[dict[str, Any]] = []
    for route, texts in templates.items():
        for index, text in enumerate(texts, start=1):
            records.append(
                subtype_dataset.stage1_record(
                    record_id=f"stage1b_v5_generated_{route_code(route)}_{index:03d}",
                    text=f"{text} V5 risky subtype recovery case {index}.",
                    expected_route=route,
                    category="stage1b_v5_risky_generated",
                    action_family=subtype_dataset.action_family_for_route(route),
                    template_family=f"stage1b_v5_recovery:generated:{route.replace('.', '_')}",
                    source="stage1b_v5_recovery_generated",
                    training_role="stage1b_v5_balanced_positive",
                    context_flags={"HAS_IMAGE": True} if route == "vision.edit_image" else {},
                    required_context_flags=["HAS_IMAGE"] if route == "vision.edit_image" else [],
                )
            )
    return records


def build_stage0_recovery_dataset(result_paths: list[Path], output_path: Path = DEFAULT_STAGE0_OUTPUT) -> dict[str, Any]:
    rows = extract_stage0_recovery_records(result_paths)
    write_jsonl(output_path, rows)
    manifest = {
        "dataset": "router_stage0_v5_recovery",
        "output": str(output_path),
        "source_results": [str(path) for path in result_paths],
        "row_count": len(rows),
        "route_counts": dict(sorted(Counter(row["route"] for row in rows).items())),
        "stage0_label_counts": dict(sorted(Counter(row["stage0_label"] for row in rows).items())),
        "training_role_counts": dict(sorted(Counter(row["training_role"] for row in rows).items())),
        "must_not_emit_g04_count": sum(1 for row in rows if row["must_not_emit_g04"]),
        "hash": classifier.train_data_hash(rows),
    }
    manifest_path = output_path.with_suffix(".manifest.json")
    write_json(manifest_path, manifest)
    manifest["manifest"] = str(manifest_path)
    return manifest


def build_stage1b_recovery_dataset(
    *,
    result_paths: list[Path],
    base_dataset_dir: Path = DEFAULT_STAGE1_BASE_DIR,
    output_dir: Path = DEFAULT_STAGE1_OUTPUT_DIR,
) -> dict[str, Any]:
    base_splits = subtype_dataset.load_base_splits(base_dataset_dir)
    extra_records = extract_stage1b_recovery_records(result_paths)
    paths = subtype_dataset.write_augmented_splits(base_splits=base_splits, extra_records=extra_records, output_dir=output_dir)
    all_records = [record for split in ("train", "dev", "calibration", "focused") for record in read_jsonl(paths[split])]
    extra_path = output_dir / "router_stage1b_v5_recovery_records.jsonl"
    write_jsonl(extra_path, extra_records)
    manifest = {
        "dataset": "router_stage1b_v5_recovery",
        "base_dataset_dir": str(base_dataset_dir),
        "source_results": [str(path) for path in result_paths],
        "output_dir": str(output_dir),
        "extra_count": len(extra_records),
        "extra_route_counts": dict(sorted(Counter(record["route"] for record in extra_records).items())),
        "extra_training_role_counts": dict(sorted(Counter(record["training_role"] for record in extra_records).items())),
        "split_counts": {split: len(read_jsonl(path)) for split, path in paths.items()},
        "stage1a_train_count": sum(1 for record in read_jsonl(paths["train"]) if record["code"] in classifier.SAFE_READ_ROUTE_CODES),
        "stage1b_train_count": sum(1 for record in read_jsonl(paths["train"]) if record["code"] in classifier.RISKY_ROUTE_CODES),
        "stage1c_train_count": sum(1 for record in read_jsonl(paths["train"]) if record["code"] in classifier.SAFE_STAGE_CODES),
        "paths": {split: str(path) for split, path in paths.items()},
        "extra_records": str(extra_path),
        "hash": classifier.train_data_hash(all_records),
    }
    manifest_path = output_dir / "router_stage1b_v5_recovery_manifest.json"
    write_json(manifest_path, manifest)
    manifest["paths"]["manifest"] = str(manifest_path)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build v5 recovery data for Stage 0 and risky Stage1B.")
    parser.add_argument("--result", type=Path, action="append", default=None)
    parser.add_argument("--stage0-output", type=Path, default=DEFAULT_STAGE0_OUTPUT)
    parser.add_argument("--stage1-base-dir", type=Path, default=DEFAULT_STAGE1_BASE_DIR)
    parser.add_argument("--stage1-output-dir", type=Path, default=DEFAULT_STAGE1_OUTPUT_DIR)
    args = parser.parse_args(argv)
    result_paths = args.result or [DEFAULT_V5_RESULT]
    payload = {
        "stage0": build_stage0_recovery_dataset(result_paths, output_path=args.stage0_output),
        "stage1b": build_stage1b_recovery_dataset(
            result_paths=result_paths,
            base_dataset_dir=args.stage1_base_dir,
            output_dir=args.stage1_output_dir,
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
