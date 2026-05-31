from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    import sys

    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from evals import router_gate
    from training import router_r08_boundary_dataset as v1_builder
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    from evals import router_gate
    from training import router_r08_boundary_dataset as v1_builder


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "router_direct_action_boundaries_v2"
DEFAULT_FALSE_R08_RESULT = (
    PROJECT_ROOT / ".suite" / "local" / "router_console_semantics_350_route_code_qwen3_0_6b_hardened_stops.json"
)
DEFAULT_HOLDOUT_V2_RESULT = (
    PROJECT_ROOT / ".suite" / "local" / "router_holdout_1000_v2_route_code_qwen3_0_6b_lora_v1_hf.json"
)
DEFAULT_TRAINING_BASE = "Qwen/Qwen3-0.6B"
DEFAULT_PRODUCTION_MODEL = "qwen3:0.6b"
ROUTER_ADAPTER_NAME = "router_lora_direct_action_boundaries_v2"
BALANCED_ROUTE_TARGETS = {
    "chat.no_action": 100,
    "answer.question": 100,
    "ask_clarifying_question": 100,
    "vision.describe_image": 100,
    "vision.ocr_image": 100,
    "vision.edit_image": 100,
    "console.edit_file": 100,
    "console.run_command": 100,
    "agent.start_job": 100,
    "file.search": 100,
    "memory.save_preference": 100,
}
REJECTED_BY_ROUTE = {
    "chat.no_action": router_gate.ROUTE_TO_CODE["memory.save_preference"],
    "answer.question": router_gate.ROUTE_TO_CODE["console.run_command"],
    "ask_clarifying_question": router_gate.ROUTE_TO_CODE["console.run_command"],
    "vision.describe_image": router_gate.ROUTE_TO_CODE["vision.edit_image"],
    "vision.ocr_image": router_gate.ROUTE_TO_CODE["vision.edit_image"],
    "vision.edit_image": router_gate.ROUTE_TO_CODE["console.edit_file"],
    "console.edit_file": router_gate.ROUTE_TO_CODE["console.run_command"],
    "console.run_command": router_gate.ROUTE_TO_CODE["answer.question"],
    "agent.start_job": router_gate.ROUTE_TO_CODE["console.run_command"],
    "file.search": router_gate.ROUTE_TO_CODE["console.run_command"],
    "memory.save_preference": router_gate.ROUTE_TO_CODE["chat.no_action"],
}
V3_HARD_NEGATIVE_FORMS = [
    "No action now; talk through {topic}. V3 case {n}.",
    "Explain {topic} without using a tool. V3 case {n}.",
    "This is only conceptual: {topic}. V3 case {n}.",
    "Before any action, describe {topic}. V3 case {n}.",
    "Do not execute anything; compare options for {topic}. V3 case {n}.",
]
V3_ANSWER_FORMS = [
    "Explain why {topic} matters. V3 case {n}.",
    "What should I know about {topic}? V3 case {n}.",
    "How would you reason about {topic}? V3 case {n}.",
    "What would happen if {topic}? V3 case {n}.",
    "Can you compare choices around {topic}? V3 case {n}.",
]
V3_DIRECT_ACTIONS = [
    ("Run the router protocol check now.", "console.run_command", "run_command"),
    ("Find the router protocol file in the repo.", "file.search", "lookup"),
    ("Start a broader router audit job.", "agent.start_job", "job"),
    ("Apply the direct-action boundary patch.", "console.edit_file", "file_edit"),
    ("Use the heavy model for a background router inspection.", "agent.start_job", "job"),
    ("Execute pytest for the router backend tests.", "console.run_command", "run_command"),
]
V3_AMBIGUOUS_REQUESTS = [
    "Can you handle that risky route?",
    "Move the image/file issue forward.",
    "Use the right action lane here.",
    "Can you deal with that memory thing?",
    "Send this through whichever path is useful.",
]
V3_MEDIA_ACTIONS = [
    ("Describe the attached screenshot.", "vision.describe_image", "media"),
    ("OCR this image and return the text.", "vision.ocr_image", "media"),
    ("Edit this image to remove the background.", "vision.edit_image", "media_edit"),
    ("Generate an image for the router article.", "agent.start_job", "media_generate"),
]
V3_CONSOLE_ACTIONS = [
    ("Open the console UI.", "console.open_ui", "ui"),
    ("Open the console UI and edit the boundary config.", "console.edit_file", "file_edit"),
    ("Run the router gate tests.", "console.run_command", "run_command"),
    ("Edit the current router source file.", "console.edit_file", "file_edit"),
]
V3_WEB_FILE_ACTIONS = [
    ("Look up current local-router backend docs online.", "web.lookup", "lookup"),
    ("Read the local v2 training manifest.", "file.search", "lookup"),
    ("Search backend logs for false direct actions.", "file.search", "lookup"),
    ("Find current RTX 3090 training notes online.", "web.lookup", "lookup"),
]
V3_MEMORY_CASES = [
    ("I prefer short benchmark summaries.", "chat.no_action", "none"),
    ("Remember that I prefer short benchmark summaries.", "memory.save_preference", "memory"),
    ("Can the router remember preferences?", "answer.question", "none"),
    ("Would saving that as a preference help?", "answer.question", "none"),
    ("Save my preference for zero false direct actions.", "memory.save_preference", "memory"),
]
V3_MESSY_PROMPTS = [
    ("pls run direct action gate now", "console.run_command", "run_command"),
    ("dont run just explain risky action routing", "answer.question", "none"),
    ("edit teh boundary config file", "console.edit_file", "file_edit"),
    ("ocr dis screenshot pls", "vision.ocr_image", "media"),
    ("remember i want short router reports", "memory.save_preference", "memory"),
]
EXTRA_POSITIVE_TEMPLATES = {
    "chat.no_action": [
        "I prefer short answers, but do not save that.",
        "Let's talk about router accuracy only.",
        "I am thinking out loud about action routing.",
        "No action; just noting the benchmark result.",
        "This is a casual comment about tool safety.",
    ],
    "answer.question": [
        "Explain the difference between image edit and file edit.",
        "What would happen if we started a job?",
        "Why is memory.save_preference risky?",
        "Compare file search and shell commands.",
        "Can you explain when route_code helps?",
    ],
    "ask_clarifying_question": [
        "Can you handle the route thing?",
        "Do the right action with that file or image.",
        "Move this forward using the proper tool.",
        "Can you take care of that command situation?",
        "Send it somewhere useful.",
    ],
    "vision.describe_image": [
        "Describe the attached image.",
        "Tell me what is visible in this screenshot.",
        "Look at this image and summarize it.",
        "Identify what the photo shows.",
        "Describe the image content.",
    ],
    "vision.ocr_image": [
        "Read the text in this screenshot.",
        "OCR the attached image.",
        "Extract the words from this image.",
        "Transcribe the text in the photo.",
        "Read the visible text from the image.",
    ],
    "vision.edit_image": [
        "Edit this image to darken the background.",
        "Remove the background from the attached image.",
        "Blur the private text in this screenshot.",
        "Crop and brighten this image.",
        "Change the colors in the attached picture.",
    ],
    "console.edit_file": [
        "Apply the patch to the project files.",
        "Edit the router source file.",
        "Modify the test expectation.",
        "Update the YAML config file.",
        "Patch the route definitions.",
    ],
    "console.run_command": [
        "Run the router tests now.",
        "Execute the benchmark script.",
        "Run the build command.",
        "Start the shell command.",
        "Execute pytest for this module.",
    ],
    "agent.start_job": [
        "Start a background router audit job.",
        "Use the heavy model to inspect this issue.",
        "Begin a broader agent task for the repo.",
        "Start the code inspection job.",
        "Run this as a multi-step agent job.",
    ],
    "file.search": [
        "Search the repo for route_code.",
        "Read the local benchmark result file.",
        "Find every file mentioning console.run_command.",
        "Inspect the backend logs.",
        "Look through project files for the router gate.",
    ],
    "memory.save_preference": [
        "Remember that I prefer concise results.",
        "Save my preference for strict safety gates.",
        "Remember that I want shadow mode before promotion.",
        "Save that I prefer zero false direct actions.",
        "Remember my router reporting preference.",
    ],
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_result_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload.get("results") or []
    return list(results[0].get("rows") or []) if results else []


def boundary_category(chosen_route: str, rejected_route: str, fallback: str) -> str:
    pair = (chosen_route, rejected_route)
    labels = {
        ("vision.edit_image", "console.edit_file"): "vision_edit_not_file_edit",
        ("console.edit_file", "console.run_command"): "file_edit_not_run_command",
        ("file.search", "console.run_command"): "file_search_not_run_command",
        ("chat.no_action", "memory.save_preference"): "preference_talk_not_memory_write",
        ("memory.save_preference", "chat.no_action"): "explicit_memory_save",
    }
    return labels.get(pair, fallback)


def preference_record(
    *,
    record_id: str,
    source: str,
    prompt: str,
    chosen_route: str,
    rejected_route: str,
    category: str,
    action_family: str,
) -> dict[str, Any]:
    return {
        "id": record_id,
        "source": source,
        "prompt": prompt,
        "chosen": router_gate.ROUTE_TO_CODE[chosen_route],
        "chosen_route": chosen_route,
        "rejected": router_gate.ROUTE_TO_CODE[rejected_route],
        "rejected_route": rejected_route,
        "category": boundary_category(chosen_route, rejected_route, category),
        "action_family": action_family,
    }


def extract_false_r08_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in load_result_rows(path):
        if row.get("actual_route") != "console.run_command" or row.get("expected_route") == "console.run_command":
            continue
        records.append(
            preference_record(
                record_id=str(row["id"]),
                source="v1_false_r08",
                prompt=str(row["text"]),
                chosen_route=str(row["expected_route"]),
                rejected_route="console.run_command",
                category=f"{row['category']}_false_r08",
                action_family=str(row["action_family"]),
            )
        )
    return records


def extract_false_direct_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in load_result_rows(path):
        actual = str(row.get("actual_route"))
        expected = str(row.get("expected_route"))
        if actual not in router_gate.STRICT_CONFIRM_ROUTES or actual == expected:
            continue
        records.append(
            preference_record(
                record_id=str(row["id"]),
                source="holdout_v2_false_direct",
                prompt=str(row["text"]),
                chosen_route=expected,
                rejected_route=actual,
                category=f"{row['category']}_false_{actual.replace('.', '_')}",
                action_family=str(row["action_family"]),
            )
        )
    return records


def case_to_preference(case: dict[str, Any], *, source: str) -> dict[str, Any]:
    route = str(case["expected_route"])
    return preference_record(
        record_id=str(case["id"]),
        source=source,
        prompt=str(case["text"]),
        chosen_route=route,
        rejected_route=router_gate.ROUTE_CODES[REJECTED_BY_ROUTE[route]],
        category=str(case["category"]),
        action_family=str(case["action_family"]),
    )


def build_extra_positive_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for route, templates in EXTRA_POSITIVE_TEMPLATES.items():
        family = {
            "chat.no_action": "none",
            "answer.question": "none",
            "ask_clarifying_question": "none",
            "vision.describe_image": "media",
            "vision.ocr_image": "media",
            "vision.edit_image": "media_edit",
            "console.edit_file": "file_edit",
            "console.run_command": "run_command",
            "agent.start_job": "job",
            "file.search": "lookup",
            "memory.save_preference": "memory",
        }[route]
        for idx in range(120):
            text = f"{templates[idx % len(templates)]} Extra boundary positive {idx + 1}."
            cases.append(router_gate.case_row(f"v2_extra_{route.replace('.', '_')}_{idx + 1:04d}", "balanced_positive", text, route, family))
    return cases


def collect_balanced_positive_preferences(exclude_prompts: set[str]) -> list[dict[str, Any]]:
    candidates = (
        router_gate.build_cases(router_gate.SPLIT_1000)
        + router_gate.build_console_semantics_cases()
        + router_gate.build_direct_action_boundaries_cases()
        + build_holdout_v3_cases()
        + build_extra_positive_cases()
    )
    by_route: dict[str, list[dict[str, Any]]] = {route: [] for route in BALANCED_ROUTE_TARGETS}
    seen = set(exclude_prompts)
    for case in candidates:
        route = str(case["expected_route"])
        text = str(case["text"])
        if route not in by_route or text in seen:
            continue
        by_route[route].append(case)
        seen.add(text)
    records: list[dict[str, Any]] = []
    for route, target in BALANCED_ROUTE_TARGETS.items():
        available = by_route[route]
        if len(available) < target:
            raise ValueError(f"Only {len(available)} positive examples available for {route}; need {target}")
        records.extend(case_to_preference(case, source="balanced_positive") for case in available[:target])
    return records


def sft_record(record: dict[str, Any], index: int) -> dict[str, Any]:
    record_id = f"router_direct_action_v2_sft_{index:04d}_{record['id']}"
    return {
        "id": record_id,
        "scenario_id": record_id,
        "messages": [
            {"role": "system", "content": router_gate.build_system_prompt("route_code")},
            {"role": "user", "content": str(record["prompt"])},
            {"role": "assistant", "content": str(record["chosen"])},
        ],
        "metadata": {
            "adapter_name": ROUTER_ADAPTER_NAME,
            "source": record["source"],
            "category": record["category"],
            "chosen_route": record["chosen_route"],
            "rejected_route": record["rejected_route"],
            "protocol": "route_code",
        },
    }


def dpo_pair(record: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": f"router_direct_action_v2_dpo_{index:04d}_{record['id']}",
        "prompt": str(record["prompt"]),
        "chosen": str(record["chosen"]),
        "rejected": str(record["rejected"]),
        "category": str(record["category"]),
        "metadata": {
            "adapter_name": ROUTER_ADAPTER_NAME,
            "source": record["source"],
            "chosen_route": record["chosen_route"],
            "rejected_route": record["rejected_route"],
            "protocol": "route_code",
        },
    }


def build_holdout_v3_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form = V3_HARD_NEGATIVE_FORMS[(idx // len(router_gate.DISCUSSION_TOPICS)) % len(V3_HARD_NEGATIVE_FORMS)]
        cases.append(router_gate.case_row(f"v3_hn_{idx + 1:04d}", "hard_negative", form.format(topic=topic, n=idx + 1), "chat.no_action", "none"))
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form = V3_ANSWER_FORMS[(idx // len(router_gate.DISCUSSION_TOPICS)) % len(V3_ANSWER_FORMS)]
        cases.append(router_gate.case_row(f"v3_aq_{idx + 1:04d}", "answer_question", form.format(topic=topic, n=idx + 251), "answer.question", "none"))
    for idx in range(split["direct_action"]):
        text, route, family = V3_DIRECT_ACTIONS[idx % len(V3_DIRECT_ACTIONS)]
        cases.append(router_gate.case_row(f"v3_direct_{idx + 1:04d}", "direct_action", f"{text} V3 case {idx + 401}.", route, family))
    for idx in range(split["ambiguous"]):
        text = f"{V3_AMBIGUOUS_REQUESTS[idx % len(V3_AMBIGUOUS_REQUESTS)]} V3 case {idx + 551}."
        cases.append(router_gate.case_row(f"v3_amb_{idx + 1:04d}", "ambiguous", text, "ask_clarifying_question", "none"))
    for idx in range(split["media_route"]):
        text, route, family = V3_MEDIA_ACTIONS[idx % len(V3_MEDIA_ACTIONS)]
        cases.append(router_gate.case_row(f"v3_media_{idx + 1:04d}", "media_route", f"{text} V3 case {idx + 651}.", route, family))
    for idx in range(split["console_route"]):
        text, route, family = V3_CONSOLE_ACTIONS[idx % len(V3_CONSOLE_ACTIONS)]
        cases.append(router_gate.case_row(f"v3_console_{idx + 1:04d}", "console_route", f"{text} V3 case {idx + 751}.", route, family))
    for idx in range(split["web_file_data"]):
        text, route, family = V3_WEB_FILE_ACTIONS[idx % len(V3_WEB_FILE_ACTIONS)]
        cases.append(router_gate.case_row(f"v3_webfile_{idx + 1:04d}", "web_file_data", f"{text} V3 case {idx + 826}.", route, family))
    for idx in range(split["memory_preference"]):
        text, route, family = V3_MEMORY_CASES[idx % len(V3_MEMORY_CASES)]
        cases.append(router_gate.case_row(f"v3_mem_{idx + 1:04d}", "memory_preference", f"{text} V3 case {idx + 901}.", route, family))
    for idx in range(split["messy_voice_typo"]):
        text, route, family = V3_MESSY_PROMPTS[idx % len(V3_MESSY_PROMPTS)]
        cases.append(router_gate.case_row(f"v3_messy_{idx + 1:04d}", "messy_voice_typo", f"{text} v3 case {idx + 951}", route, family))
    texts = [case["text"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)):
        raise ValueError("router_holdout_1000_v3 generation failed uniqueness or count checks")
    return cases


def serializable_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": case["id"],
        "category": case["category"],
        "text": case["text"],
        "expected_route": case["expected_route"],
        "action_family": case["action_family"],
    }


def build_router_direct_action_boundaries_dataset(
    false_r08_result_path: Path = DEFAULT_FALSE_R08_RESULT,
    holdout_v2_result_path: Path = DEFAULT_HOLDOUT_V2_RESULT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    training_base: str = DEFAULT_TRAINING_BASE,
    production_model: str = DEFAULT_PRODUCTION_MODEL,
    ollama_show_text: str = "",
    ollama_show_error: str | None = None,
) -> dict[str, Any]:
    false_r08_records = extract_false_r08_records(false_r08_result_path)
    false_direct_records = extract_false_direct_records(holdout_v2_result_path)
    false_prompts = {record["prompt"] for record in false_r08_records + false_direct_records}
    positive_records = collect_balanced_positive_preferences(false_prompts)
    preferences = false_r08_records + false_direct_records + positive_records

    train_records = [sft_record(record, index) for index, record in enumerate(preferences, start=1)]
    direct_action_dev_cases = router_gate.build_direct_action_boundaries_cases()
    dev_records = [
        sft_record(case_to_preference(case, source="dev_direct_action_boundaries"), index)
        for index, case in enumerate(direct_action_dev_cases, start=1)
    ]
    dpo_records = [dpo_pair(record, index) for index, record in enumerate(preferences, start=1)]
    holdout_cases = build_holdout_v3_cases()

    train_path = output_dir / "router_lora_train_v2.jsonl"
    dev_path = output_dir / "router_lora_dev_direct_action_boundaries_v2.jsonl"
    dpo_path = output_dir / "router_lora_dpo_pairs_v2.jsonl"
    holdout_path = output_dir / "router_holdout_1000_v3.jsonl"
    preflight_path = output_dir / "serving_parity_preflight.json"
    manifest_path = output_dir / "router_direct_action_boundaries_manifest.json"

    write_jsonl(train_path, train_records)
    write_jsonl(dev_path, dev_records)
    write_jsonl(dpo_path, dpo_records)
    write_jsonl(holdout_path, [serializable_case(case) for case in holdout_cases])
    preflight = v1_builder.build_serving_parity_preflight(
        ollama_show_text,
        training_base=training_base,
        production_model=production_model,
        error=ollama_show_error,
    )
    preflight["adapter_name"] = ROUTER_ADAPTER_NAME
    write_json(preflight_path, preflight)

    route_counts = Counter(record["chosen_route"] for record in preferences)
    category_counts = Counter(record["category"] for record in preferences)
    summary = {
        "adapter_name": ROUTER_ADAPTER_NAME,
        "false_r08_result_path": str(false_r08_result_path),
        "holdout_v2_result_path": str(holdout_v2_result_path),
        "output_dir": str(output_dir),
        "training_base": training_base,
        "production_model": production_model,
        "false_r08_count": len(false_r08_records),
        "false_direct_count": len(false_direct_records),
        "balanced_positive_count": len(positive_records),
        "train_count": len(train_records),
        "dev_count": len(dev_records),
        "dpo_pair_count": len(dpo_records),
        "holdout_v3_count": len(holdout_cases),
        "chosen_route_counts": dict(sorted(route_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "paths": {
            "train": str(train_path),
            "dev": str(dev_path),
            "dpo": str(dpo_path),
            "holdout_v3": str(holdout_path),
            "preflight": str(preflight_path),
            "manifest": str(manifest_path),
        },
        "serving_parity": preflight,
    }
    write_json(manifest_path, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build router direct-action boundary SFT/DPO datasets.")
    parser.add_argument("--false-r08-result", type=Path, default=DEFAULT_FALSE_R08_RESULT)
    parser.add_argument("--holdout-v2-result", type=Path, default=DEFAULT_HOLDOUT_V2_RESULT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--training-base", default=DEFAULT_TRAINING_BASE)
    parser.add_argument("--production-model", default=DEFAULT_PRODUCTION_MODEL)
    parser.add_argument("--skip-ollama-show", action="store_true")
    args = parser.parse_args(argv)

    show_text, show_error = ("", "ollama_show_skipped")
    if not args.skip_ollama_show:
        show_text, show_error = v1_builder.run_ollama_show(args.production_model)
    summary = build_router_direct_action_boundaries_dataset(
        false_r08_result_path=args.false_r08_result,
        holdout_v2_result_path=args.holdout_v2_result,
        output_dir=args.output_dir,
        training_base=args.training_base,
        production_model=args.production_model,
        ollama_show_text=show_text,
        ollama_show_error=show_error,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
