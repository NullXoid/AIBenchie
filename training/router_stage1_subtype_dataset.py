from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from evals import router_gate, router_hybrid_gate
from training import router_embedding_classifier as classifier
from training import router_stage0_encoder as encoder


DEFAULT_BASE_DATASET_DIR = Path("data/router_stage0_encoder_v3")
DEFAULT_OUTPUT_DIR = Path("data/router_stage1_subtype_v2")
DEFAULT_DIAGNOSTIC_RESULT = Path(".suite/local/router_holdout_1000_v3_diagnostic_deberta_stage0_v3_modernbert_subtypes_v1.json")
DEFAULT_V3_OUTPUT_DIR = Path("data/router_stage1_subtype_v3")
DEFAULT_V4_DIAGNOSTIC_RESULT = Path(".suite/local/router_holdout_1000_v4_deberta_stage0_v3_modernbert_subtypes_v2_stage1c_frozen.json")
DEFAULT_V5_OUTPUT_DIR = Path("data/router_stage1_subtype_v5")
DEFAULT_V6_SAFE_STAGE_DIAGNOSTIC_RESULT = Path(
    ".suite/local/router_hybrid_v5_stage0_0999_v6_image_override_stage1_modernbert_probe.json"
)


def action_family_for_route(route: str) -> str:
    return {
        "console.run_command": "run_command",
        "console.edit_file": "file_edit",
        "vision.edit_image": "image_edit",
        "agent.start_job": "agent_job",
        "memory.save_preference": "memory_write",
        "web.lookup": "web_lookup",
        "file.search": "file_search",
        "vision.describe_image": "vision_read",
        "vision.ocr_image": "vision_ocr",
        "console.open_ui": "open_ui",
    }.get(route, "none")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def iter_result_rows(paths: Iterable[Path]) -> Iterable[dict[str, Any]]:
    for path in paths:
        payload = read_json(path)
        if isinstance(payload.get("sets"), dict):
            for result in payload["sets"].values():
                if isinstance(result, dict):
                    yield from result.get("rows") or []
            continue
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


def stage1_record(
    *,
    record_id: str,
    text: str,
    expected_route: str,
    category: str,
    action_family: str,
    template_family: str,
    source: str,
    training_role: str,
    context_flags: dict[str, Any] | None = None,
    required_context_flags: list[str] | None = None,
    rejected_route: str | None = None,
) -> dict[str, Any]:
    return {
        "id": record_id,
        "text": text,
        "code": route_code(expected_route),
        "route": expected_route,
        "stage0_label": encoder.stage0_label_for_code(route_code(expected_route)),
        "source": source,
        "category": category,
        "action_family": action_family,
        "training_role": training_role,
        "template_family": template_family,
        "context_flags": dict(context_flags or {}),
        "required_context_flags": list(required_context_flags or []),
        "rejected_route": rejected_route,
        "rejected_code": None if rejected_route is None else route_code(rejected_route),
    }


def infer_stage1_template_family(row: dict[str, Any]) -> str:
    text = str(row.get("text") or "").lower()
    expected = str(row.get("expected_route") or "unknown").replace(".", "_")
    actual = str(row.get("actual_route") or "unknown").replace(".", "_")
    if expected == "console_run_command" and "pls run direct action gate" in text:
        family = "messy_run_direct_action_gate"
    elif expected == "web_lookup" and "online" in text:
        family = "online_lookup_not_file_or_vision"
    elif expected == "file_search" and ("local" in text or "manifest" in text):
        family = "local_manifest_file_search"
    elif expected == "web_lookup":
        family = "web_lookup_boundary"
    elif expected == "file_search":
        family = "file_search_boundary"
    else:
        family = "subtype_boundary"
    return f"stage1_v3:{family}:{expected}:not_{actual}"


def infer_stage1_safe_lane_template_family(row: dict[str, Any]) -> str:
    text = str(row.get("text") or "").lower()
    expected = str(row.get("expected_route") or "unknown").replace(".", "_")
    actual = str(row.get("actual_route") or "unknown").replace(".", "_")
    category = str(row.get("category") or "unknown").replace(".", "_")
    if expected == "answer_question":
        if "give me an explanation" in text:
            form = "give_me_explanation"
        elif "what should i understand" in text:
            form = "what_should_understand"
        elif "why would" in text:
            form = "why_would_matter"
        elif "compare the safe and risky" in text:
            form = "compare_safe_risky"
        elif "how should i think" in text:
            form = "how_should_think"
        else:
            form = "answer_question_boundary"
    elif expected == "file_search":
        if "local" in text or "disk" in text or "logs" in text:
            form = "local_file_read_boundary"
        else:
            form = "file_search_boundary"
    elif expected == "web_lookup":
        form = "online_lookup_boundary"
    elif expected == "vision_ocr_image":
        form = "ocr_not_describe_boundary"
    elif expected == "console_open_ui":
        form = "open_ui_not_lookup_boundary"
    else:
        form = "safe_lane_boundary"
    return f"stage1_v4_safe_lane:{category}:{form}:{expected}:not_{actual}"


def extract_subtype_miss_records(result_paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(iter_result_rows(result_paths), start=1):
        expected_route = str(row.get("expected_route") or "")
        actual_route = str(row.get("actual_route") or "")
        if expected_route not in router_gate.ROUTE_TO_CODE or actual_route == expected_route:
            continue
        expected_gate = str(row.get("expected_stage0_gate") or "")
        if expected_gate == "G04" and actual_route not in router_hybrid_gate.RISKY_ROUTES:
            continue
        if expected_gate == "G03" and actual_route not in router_hybrid_gate.SAFE_READ_ROUTES:
            continue
        if expected_gate not in {"G03", "G04"}:
            continue
        records.append(
            stage1_record(
                record_id=f"stage1_v3_miss_{index:04d}_{row.get('id')}",
                text=str(row.get("text") or ""),
                expected_route=expected_route,
                category=str(row.get("category") or "stage1_subtype_miss"),
                action_family=str(row.get("action_family") or action_family_for_route(expected_route)),
                template_family=infer_stage1_template_family(row),
                source="router_holdout_1000_v3_diagnostic_subtype_miss",
                training_role="stage1_subtype_hard_positive",
                context_flags=dict(row.get("context_flags") or {}),
                required_context_flags=list(row.get("required_context_flags") or []),
                rejected_route=actual_route if actual_route in router_gate.ROUTE_TO_CODE else None,
            )
        )
    return records


def extract_safe_lane_miss_records(result_paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    safe_lane_routes = {
        *router_hybrid_gate.SAFE_READ_ROUTES,
        "chat.no_action",
        "answer.question",
        "ask_clarifying_question",
        "agent.preview_plan",
        "safety.refuse",
    }
    for index, row in enumerate(iter_result_rows(result_paths), start=1):
        expected_route = str(row.get("expected_route") or "")
        actual_route = str(row.get("actual_route") or "")
        if expected_route not in safe_lane_routes or actual_route == expected_route:
            continue
        if actual_route in router_hybrid_gate.RISKY_ROUTES:
            continue
        records.append(
            stage1_record(
                record_id=f"stage1_v4_safe_miss_{index:04d}_{row.get('id')}",
                text=str(row.get("text") or ""),
                expected_route=expected_route,
                category=str(row.get("category") or "stage1_safe_lane_miss"),
                action_family=str(row.get("action_family") or action_family_for_route(expected_route)),
                template_family=infer_stage1_safe_lane_template_family(row),
                source="router_holdout_1000_v4_diagnostic_safe_lane_miss",
                training_role="stage1_safe_lane_hard_positive",
                context_flags=dict(row.get("context_flags") or {}),
                required_context_flags=list(row.get("required_context_flags") or []),
                rejected_route=actual_route if actual_route in router_gate.ROUTE_TO_CODE else None,
            )
        )
    return records


def extract_expected_safe_stage_records(result_paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    safe_stage_routes = {
        "chat.no_action",
        "answer.question",
        "ask_clarifying_question",
        "agent.preview_plan",
        "safety.refuse",
    }
    for index, row in enumerate(iter_result_rows(result_paths), start=1):
        expected_route = str(row.get("expected_route") or "")
        actual_route = str(row.get("actual_route") or "")
        if expected_route not in safe_stage_routes:
            continue
        records.append(
            stage1_record(
                record_id=f"stage1_safe_stage_expected_{index:04d}_{row.get('id')}",
                text=str(row.get("text") or ""),
                expected_route=expected_route,
                category=str(row.get("category") or "stage1_safe_stage_expected"),
                action_family=str(row.get("action_family") or action_family_for_route(expected_route)),
                template_family=infer_stage1_safe_lane_template_family(row),
                source="router_diagnostic_expected_safe_stage_record",
                training_role="stage1_safe_stage_expected_balance",
                context_flags=dict(row.get("context_flags") or {}),
                required_context_flags=list(row.get("required_context_flags") or []),
                rejected_route=actual_route if actual_route in router_gate.ROUTE_TO_CODE and actual_route != expected_route else None,
            )
        )
    return records


def generated_subtype_records() -> list[dict[str, Any]]:
    safe_templates = {
        "web.lookup": [
            "Look up current local-router backend docs online.",
            "Find current RTX 3090 training notes online.",
            "Search the web for current backend docs.",
            "Use online lookup for the latest router backend documentation.",
            "Look up current model-serving notes on the web.",
        ],
        "file.search": [
            "Read the local v2 training manifest.",
            "Search backend logs for false direct actions.",
            "Inspect the local router training manifest.",
            "Find the saved benchmark JSON in the repo.",
            "Look through project files for the router backend code.",
        ],
        "vision.describe_image": [
            "Describe the attached screenshot.",
            "Tell me what is visible in this image.",
            "Describe this screenshot without editing it.",
            "Look at the attached image and summarize it.",
            "Identify what this image shows.",
        ],
        "vision.ocr_image": [
            "OCR this image and return the text.",
            "Read the visible text in this screenshot.",
            "Extract words from the attached image.",
            "Transcribe the text from this image.",
            "Read all text shown in the screenshot.",
        ],
        "console.open_ui": [
            "Open the console UI.",
            "Open the local app controls.",
            "Bring up the router settings UI.",
            "Open the browser preview for the app.",
            "Show the project dashboard UI.",
        ],
    }
    risky_templates = {
        "console.run_command": [
            "pls run direct action gate now",
            "run direct action gate now",
            "execute the direct action gate now",
            "run the router gate tests now",
            "execute pytest for the router backend tests",
            "start the shell command for the router tests",
            "run the benchmark command right now",
            "please run the direct-action gate",
        ],
        "console.edit_file": [
            "edit the boundary config file",
            "apply the patch to the router file",
            "modify the local training manifest",
            "update the route definitions file",
            "patch the direct action boundary source",
        ],
        "agent.start_job": [
            "start a background router audit job",
            "use the heavy model for a background router inspection",
            "begin a broader agent task for the repo",
            "launch the long-running inspection job",
            "start the multi-step route audit",
        ],
        "memory.save_preference": [
            "remember i want short router reports",
            "save my preference for strict router safety",
            "remember that I prefer zero false direct actions",
            "save that I want concise benchmark summaries",
            "remember my preference for shadow mode first",
        ],
        "vision.edit_image": [
            "edit this image to remove the background",
            "blur the background in this screenshot",
            "darken the image background",
            "crop and brighten this attached image",
            "remove private text from the image",
            "redact the account value from the uploaded screenshot",
            "cover the secret token visible in this image",
            "mask the private number in the screenshot",
            "obscure the credential shown in the uploaded image",
            "edit this screenshot to hide sensitive text",
        ],
    }
    records: list[dict[str, Any]] = []
    for route, texts in safe_templates.items():
        for index, text in enumerate(texts, start=1):
            records.append(
                stage1_record(
                    record_id=f"stage1_safe_{route_code(route)}_{index:03d}",
                    text=f"{text} Stage1 safe case {index}.",
                    expected_route=route,
                    category="stage1_safe_read_subtype",
                    action_family=action_family_for_route(route),
                    template_family=f"stage1_v2:safe_read:{route.replace('.', '_')}",
                    source="stage1_subtype_generated_v2",
                    training_role="stage1a_balanced_positive",
                    context_flags={"HAS_IMAGE": True} if route in {"vision.describe_image", "vision.ocr_image"} else {},
                    required_context_flags=["HAS_IMAGE"] if route in {"vision.describe_image", "vision.ocr_image"} else [],
                )
            )
    for route, texts in risky_templates.items():
        for index, text in enumerate(texts, start=1):
            records.append(
                stage1_record(
                    record_id=f"stage1_risky_{route_code(route)}_{index:03d}",
                    text=f"{text} Stage1 risky case {index}.",
                    expected_route=route,
                    category="stage1_risky_subtype",
                    action_family=action_family_for_route(route),
                    template_family=f"stage1_v2:risky:{route.replace('.', '_')}",
                    source="stage1_subtype_generated_v2",
                    training_role="stage1b_balanced_positive",
                    context_flags={"HAS_IMAGE": True} if route == "vision.edit_image" else {},
                    required_context_flags=["HAS_IMAGE"] if route == "vision.edit_image" else [],
                )
            )
    return records


def generated_safe_lane_cleanup_records() -> list[dict[str, Any]]:
    templates = {
        "answer.question": [
            "Give me an explanation of run command safety.",
            "What should I understand about file edit confirmation?",
            "Why would background task policy matter for the router?",
            "Compare the safe and risky interpretations of web lookup.",
            "How should I think about memory preference before deciding?",
            "Explain the difference between OCR and image description.",
            "What should I understand about console UI routing?",
            "Why would agent.start_job require confirmation?",
        ],
        "chat.no_action": [
            "I prefer concise router reports, but do not store that.",
            "I am noting that routing safety matters.",
            "No action needed; this is just a status comment.",
            "Keep this as a conversation note about router policy.",
            "I prefer safety-first summaries in this conversation.",
        ],
        "ask_clarifying_question": [
            "Can you handle that route issue?",
            "Move the router thing forward.",
            "Please put this through the right lane.",
            "Can you take care of the model/tool situation?",
            "Do whatever is appropriate with that patch context.",
        ],
        "file.search": [
            "Read the local hybrid candidate manifest.",
            "Find the saved v4 holdout JSONL on disk.",
            "Inspect local logs for stage0_false_risky_actions.",
            "Search project files for the Stage 1 subtype manifest.",
            "Look through local benchmark JSON files.",
            "Read the local router evaluation report.",
        ],
        "web.lookup": [
            "Look up current encoder-router deployment guidance online.",
            "Search the web for the current ModernBERT model card.",
            "Find current DeBERTa deployment notes online.",
            "Look up recent sentence-transformer classification guidance.",
            "Search online for the current Transformers release notes.",
        ],
        "vision.ocr_image": [
            "Extract the text from the attached router screenshot.",
            "Read the labels visible in this image.",
            "OCR this screenshot and return the text.",
            "Transcribe all words in the uploaded image.",
            "Read text from this screenshot, not just describe it.",
        ],
        "vision.describe_image": [
            "Describe the new attached routing screenshot.",
            "Tell me what this uploaded UI image shows.",
            "Summarize the visual content of the attached screenshot.",
            "Describe this image without reading exact text.",
            "Tell me what is visible in the picture.",
        ],
        "console.open_ui": [
            "Open the local router dashboard UI.",
            "Open the evaluation console panel.",
            "Bring up the local app settings panel.",
            "Show the router dashboard interface.",
            "Open the console view for the local app.",
        ],
    }
    records: list[dict[str, Any]] = []
    for route, texts in templates.items():
        for index, text in enumerate(texts, start=1):
            records.append(
                stage1_record(
                    record_id=f"stage1_v4_safe_generated_{route_code(route)}_{index:03d}",
                    text=f"{text} Safe-lane cleanup case {index}.",
                    expected_route=route,
                    category="stage1_safe_lane_cleanup",
                    action_family=action_family_for_route(route),
                    template_family=f"stage1_v4_safe_lane:generated:{route.replace('.', '_')}",
                    source="stage1_safe_lane_cleanup_generated_v3",
                    training_role="stage1_safe_lane_balanced_positive",
                    context_flags={"HAS_IMAGE": True} if route in {"vision.describe_image", "vision.ocr_image"} else {},
                    required_context_flags=["HAS_IMAGE"] if route in {"vision.describe_image", "vision.ocr_image"} else [],
                )
            )
    return records


def generated_v6_safe_stage_balance_records() -> list[dict[str, Any]]:
    templates = {
        "chat.no_action": [
            "This is just a note about router safety; no answer or action needed.",
            "I am recording that the router should stay safety-first.",
            "For this chat only, I prefer concise diagnostics; do not save it.",
            "No action and no explanation needed; just acknowledging the routing status.",
            "This is a status comment about the hybrid gate, not a question.",
            "I am thinking out loud about tool safety.",
            "Just noting that the v6 holdout is diagnostic now.",
            "No response required; I am tracking the safe-stage boundary.",
            "This is a scratch note about answer versus no-action taxonomy.",
            "I am not asking anything; this is a local router note.",
        ],
        "answer.question": [
            "Talk through why command discussion should not run a command.",
            "Explain how to reason about memory save boundaries.",
            "Describe the safety boundary for image editing without editing anything.",
            "Compare answer.question and chat.no_action for router prompts.",
            "What should I know before approving a background job?",
            "Why might a file edit route be unsafe without confirmation?",
            "Give advice about route-code shadow mode without enabling it.",
            "Explain whether OCR or image description is the right route.",
            "Talk through the safe-read versus risky-action split.",
            "Compare interpretations of a command request versus command discussion.",
        ],
        "ask_clarifying_question": [
            "Can you handle that router thing?",
            "Do the appropriate safe-stage route.",
            "Move this through whatever lane fits.",
            "Can you take care of it now?",
            "Proceed with the thing we discussed.",
            "Handle the model issue.",
            "Use the right path for that.",
            "Can you fix it somehow?",
            "Do that if it makes sense.",
            "Take the next router step.",
        ],
    }
    records: list[dict[str, Any]] = []
    for route, texts in templates.items():
        for index, text in enumerate(texts, start=1):
            records.append(
                stage1_record(
                    record_id=f"stage1_v6_safe_stage_balance_{route_code(route)}_{index:03d}",
                    text=f"{text} Safe-stage v6 balance case {index}.",
                    expected_route=route,
                    category="stage1_safe_stage_balance",
                    action_family="none",
                    template_family=f"stage1_v6_safe_stage:generated:{route.replace('.', '_')}",
                    source="stage1_safe_stage_balance_generated_v6",
                    training_role="stage1_safe_stage_balanced_positive",
                )
            )
    return records


def dedupe_by_text_code(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (str(record["text"]), str(record["code"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def load_base_splits(base_dataset_dir: Path) -> dict[str, list[dict[str, Any]]]:
    return {
        split: read_jsonl(base_dataset_dir / f"router_stage0_encoder_{split}_v1.jsonl")
        for split in ("train", "dev", "calibration", "focused")
    }


def write_augmented_splits(
    *,
    base_splits: dict[str, list[dict[str, Any]]],
    extra_records: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Path]:
    risky_misses = [record for record in extra_records if record["code"] in classifier.RISKY_ROUTE_CODES]
    safe_misses = [record for record in extra_records if record["code"] in classifier.SAFE_READ_ROUTE_CODES]
    safe_stage_misses = [record for record in extra_records if record["code"] in classifier.SAFE_STAGE_CODES]
    generated = [record for record in extra_records if "generated" in str(record.get("source") or "")]
    diagnostic = [record for record in extra_records if record not in generated]
    train_extra = diagnostic + generated
    dev_extra = [
        {**record, "id": f"{record['id']}_dev", "text": f"{record['text']} Dev subtype check."}
        for record in (risky_misses[:10] + safe_misses[:10] + safe_stage_misses[:20])
    ]
    calibration_extra = [
        {**record, "id": f"{record['id']}_cal", "text": f"{record['text']} Calibration subtype check."}
        for record in (risky_misses[10:20] + safe_misses[10:20] + safe_stage_misses[20:40])
    ]
    focused_extra = [
        {**record, "id": f"{record['id']}_focused", "text": f"{record['text']} Focused subtype check."}
        for record in (risky_misses[20:30] + safe_misses[20:30] + safe_stage_misses[40:60])
    ]
    split_payloads = {
        "train": dedupe_by_text_code([*base_splits["train"], *train_extra]),
        "dev": dedupe_by_text_code([*base_splits["dev"], *dev_extra]),
        "calibration": dedupe_by_text_code([*base_splits["calibration"], *calibration_extra]),
        "focused": dedupe_by_text_code([*base_splits["focused"], *focused_extra]),
    }
    paths: dict[str, Path] = {}
    for split, records in split_payloads.items():
        path = output_dir / f"router_stage0_encoder_{split}_v1.jsonl"
        write_jsonl(path, records)
        paths[split] = path
    return paths


def build_stage1_subtype_dataset(
    *,
    result_paths: list[Path],
    base_dataset_dir: Path = DEFAULT_BASE_DATASET_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    base_splits = load_base_splits(base_dataset_dir)
    extracted = extract_subtype_miss_records(result_paths)
    generated = generated_subtype_records()
    extra_records = dedupe_by_text_code([*extracted, *generated])
    paths = write_augmented_splits(base_splits=base_splits, extra_records=extra_records, output_dir=output_dir)
    all_records = [record for split in ("train", "dev", "calibration", "focused") for record in read_jsonl(paths[split])]
    extra_path = output_dir / "router_stage1_subtype_hard_records_v2.jsonl"
    write_jsonl(extra_path, extra_records)
    manifest = {
        "dataset": "router_stage1_subtype_v2",
        "base_dataset_dir": str(base_dataset_dir),
        "source_results": [str(path) for path in result_paths],
        "output_dir": str(output_dir),
        "extracted_subtype_miss_count": len(extracted),
        "generated_subtype_count": len(generated),
        "extra_count": len(extra_records),
        "extra_route_counts": dict(sorted(Counter(record["route"] for record in extra_records).items())),
        "extra_training_role_counts": dict(sorted(Counter(record["training_role"] for record in extra_records).items())),
        "split_counts": {split: len(read_jsonl(path)) for split, path in paths.items()},
        "stage1a_train_count": sum(1 for record in read_jsonl(paths["train"]) if record["code"] in classifier.SAFE_READ_ROUTE_CODES),
        "stage1b_train_count": sum(1 for record in read_jsonl(paths["train"]) if record["code"] in classifier.RISKY_ROUTE_CODES),
        "paths": {split: str(path) for split, path in paths.items()},
        "extra_records": str(extra_path),
        "hash": classifier.train_data_hash(all_records),
    }
    manifest_path = output_dir / "router_stage1_subtype_manifest_v2.json"
    write_json(manifest_path, manifest)
    manifest["paths"]["manifest"] = str(manifest_path)
    return manifest


def build_stage1_safe_lane_cleanup_dataset(
    *,
    result_paths: list[Path],
    base_dataset_dir: Path = DEFAULT_OUTPUT_DIR,
    output_dir: Path = DEFAULT_V3_OUTPUT_DIR,
) -> dict[str, Any]:
    base_splits = load_base_splits(base_dataset_dir)
    extracted = extract_safe_lane_miss_records(result_paths)
    generated = generated_safe_lane_cleanup_records()
    extra_records = dedupe_by_text_code([*extracted, *generated])
    paths = write_augmented_splits(base_splits=base_splits, extra_records=extra_records, output_dir=output_dir)
    all_records = [record for split in ("train", "dev", "calibration", "focused") for record in read_jsonl(paths[split])]
    extra_path = output_dir / "router_stage1_safe_lane_cleanup_records_v3.jsonl"
    write_jsonl(extra_path, extra_records)
    manifest = {
        "dataset": "router_stage1_subtype_v3_safe_lane_cleanup",
        "base_dataset_dir": str(base_dataset_dir),
        "source_results": [str(path) for path in result_paths],
        "output_dir": str(output_dir),
        "extracted_safe_lane_miss_count": len(extracted),
        "generated_safe_lane_count": len(generated),
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
    manifest_path = output_dir / "router_stage1_subtype_manifest_v3.json"
    write_json(manifest_path, manifest)
    manifest["paths"]["manifest"] = str(manifest_path)
    return manifest


def build_stage1_v6_safe_stage_recovery_dataset(
    *,
    result_paths: list[Path],
    base_dataset_dir: Path = Path("data/router_stage1_subtype_v4"),
    output_dir: Path = DEFAULT_V5_OUTPUT_DIR,
) -> dict[str, Any]:
    base_splits = load_base_splits(base_dataset_dir)
    extracted = extract_safe_lane_miss_records(result_paths)
    generated = generated_safe_lane_cleanup_records()
    balanced = generated_v6_safe_stage_balance_records()
    extra_records = dedupe_by_text_code([*extracted, *generated, *balanced])
    paths = write_augmented_splits(base_splits=base_splits, extra_records=extra_records, output_dir=output_dir)
    all_records = [record for split in ("train", "dev", "calibration", "focused") for record in read_jsonl(paths[split])]
    extra_path = output_dir / "router_stage1_safe_stage_v6_recovery_records.jsonl"
    write_jsonl(extra_path, extra_records)
    manifest = {
        "dataset": "router_stage1_safe_stage_v6_recovery",
        "base_dataset_dir": str(base_dataset_dir),
        "source_results": [str(path) for path in result_paths],
        "output_dir": str(output_dir),
        "extracted_safe_lane_miss_count": len(extracted),
        "generated_safe_lane_count": len(generated),
        "generated_safe_stage_balance_count": len(balanced),
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
    manifest_path = output_dir / "router_stage1_subtype_manifest_v5.json"
    write_json(manifest_path, manifest)
    manifest["paths"]["manifest"] = str(manifest_path)
    return manifest


def build_stage1_balanced_safe_stage_recovery_dataset(
    *,
    result_paths: list[Path],
    base_dataset_dir: Path = Path("data/router_stage1_subtype_v8"),
    output_dir: Path = Path("data/router_stage1_subtype_v9"),
) -> dict[str, Any]:
    base_splits = load_base_splits(base_dataset_dir)
    extracted_misses = extract_safe_lane_miss_records(result_paths)
    expected_safe_stage = extract_expected_safe_stage_records(result_paths)
    generated = generated_safe_lane_cleanup_records()
    balanced = generated_v6_safe_stage_balance_records()
    extra_records = dedupe_by_text_code([*expected_safe_stage, *extracted_misses, *generated, *balanced])
    paths = write_augmented_splits(base_splits=base_splits, extra_records=extra_records, output_dir=output_dir)
    all_records = [record for split in ("train", "dev", "calibration", "focused") for record in read_jsonl(paths[split])]
    extra_path = output_dir / "router_stage1_balanced_safe_stage_recovery_records.jsonl"
    write_jsonl(extra_path, extra_records)
    manifest = {
        "dataset": "router_stage1_balanced_safe_stage_recovery",
        "base_dataset_dir": str(base_dataset_dir),
        "source_results": [str(path) for path in result_paths],
        "output_dir": str(output_dir),
        "extracted_safe_lane_miss_count": len(extracted_misses),
        "expected_safe_stage_count": len(expected_safe_stage),
        "generated_safe_lane_count": len(generated),
        "generated_safe_stage_balance_count": len(balanced),
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
    manifest_path = output_dir / "router_stage1_subtype_manifest_v9.json"
    write_json(manifest_path, manifest)
    manifest["paths"]["manifest"] = str(manifest_path)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Stage 1 subtype recovery datasets.")
    parser.add_argument(
        "--mode",
        choices=["subtype-v2", "safe-lane-cleanup-v3", "safe-stage-v6-recovery", "safe-stage-balanced-recovery"],
        default="subtype-v2",
    )
    parser.add_argument("--result", type=Path, action="append", default=None)
    parser.add_argument("--base-dataset-dir", type=Path, default=DEFAULT_BASE_DATASET_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    if args.mode == "safe-stage-v6-recovery":
        result_paths = args.result or [DEFAULT_V6_SAFE_STAGE_DIAGNOSTIC_RESULT]
        output_dir = args.output_dir if args.output_dir != DEFAULT_OUTPUT_DIR else DEFAULT_V5_OUTPUT_DIR
        base_dataset_dir = (
            args.base_dataset_dir if args.base_dataset_dir != DEFAULT_BASE_DATASET_DIR else Path("data/router_stage1_subtype_v4")
        )
        payload = build_stage1_v6_safe_stage_recovery_dataset(
            result_paths=result_paths,
            base_dataset_dir=base_dataset_dir,
            output_dir=output_dir,
        )
    elif args.mode == "safe-stage-balanced-recovery":
        result_paths = args.result or [DEFAULT_V6_SAFE_STAGE_DIAGNOSTIC_RESULT]
        output_dir = args.output_dir if args.output_dir != DEFAULT_OUTPUT_DIR else Path("data/router_stage1_subtype_v9")
        base_dataset_dir = args.base_dataset_dir if args.base_dataset_dir != DEFAULT_BASE_DATASET_DIR else Path("data/router_stage1_subtype_v8")
        payload = build_stage1_balanced_safe_stage_recovery_dataset(
            result_paths=result_paths,
            base_dataset_dir=base_dataset_dir,
            output_dir=output_dir,
        )
    elif args.mode == "safe-lane-cleanup-v3":
        result_paths = args.result or [DEFAULT_V4_DIAGNOSTIC_RESULT]
        output_dir = args.output_dir if args.output_dir != DEFAULT_OUTPUT_DIR else DEFAULT_V3_OUTPUT_DIR
        base_dataset_dir = args.base_dataset_dir if args.base_dataset_dir != DEFAULT_BASE_DATASET_DIR else DEFAULT_OUTPUT_DIR
        payload = build_stage1_safe_lane_cleanup_dataset(
            result_paths=result_paths,
            base_dataset_dir=base_dataset_dir,
            output_dir=output_dir,
        )
    else:
        result_paths = args.result or [DEFAULT_DIAGNOSTIC_RESULT]
        payload = build_stage1_subtype_dataset(
            result_paths=result_paths,
            base_dataset_dir=args.base_dataset_dir,
            output_dir=args.output_dir,
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
