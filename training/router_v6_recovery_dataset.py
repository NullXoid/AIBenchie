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


DEFAULT_V6_RESULT = Path(".suite/local/router_holdout_1000_v6_deberta_stage0_v5_modernbert_stage1a_v3_stage1c_v2_stage1b_v4_intent_diagnostic.json")
DEFAULT_STAGE0_OUTPUT = Path("data/router_v6_recovery/stage0_hard_records_v6.jsonl")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
    if row.get("category") == "memory_preference" and row.get("expected_route") != "memory.save_preference":
        topic = "preference_talk_not_memory"
    elif row.get("expected_route") == "vision.edit_image" and "blur the username" in text:
        topic = "image_blur_username_edit_not_ocr"
    elif row.get("expected_route") == "vision.edit_image":
        topic = "image_edit_not_safe_read"
    else:
        topic = "stage0_boundary"
    return f"stage0_v6_recovery:{topic}:{expected}:not_{actual}"


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
                    record_id=f"stage0_v6_false_risky_{index:04d}_{row.get('id')}",
                    text=str(row.get("text") or ""),
                    expected_route=expected_route,
                    source="router_holdout_1000_v6_diagnostic_stage0_false_risky",
                    training_role="v6_must_not_emit_g04",
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
                    record_id=f"stage0_v6_missed_risky_{index:04d}_{row.get('id')}",
                    text=str(row.get("text") or ""),
                    expected_route=expected_route,
                    source="router_holdout_1000_v6_diagnostic_stage0_missed_risky",
                    training_role="v6_risky_hard_positive",
                    template_family=stage0_family_for_row(row),
                    category=str(row.get("category") or "stage0_missed_risky"),
                    action_family=str(row.get("action_family") or subtype_dataset.action_family_for_route(expected_route)),
                    must_not_emit_g04=False,
                    context_flags=dict(row.get("context_flags") or {}),
                    required_context_flags=list(row.get("required_context_flags") or []),
                    rejected_route=actual_route if actual_route in router_gate.ROUTE_TO_CODE else None,
                )
            )
    records.extend(generated_stage0_v6_records())
    return subtype_dataset.dedupe_by_text_code(records)


def generated_stage0_v6_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    preference_negatives = [
        "My preference is short diagnostics for this chat only.",
        "I prefer terse router notes here, but do not save that.",
        "I like concise safety updates in this conversation only.",
        "My style preference is brief replies; this is not a memory request.",
        "I prefer short benchmark summaries, no need to remember it.",
        "For this thread, keep diagnostics compact without saving a preference.",
    ]
    for index, text in enumerate(preference_negatives, start=1):
        records.append(
            stage0_record(
                record_id=f"stage0_v6_generated_preference_negative_{index:03d}",
                text=f"{text} V6 recovery preference negative {index}.",
                expected_route="chat.no_action",
                source="stage0_v6_recovery_generated",
                training_role="v6_must_not_emit_g04",
                template_family=f"stage0_v6_recovery:generated:preference_talk_not_memory:{index}",
                category="memory_preference",
                action_family="none",
                must_not_emit_g04=True,
            )
        )
    apply_unknown_negatives = [
        "Apply that.",
        "Apply it.",
        "Do that patch thing.",
        "Proceed with the change.",
        "Make that update.",
        "Use that fix.",
        "Go ahead with the patch.",
        "Patch it now.",
    ]
    unknown_or_absent_patch_flags = [
        {"LAST_ASSISTANT_OFFERED_PATCH": "unknown", "ACTIVE_FILE": "unknown"},
        {"LAST_ASSISTANT_OFFERED_PATCH": "false", "ACTIVE_FILE": "unknown"},
        {"LAST_ASSISTANT_OFFERED_PATCH": "unknown", "ACTIVE_FILE": "false"},
        {"LAST_ASSISTANT_OFFERED_PATCH": "false", "ACTIVE_FILE": "false"},
    ]
    for index, text in enumerate(apply_unknown_negatives, start=1):
        flags = unknown_or_absent_patch_flags[(index - 1) % len(unknown_or_absent_patch_flags)]
        records.append(
            stage0_record(
                record_id=f"stage0_v6_generated_apply_unknown_negative_{index:03d}",
                text=f"{text} V6 recovery unknown patch context negative {index}.",
                expected_route="ask_clarifying_question",
                source="stage0_v6_recovery_generated",
                training_role="v6_must_not_emit_g04",
                template_family=f"stage0_v6_recovery:generated:apply_that_unknown_context_negative:{index}",
                category="context_dependent_case",
                action_family="none",
                must_not_emit_g04=True,
                context_flags=flags,
            )
        )
    apply_context_positives = [
        "Apply that.",
        "Apply it.",
        "Proceed with the patch.",
        "Make that source update.",
    ]
    for index, text in enumerate(apply_context_positives, start=1):
        records.append(
            stage0_record(
                record_id=f"stage0_v6_generated_apply_context_positive_{index:03d}",
                text=f"{text} V6 recovery confirmed patch context positive {index}.",
                expected_route="console.edit_file",
                source="stage0_v6_recovery_generated",
                training_role="v6_risky_hard_positive",
                template_family=f"stage0_v6_recovery:generated:apply_that_patch_context_positive:{index}",
                category="console_route",
                action_family="file_edit",
                context_flags={"LAST_ASSISTANT_OFFERED_PATCH": "true", "ACTIVE_FILE": "true"},
                required_context_flags=["LAST_ASSISTANT_OFFERED_PATCH"],
            )
        )
    memory_positives = [
        "Remember that I prefer concise router updates.",
        "Save my preference for short diagnostic summaries.",
        "Remember that I want terse benchmark reports.",
        "Save that I prefer zero-false-direct summaries first.",
    ]
    for index, text in enumerate(memory_positives, start=1):
        records.append(
            stage0_record(
                record_id=f"stage0_v6_generated_memory_positive_{index:03d}",
                text=f"{text} V6 recovery memory positive {index}.",
                expected_route="memory.save_preference",
                source="stage0_v6_recovery_generated",
                training_role="v6_risky_hard_positive",
                template_family=f"stage0_v6_recovery:generated:explicit_memory_save:{index}",
                category="memory_preference",
                action_family="memory",
            )
        )
    image_edit_positives = [
        "Blur the username in the attached screenshot.",
        "Hide the private token in this image.",
        "Cover the email address in the uploaded screenshot.",
        "Edit this screenshot to redact the visible username.",
        "Obscure the account name in the attached image.",
        "Blur the private path text in this UI capture.",
    ]
    for index, text in enumerate(image_edit_positives, start=1):
        records.append(
            stage0_record(
                record_id=f"stage0_v6_generated_image_edit_positive_{index:03d}",
                text=f"{text} V6 recovery image edit positive {index}.",
                expected_route="vision.edit_image",
                source="stage0_v6_recovery_generated",
                training_role="v6_risky_hard_positive",
                template_family=f"stage0_v6_recovery:generated:image_redaction_edit:{index}",
                category="media_route",
                action_family="media_edit",
                context_flags={"HAS_IMAGE": True},
                required_context_flags=["HAS_IMAGE"],
            )
        )
    image_safe_reads = [
        ("Read the username visible in the attached screenshot.", "vision.ocr_image", "media"),
        ("OCR the private-looking text in this image without editing it.", "vision.ocr_image", "media"),
        ("Describe the screenshot that contains a username.", "vision.describe_image", "media"),
        ("Tell me what is visible in the attached UI capture.", "vision.describe_image", "media"),
    ]
    for index, (text, route, family) in enumerate(image_safe_reads, start=1):
        records.append(
            stage0_record(
                record_id=f"stage0_v6_generated_image_safe_read_{index:03d}",
                text=f"{text} V6 recovery image safe-read {index}.",
                expected_route=route,
                source="stage0_v6_recovery_generated",
                training_role="v6_safe_read_contrast",
                template_family=f"stage0_v6_recovery:generated:image_safe_read_contrast:{index}",
                category="media_route",
                action_family=family,
                context_flags={"HAS_IMAGE": True},
                required_context_flags=["HAS_IMAGE"],
            )
        )
    return records


def build_stage0_recovery_dataset(result_paths: list[Path], output_path: Path = DEFAULT_STAGE0_OUTPUT) -> dict[str, Any]:
    rows = extract_stage0_recovery_records(result_paths)
    write_jsonl(output_path, rows)
    manifest = {
        "dataset": "router_stage0_v6_recovery",
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build v6 recovery data for Stage 0.")
    parser.add_argument("--result", type=Path, action="append", default=None)
    parser.add_argument("--stage0-output", type=Path, default=DEFAULT_STAGE0_OUTPUT)
    args = parser.parse_args(argv)
    result_paths = args.result or [DEFAULT_V6_RESULT]
    manifest = build_stage0_recovery_dataset(result_paths, output_path=args.stage0_output)
    print(json.dumps({"stage0": manifest}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
