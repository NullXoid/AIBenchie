from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    import sys

    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from evals import router_gate
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    from evals import router_gate


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "router_r08_boundary_v1"
DEFAULT_FOCUSED_RESULT = (
    PROJECT_ROOT / ".suite" / "local" / "router_console_semantics_350_route_code_qwen3_0_6b.json"
)
DEFAULT_TRAINING_BASE = "Qwen/Qwen3-0.6B"
DEFAULT_PRODUCTION_MODEL = "qwen3:0.6b"
ROUTER_ADAPTER_NAME = "router_lora_r08_boundary_v1"
FALSE_R08_REJECTED = router_gate.ROUTE_TO_CODE["console.run_command"]
BALANCED_ROUTE_TARGETS = {
    "console.run_command": 100,
    "console.edit_file": 100,
    "file.search": 100,
    "answer.question": 100,
    "ask_clarifying_question": 100,
    "chat.no_action": 100,
}
REJECTED_BY_ROUTE = {
    "console.run_command": router_gate.ROUTE_TO_CODE["answer.question"],
    "console.edit_file": FALSE_R08_REJECTED,
    "file.search": FALSE_R08_REJECTED,
    "answer.question": FALSE_R08_REJECTED,
    "ask_clarifying_question": FALSE_R08_REJECTED,
    "chat.no_action": FALSE_R08_REJECTED,
}

V2_HARD_NEGATIVE_FORMS = [
    "No action now: explain {topic}. V2 case {n}.",
    "This is only discussion about {topic}; do not execute anything. V2 case {n}.",
    "Talk through {topic} without using tools. V2 case {n}.",
    "I am asking conceptually about {topic}, not asking you to act. V2 case {n}.",
    "Before any action, explain {topic}. V2 case {n}.",
]
V2_ANSWER_FORMS = [
    "Explain the tradeoff around {topic}. V2 case {n}.",
    "What should I know about {topic}? V2 case {n}.",
    "Why would {topic} matter? V2 case {n}.",
    "Compare options for {topic}. V2 case {n}.",
    "What would happen if {topic}? V2 case {n}.",
]
V2_DIRECT_ACTIONS = [
    ("Run the focused router tests now.", "console.run_command", "run_command"),
    ("Find the intent router file in this repo.", "file.search", "lookup"),
    ("Start a background inspection job for the router.", "agent.start_job", "job"),
    ("Apply the route-code patch to the current files.", "console.edit_file", "file_edit"),
    ("Use the heavy model to inspect this issue.", "agent.start_job", "job"),
    ("Execute pytest for the router gate module.", "console.run_command", "run_command"),
]
V2_AMBIGUOUS_REQUESTS = [
    "Can you handle that router thing?",
    "Move the file issue forward.",
    "Use whatever route makes sense here.",
    "Can you deal with the command problem?",
    "Send this through the right path.",
]
V2_MEDIA_ACTIONS = [
    ("Describe the attached image.", "vision.describe_image", "media"),
    ("Read the text from this screenshot.", "vision.ocr_image", "media"),
    ("Edit this image by removing the background.", "vision.edit_image", "media_edit"),
    ("Generate an image for this design idea.", "agent.start_job", "media_generate"),
]
V2_CONSOLE_ACTIONS = [
    ("Open the console UI in the app.", "console.open_ui", "ui"),
    ("Open the console UI and change the router prompt file.", "console.edit_file", "file_edit"),
    ("Run the backend regression tests.", "console.run_command", "run_command"),
    ("Edit the current source file in the console UI.", "console.edit_file", "file_edit"),
]
V2_WEB_FILE_ACTIONS = [
    ("Look up current router model releases online.", "web.lookup", "lookup"),
    ("Read the local router gate result file.", "file.search", "lookup"),
    ("Search backend logs for failed router decisions.", "file.search", "lookup"),
    ("Find current GPU prices on the web.", "web.lookup", "lookup"),
]
V2_MEMORY_CASES = [
    ("I prefer short router summaries.", "chat.no_action", "none"),
    ("Remember that I prefer short router summaries.", "memory.save_preference", "memory"),
    ("Can this system remember routing preferences?", "answer.question", "none"),
    ("Would saving that preference help routing?", "answer.question", "none"),
    ("Save my preference for strict router safety gates.", "memory.save_preference", "memory"),
]
V2_MESSY_PROMPTS = [
    ("pls run router pytests now", "console.run_command", "run_command"),
    ("dont run it just explain command safety", "answer.question", "none"),
    ("edit teh current router file", "console.edit_file", "file_edit"),
    ("what wud file search do no action", "answer.question", "none"),
    ("find router gate file pls", "file.search", "lookup"),
]


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


def parse_ollama_show(text: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {"capabilities": [], "parameters": {}}
    current_section = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in {"Model", "Capabilities", "Parameters", "License"}:
            current_section = line.lower()
            continue
        parts = line.split()
        if current_section == "model" and len(parts) >= 2:
            key = parts[0].lower().replace(" ", "_")
            if parts[0].lower() == "parameters":
                key = "parameter_count"
            elif len(parts) >= 3 and parts[0].lower() == "context" and parts[1].lower() == "length":
                key = "context_length"
                parts = [parts[0], *parts[2:]]
            elif len(parts) >= 3 and parts[0].lower() == "embedding" and parts[1].lower() == "length":
                key = "embedding_length"
                parts = [parts[0], *parts[2:]]
            metadata[key] = " ".join(parts[1:])
        elif current_section == "capabilities":
            metadata["capabilities"].append(line)
        elif current_section == "parameters" and len(parts) >= 2:
            metadata["parameters"][parts[0]] = " ".join(parts[1:])
    return metadata


def run_ollama_show(model: str) -> tuple[str, str | None]:
    try:
        result = subprocess.run(
            ["ollama", "show", model],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except Exception as exc:
        return "", str(exc)
    if result.returncode != 0:
        return result.stdout, result.stderr.strip() or f"ollama show failed with exit code {result.returncode}"
    return result.stdout, None


def build_serving_parity_preflight(
    ollama_show_text: str,
    *,
    training_base: str = DEFAULT_TRAINING_BASE,
    production_model: str = DEFAULT_PRODUCTION_MODEL,
    error: str | None = None,
) -> dict[str, Any]:
    metadata = parse_ollama_show(ollama_show_text) if ollama_show_text else {}
    blockers: list[str] = []
    if error:
        blockers.append("ollama_show_failed")
    if metadata.get("quantization"):
        blockers.append("production_model_is_quantized")
    blockers.append("merged_or_adapter_serving_parity_not_proven")
    return {
        "adapter_name": ROUTER_ADAPTER_NAME,
        "training_base": training_base,
        "training_backend": "hf_peft",
        "production_backend": "ollama",
        "production_model": production_model,
        "production_model_metadata": metadata,
        "serving_paths_to_prove": [
            "evaluate base plus LoRA through hf_transformers/PEFT",
            "merge adapter or serve active adapter in intended backend",
            "rerun router_protocol_200 and router_console_semantics_350 through production-equivalent backend",
        ],
        "promotion_eligible": False,
        "parity_blockers": blockers,
        "error": error,
    }


def focused_false_r08_records(result_payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = result_payload.get("results") or []
    if not results:
        return []
    rows = results[0].get("rows") or []
    records: list[dict[str, Any]] = []
    for row in rows:
        if row.get("actual_route") != "console.run_command" or row.get("expected_route") == "console.run_command":
            continue
        records.append(
            {
                "id": str(row["id"]),
                "source": "focused_false_r08",
                "prompt": str(row["text"]),
                "chosen": str(row["expected_output"]),
                "chosen_route": str(row["expected_route"]),
                "rejected": FALSE_R08_REJECTED,
                "rejected_route": "console.run_command",
                "category": f"{row['category']}_false_r08",
                "action_family": str(row["action_family"]),
            }
        )
    return records


def load_false_r08_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        loaded = read_jsonl(path)
        return [record for record in loaded if record.get("rejected_route") == "console.run_command"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    return focused_false_r08_records(payload)


def case_to_preference(case: dict[str, Any], *, source: str, rejected: str | None = None) -> dict[str, Any]:
    route = str(case["expected_route"])
    return {
        "id": str(case["id"]),
        "source": source,
        "prompt": str(case["text"]),
        "chosen": router_gate.ROUTE_TO_CODE[route],
        "chosen_route": route,
        "rejected": rejected or REJECTED_BY_ROUTE.get(route, FALSE_R08_REJECTED),
        "rejected_route": router_gate.ROUTE_CODES.get(rejected or REJECTED_BY_ROUTE.get(route, FALSE_R08_REJECTED), "unknown"),
        "category": str(case["category"]),
        "action_family": str(case["action_family"]),
    }


def collect_balanced_positive_preferences(exclude_prompts: set[str]) -> list[dict[str, Any]]:
    candidates = (
        router_gate.build_cases(router_gate.SPLIT_1000)
        + router_gate.build_console_semantics_cases()
        + build_holdout_v2_cases()
    )
    by_route: dict[str, list[dict[str, Any]]] = {route: [] for route in BALANCED_ROUTE_TARGETS}
    seen: set[str] = set(exclude_prompts)
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
    record_id = f"router_r08_sft_{index:04d}_{record['id']}"
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
        "id": f"router_r08_dpo_{index:04d}_{record['id']}",
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


def build_holdout_v2_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form = V2_HARD_NEGATIVE_FORMS[(idx // len(router_gate.DISCUSSION_TOPICS)) % len(V2_HARD_NEGATIVE_FORMS)]
        cases.append(router_gate.case_row(f"v2_hn_{idx + 1:04d}", "hard_negative", form.format(topic=topic, n=idx + 1), "chat.no_action", "none"))
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form = V2_ANSWER_FORMS[(idx // len(router_gate.DISCUSSION_TOPICS)) % len(V2_ANSWER_FORMS)]
        cases.append(router_gate.case_row(f"v2_aq_{idx + 1:04d}", "answer_question", form.format(topic=topic, n=idx + 251), "answer.question", "none"))
    for idx in range(split["direct_action"]):
        text, route, family = V2_DIRECT_ACTIONS[idx % len(V2_DIRECT_ACTIONS)]
        cases.append(router_gate.case_row(f"v2_direct_{idx + 1:04d}", "direct_action", f"{text} V2 case {idx + 401}.", route, family))
    for idx in range(split["ambiguous"]):
        text = f"{V2_AMBIGUOUS_REQUESTS[idx % len(V2_AMBIGUOUS_REQUESTS)]} V2 case {idx + 551}."
        cases.append(router_gate.case_row(f"v2_amb_{idx + 1:04d}", "ambiguous", text, "ask_clarifying_question", "none"))
    for idx in range(split["media_route"]):
        text, route, family = V2_MEDIA_ACTIONS[idx % len(V2_MEDIA_ACTIONS)]
        cases.append(router_gate.case_row(f"v2_media_{idx + 1:04d}", "media_route", f"{text} V2 case {idx + 651}.", route, family))
    for idx in range(split["console_route"]):
        text, route, family = V2_CONSOLE_ACTIONS[idx % len(V2_CONSOLE_ACTIONS)]
        cases.append(router_gate.case_row(f"v2_console_{idx + 1:04d}", "console_route", f"{text} V2 case {idx + 751}.", route, family))
    for idx in range(split["web_file_data"]):
        text, route, family = V2_WEB_FILE_ACTIONS[idx % len(V2_WEB_FILE_ACTIONS)]
        cases.append(router_gate.case_row(f"v2_webfile_{idx + 1:04d}", "web_file_data", f"{text} V2 case {idx + 826}.", route, family))
    for idx in range(split["memory_preference"]):
        text, route, family = V2_MEMORY_CASES[idx % len(V2_MEMORY_CASES)]
        cases.append(router_gate.case_row(f"v2_mem_{idx + 1:04d}", "memory_preference", f"{text} V2 case {idx + 901}.", route, family))
    for idx in range(split["messy_voice_typo"]):
        text, route, family = V2_MESSY_PROMPTS[idx % len(V2_MESSY_PROMPTS)]
        cases.append(router_gate.case_row(f"v2_messy_{idx + 1:04d}", "messy_voice_typo", f"{text} v2 case {idx + 951}", route, family))
    texts = [case["text"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)):
        raise ValueError("router_holdout_1000_v2 generation failed uniqueness or count checks")
    return cases


def serializable_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": case["id"],
        "category": case["category"],
        "text": case["text"],
        "expected_route": case["expected_route"],
        "action_family": case["action_family"],
    }


def build_router_r08_boundary_dataset(
    focused_result_path: Path = DEFAULT_FOCUSED_RESULT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    training_base: str = DEFAULT_TRAINING_BASE,
    production_model: str = DEFAULT_PRODUCTION_MODEL,
    ollama_show_text: str = "",
    ollama_show_error: str | None = None,
) -> dict[str, Any]:
    false_records = load_false_r08_records(focused_result_path)
    false_prompts = {record["prompt"] for record in false_records}
    positive_records = collect_balanced_positive_preferences(false_prompts)
    preferences = false_records + positive_records
    train_records = [sft_record(record, index) for index, record in enumerate(preferences, start=1)]

    dev_cases = router_gate.build_console_semantics_cases()
    dev_records = [
        sft_record(case_to_preference(case, source="dev_console_semantics"), index)
        for index, case in enumerate(dev_cases, start=1)
    ]
    dpo_records = [dpo_pair(record, index) for index, record in enumerate(preferences, start=1)]
    holdout_cases = build_holdout_v2_cases()

    train_path = output_dir / "router_lora_train_v1.jsonl"
    dev_path = output_dir / "router_lora_dev_console_semantics_v1.jsonl"
    dpo_path = output_dir / "router_lora_dpo_pairs_v1.jsonl"
    holdout_path = output_dir / "router_holdout_1000_v2.jsonl"
    preflight_path = output_dir / "serving_parity_preflight.json"
    manifest_path = output_dir / "router_r08_boundary_manifest.json"

    write_jsonl(train_path, train_records)
    write_jsonl(dev_path, dev_records)
    write_jsonl(dpo_path, dpo_records)
    write_jsonl(holdout_path, [serializable_case(case) for case in holdout_cases])
    preflight = build_serving_parity_preflight(
        ollama_show_text,
        training_base=training_base,
        production_model=production_model,
        error=ollama_show_error,
    )
    write_json(preflight_path, preflight)

    route_counts = Counter(record["chosen_route"] for record in preferences)
    summary = {
        "adapter_name": ROUTER_ADAPTER_NAME,
        "focused_result_path": str(focused_result_path),
        "output_dir": str(output_dir),
        "training_base": training_base,
        "production_model": production_model,
        "false_r08_count": len(false_records),
        "balanced_positive_count": len(positive_records),
        "train_count": len(train_records),
        "dev_count": len(dev_records),
        "dpo_pair_count": len(dpo_records),
        "holdout_v2_count": len(holdout_cases),
        "chosen_route_counts": dict(sorted(route_counts.items())),
        "paths": {
            "train": str(train_path),
            "dev": str(dev_path),
            "dpo": str(dpo_path),
            "holdout_v2": str(holdout_path),
            "preflight": str(preflight_path),
            "manifest": str(manifest_path),
        },
        "serving_parity": preflight,
    }
    write_json(manifest_path, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build router R08 boundary SFT/DPO datasets.")
    parser.add_argument("--focused-result", type=Path, default=DEFAULT_FOCUSED_RESULT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--training-base", default=DEFAULT_TRAINING_BASE)
    parser.add_argument("--production-model", default=DEFAULT_PRODUCTION_MODEL)
    parser.add_argument("--skip-ollama-show", action="store_true")
    args = parser.parse_args(argv)

    show_text, show_error = ("", "ollama_show_skipped")
    if not args.skip_ollama_show:
        show_text, show_error = run_ollama_show(args.production_model)
    summary = build_router_r08_boundary_dataset(
        focused_result_path=args.focused_result,
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
