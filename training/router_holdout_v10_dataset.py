from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from evals import router_gate
from training import router_holdout_v6_dataset as v6


DEFAULT_OUTPUT_DIR = Path("data/router_holdout_v10")
DEFAULT_OUTPUT_FILE = "router_holdout_1000_v10.jsonl"

V10_HARD_NEGATIVE_FORMS = [
    ("Notebook note only: {topic}. Do not respond with an action. V10 case {n}.", "chat.no_action"),
    ("Describe the tradeoffs around {topic}; leave every tool idle. V10 case {n}.", "answer.question"),
    ("I am comparing options for {topic}, not authorizing work. V10 case {n}.", "answer.question"),
    ("Scratchpad entry about {topic}; no save, run, edit, open, or job. V10 case {n}.", "chat.no_action"),
    ("Walk through what {topic} would imply before anything happens. V10 case {n}.", "answer.question"),
]

V10_ANSWER_FORMS = [
    "Explain how to evaluate {topic} without taking action. V10 case {n}.",
    "What would be the safest review process for {topic}? V10 case {n}.",
    "Compare the possible routes for {topic}, but keep it theoretical. V10 case {n}.",
    "Why might {topic} need clarification first? V10 case {n}.",
    "Give advisory guidance about {topic}; do not touch the workspace. V10 case {n}.",
]

V10_DIRECT_ACTIONS = [
    ("Run the hybrid router validation script now.", "console.run_command", "run_command"),
    ("Run pytest for the router gate tests.", "console.run_command", "run_command"),
    ("Apply the change to the Stage 0 threshold code.", "console.edit_file", "file_edit"),
    ("Patch the safe-stage classifier dataset builder.", "console.edit_file", "file_edit"),
    ("Start an agent job to audit router serving parity.", "agent.start_job", "job"),
    ("Launch a background agent task for the holdout review.", "agent.start_job", "job"),
]

V10_AMBIGUOUS_REQUESTS = [
    ("Take care of that router thing.", {}),
    ("Proceed with it if you know what I mean.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Go ahead with the change we discussed.", {"LAST_ASSISTANT_OFFERED_PATCH": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Can you handle the next step?", {}),
    ("Yes, do that now.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
]

V10_MEDIA_ACTIONS = [
    ("Describe what is visible in the attached router trace image.", "vision.describe_image", "media"),
    ("Tell me what this uploaded UI screenshot shows.", "vision.describe_image", "media"),
    ("Extract the text from the attached benchmark screenshot.", "vision.ocr_image", "media"),
    ("Read the labels in this uploaded diagnostics capture.", "vision.ocr_image", "media"),
    ("Edit this uploaded screenshot to cover the API key.", "vision.edit_image", "media_edit"),
    ("Mask the private token visible in the attached image.", "vision.edit_image", "media_edit"),
]

V10_CONSOLE_ACTIONS = [
    ("Open the local router comparison page.", "console.open_ui", "ui"),
    ("Open the saved AIBenchie results dashboard.", "console.open_ui", "ui"),
    ("Run the router hybrid gate command.", "console.run_command", "run_command"),
    ("Run the Stage 1 subtype regression tests.", "console.run_command", "run_command"),
    ("Edit the holdout v10 generator.", "console.edit_file", "file_edit"),
    ("Patch the hybrid gate image override logic.", "console.edit_file", "file_edit"),
]

V10_WEB_FILE_ACTIONS = [
    ("Look up current encoder calibration guidance online.", "web.lookup", "lookup"),
    ("Search the web for recent ModernBERT serving notes.", "web.lookup", "lookup"),
    ("Read the local v9 holdout manifest file.", "file.search", "lookup"),
    ("Find the Stage 1C v10 artifact metadata in the repo.", "file.search", "lookup"),
    ("Inspect the saved hybrid diagnostic JSON locally.", "file.search", "lookup"),
]

V10_MEMORY_CASES = [
    ("I like concise router notes during this chat only.", "chat.no_action", "none"),
    ("Compact status messages help me follow this run; do not remember that.", "chat.no_action", "none"),
    ("Explain when a preference belongs in memory.", "answer.question", "none"),
    ("What makes a memory-save request explicit enough?", "answer.question", "none"),
    ("Remember that I prefer concise router notes.", "memory.save_preference", "memory"),
    ("Save my preference for compact router status updates.", "memory.save_preference", "memory"),
]

V10_MESSY_PROMPTS = [
    ("pls run router focused checks now", "console.run_command", "run_command"),
    ("dont do it just explain patch safety", "answer.question", "none"),
    ("fix teh stage one subtype file", "console.edit_file", "file_edit"),
    ("read txt from this holdout screenshot", "vision.ocr_image", "media"),
    ("remember i like short router updates", "memory.save_preference", "memory"),
]


def v10_template_family(category: str, route: str, action_family: str, variant: str) -> str:
    return f"holdout_v10:{category}:{variant}:{route.replace('.', '_')}:{action_family}"


def v10_case(
    case_id: str,
    category: str,
    text: str,
    route: str,
    action_family: str,
    *,
    variant: str,
    context_flags: dict[str, Any] | None = None,
    required_context_flags: list[str] | None = None,
) -> dict[str, Any]:
    case = router_gate.case_row(
        case_id,
        category,
        text,
        route,
        action_family,
        context_flags=context_flags,
        required_context_flags=required_context_flags,
        template_family=v10_template_family(category, route, action_family, variant),
    )
    case.update(v6.intent_method_metadata(route=route, action_family=action_family, text=text))
    return case


def build_holdout_v10_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V10_HARD_NEGATIVE_FORMS)
        form, route = V10_HARD_NEGATIVE_FORMS[form_index]
        cases.append(v10_case(f"v10_hn_{idx + 1:04d}", "hard_negative", form.format(topic=topic, n=idx + 1), route, "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V10_ANSWER_FORMS)
        cases.append(v10_case(f"v10_aq_{idx + 1:04d}", "answer_question", V10_ANSWER_FORMS[form_index].format(topic=topic, n=idx + 251), "answer.question", "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["direct_action"]):
        text, route, family = V10_DIRECT_ACTIONS[idx % len(V10_DIRECT_ACTIONS)]
        cases.append(v10_case(f"v10_direct_{idx + 1:04d}", "direct_action", f"{text} V10 case {idx + 401}.", route, family, variant=f"action_{idx % len(V10_DIRECT_ACTIONS):02d}"))
    for idx in range(split["ambiguous"]):
        text, flags = V10_AMBIGUOUS_REQUESTS[idx % len(V10_AMBIGUOUS_REQUESTS)]
        cases.append(v10_case(f"v10_amb_{idx + 1:04d}", "ambiguous", f"{text} V10 case {idx + 551}.", "ask_clarifying_question", "none", variant=f"amb_{idx % len(V10_AMBIGUOUS_REQUESTS):02d}", context_flags=flags))
    for idx in range(split["media_route"]):
        text, route, family = V10_MEDIA_ACTIONS[idx % len(V10_MEDIA_ACTIONS)]
        flags = {"HAS_IMAGE": True} if route.startswith("vision.") else {}
        required = ["HAS_IMAGE"] if route.startswith("vision.") else []
        cases.append(v10_case(f"v10_media_{idx + 1:04d}", "media_route", f"{text} V10 case {idx + 651}.", route, family, variant=f"media_{idx % len(V10_MEDIA_ACTIONS):02d}", context_flags=flags, required_context_flags=required))
    for idx in range(split["console_route"]):
        text, route, family = V10_CONSOLE_ACTIONS[idx % len(V10_CONSOLE_ACTIONS)]
        cases.append(v10_case(f"v10_console_{idx + 1:04d}", "console_route", f"{text} V10 case {idx + 751}.", route, family, variant=f"console_{idx % len(V10_CONSOLE_ACTIONS):02d}"))
    for idx in range(split["web_file_data"]):
        text, route, family = V10_WEB_FILE_ACTIONS[idx % len(V10_WEB_FILE_ACTIONS)]
        cases.append(v10_case(f"v10_webfile_{idx + 1:04d}", "web_file_data", f"{text} V10 case {idx + 826}.", route, family, variant=f"webfile_{idx % len(V10_WEB_FILE_ACTIONS):02d}"))
    for idx in range(split["memory_preference"]):
        text, route, family = V10_MEMORY_CASES[idx % len(V10_MEMORY_CASES)]
        cases.append(v10_case(f"v10_mem_{idx + 1:04d}", "memory_preference", f"{text} V10 case {idx + 901}.", route, family, variant=f"memory_{idx % len(V10_MEMORY_CASES):02d}"))
    for idx in range(split["messy_voice_typo"]):
        text, route, family = V10_MESSY_PROMPTS[idx % len(V10_MESSY_PROMPTS)]
        cases.append(v10_case(f"v10_messy_{idx + 1:04d}", "messy_voice_typo", f"{text} v10 case {idx + 951}", route, family, variant=f"messy_{idx % len(V10_MESSY_PROMPTS):02d}"))
    texts = [case["text"] for case in cases]
    ids = [case["id"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)) or len(ids) != len(set(ids)):
        raise ValueError("router_holdout_1000_v10 generation failed uniqueness or count checks")
    if any(not str(case.get("template_family", "")).startswith("holdout_v10:") for case in cases):
        raise ValueError("router_holdout_1000_v10 requires explicit holdout_v10 template families")
    return cases


def serializable_case(case: dict[str, Any]) -> dict[str, Any]:
    return v6.serializable_case(case)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def build_holdout_v10_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR, output_file: str = DEFAULT_OUTPUT_FILE) -> dict[str, Any]:
    cases = [serializable_case(case) for case in build_holdout_v10_cases()]
    output_path = output_dir / output_file
    manifest_path = output_dir / "router_holdout_1000_v10_manifest.json"
    manifest = {
        "dataset": "router_holdout_1000_v10",
        "description": "Fresh router holdout with intent/method metadata and alternate v10 prompts; v10 is clean until inspected or tuned from.",
        "case_count": len(cases),
        "unique_prompts": len({case["text"] for case in cases}),
        "category_counts": dict(sorted(Counter(case["category"] for case in cases).items())),
        "route_counts": dict(sorted(Counter(case["expected_route"] for case in cases).items())),
        "intent_counts": dict(sorted(Counter(case["expected_intent"] for case in cases).items())),
        "template_family_count": len({case["template_family"] for case in cases}),
        "hash": sha256("\n".join(json.dumps(case, sort_keys=True) for case in cases).encode("utf-8")).hexdigest(),
        "output": str(output_path),
        "manifest": str(manifest_path),
    }
    write_jsonl(output_path, cases)
    write_json(manifest_path, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the clean router_holdout_1000_v10 JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args(argv)
    print(json.dumps(build_holdout_v10_dataset(args.output_dir, args.output_file), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
