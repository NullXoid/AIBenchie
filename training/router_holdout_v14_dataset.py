from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from evals import router_gate
from training import router_holdout_v6_dataset as v6


DEFAULT_OUTPUT_DIR = Path("data/router_holdout_v14")
DEFAULT_OUTPUT_FILE = "router_holdout_1000_v14.jsonl"

V14_HARD_NEGATIVE_FORMS = [
    ("Notebook fragment about {topic}; no reply, route, command, edit, lookup, job, or memory save. V14 case {n}.", "chat.no_action"),
    ("Explain the safety boundary around {topic} without starting any tool path. V14 case {n}.", "answer.question"),
    ("Status-only note mentioning {topic}; keep it inert. V14 case {n}.", "chat.no_action"),
    ("Reason about {topic} at a high level before any work is requested. V14 case {n}.", "answer.question"),
    ("Scratchpad line: {topic}. This is not a request for action. V14 case {n}.", "chat.no_action"),
]

V14_ANSWER_FORMS = [
    "Describe how intent and method should be scored for {topic}, without executing anything. V14 case {n}.",
    "What should the router verify before acting on {topic}? V14 case {n}.",
    "Compare the safe conversation route and action route for {topic}. V14 case {n}.",
    "Why can {topic} be misread by an intent router? V14 case {n}.",
    "Give analysis only for {topic}; do not perform the action. V14 case {n}.",
]

V14_DIRECT_ACTIONS = [
    ("Run the hybrid router regression command now.", "console.run_command", "run_command"),
    ("Run pytest for the v14 holdout loader.", "console.run_command", "run_command"),
    ("Apply the router scoring update.", "console.edit_file", "file_edit"),
    ("Patch the method-aware safety metric test.", "console.edit_file", "file_edit"),
    ("Start a background agent job to audit serving parity metadata.", "agent.start_job", "job"),
    ("Launch an agent task for the route-code shadow readiness check.", "agent.start_job", "job"),
]

V14_AMBIGUOUS_REQUESTS = [
    ("Handle the router result when you are ready.", {}),
    ("Do that if the prior confirmation still applies.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Apply it if that was the approved change.", {"LAST_ASSISTANT_OFFERED_PATCH": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Can you safely continue the next thing?", {}),
    ("Move forward with whatever was just approved.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
]

V14_MEDIA_ACTIONS = [
    ("Describe the uploaded router matrix image.", "vision.describe_image", "media"),
    ("Summarize what is shown in this benchmark screenshot.", "vision.describe_image", "media"),
    ("Read every visible word in this router screenshot.", "vision.ocr_image", "media"),
    ("Extract text from the uploaded calibration capture.", "vision.ocr_image", "media"),
    ("Edit the attached screenshot to blur the exposed token.", "vision.edit_image", "media_edit"),
    ("Mask the private account number in this uploaded image.", "vision.edit_image", "media_edit"),
]

V14_CONSOLE_ACTIONS = [
    ("Open the local router safety dashboard.", "console.open_ui", "ui"),
    ("Open the saved benchmark comparison view.", "console.open_ui", "ui"),
    ("Run the clean v14 holdout evaluation.", "console.run_command", "run_command"),
    ("Run the router hybrid gate tests.", "console.run_command", "run_command"),
    ("Edit the v14 dataset registration code.", "console.edit_file", "file_edit"),
    ("Patch the hybrid method-aware scoring test.", "console.edit_file", "file_edit"),
]

V14_WEB_FILE_ACTIONS = [
    ("Look up current encoder calibration guidance online.", "web.lookup", "lookup"),
    ("Search the web for current local classifier serving notes.", "web.lookup", "lookup"),
    ("Read the local v13 diagnostic JSON result.", "file.search", "lookup"),
    ("Find the Stage 1B v14 artifact metadata in project files.", "file.search", "lookup"),
    ("Inspect saved router outputs for the most recent focused gate.", "file.search", "lookup"),
]

V14_MEMORY_CASES = [
    ("I like compact router updates for this session.", "chat.no_action", "none"),
    ("Short benchmark notes are useful here; do not remember that.", "chat.no_action", "none"),
    ("Explain why casual preference talk is not always a memory write.", "answer.question", "none"),
    ("What wording makes a preference an explicit memory-save request?", "answer.question", "none"),
    ("Remember that I prefer compact router updates.", "memory.save_preference", "memory"),
    ("Save my preference for short router benchmark summaries.", "memory.save_preference", "memory"),
]

V14_MESSY_PROMPTS = [
    ("pls run clean router eval now", "console.run_command", "run_command"),
    ("dont do it just explain route boundry pls", "answer.question", "none"),
    ("patch teh method aware scoring test", "console.edit_file", "file_edit"),
    ("read words from this router screencap", "vision.ocr_image", "media"),
    ("remember i prefer compact router updates", "memory.save_preference", "memory"),
]


def template_family(category: str, route: str, action_family: str, variant: str) -> str:
    return f"holdout_v14:{category}:{variant}:{route.replace('.', '_')}:{action_family}"


def case_row(
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
        template_family=template_family(category, route, action_family, variant),
    )
    case.update(v6.intent_method_metadata(route=route, action_family=action_family, text=text))
    return case


def build_holdout_v14_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[(idx * 13) % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V14_HARD_NEGATIVE_FORMS)
        form, route = V14_HARD_NEGATIVE_FORMS[form_index]
        cases.append(case_row(f"v14_hn_{idx + 1:04d}", "hard_negative", form.format(topic=topic, n=idx + 1), route, "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[(idx * 17) % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V14_ANSWER_FORMS)
        cases.append(case_row(f"v14_aq_{idx + 1:04d}", "answer_question", V14_ANSWER_FORMS[form_index].format(topic=topic, n=idx + 251), "answer.question", "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["direct_action"]):
        text, route, family = V14_DIRECT_ACTIONS[idx % len(V14_DIRECT_ACTIONS)]
        cases.append(case_row(f"v14_direct_{idx + 1:04d}", "direct_action", f"{text} V14 case {idx + 401}.", route, family, variant=f"action_{idx % len(V14_DIRECT_ACTIONS):02d}"))
    for idx in range(split["ambiguous"]):
        text, flags = V14_AMBIGUOUS_REQUESTS[idx % len(V14_AMBIGUOUS_REQUESTS)]
        cases.append(case_row(f"v14_amb_{idx + 1:04d}", "ambiguous", f"{text} V14 case {idx + 551}.", "ask_clarifying_question", "none", variant=f"amb_{idx % len(V14_AMBIGUOUS_REQUESTS):02d}", context_flags=flags))
    for idx in range(split["media_route"]):
        text, route, family = V14_MEDIA_ACTIONS[idx % len(V14_MEDIA_ACTIONS)]
        flags = {"HAS_IMAGE": True} if route.startswith("vision.") else {}
        required = ["HAS_IMAGE"] if route.startswith("vision.") else []
        cases.append(case_row(f"v14_media_{idx + 1:04d}", "media_route", f"{text} V14 case {idx + 651}.", route, family, variant=f"media_{idx % len(V14_MEDIA_ACTIONS):02d}", context_flags=flags, required_context_flags=required))
    for idx in range(split["console_route"]):
        text, route, family = V14_CONSOLE_ACTIONS[idx % len(V14_CONSOLE_ACTIONS)]
        cases.append(case_row(f"v14_console_{idx + 1:04d}", "console_route", f"{text} V14 case {idx + 751}.", route, family, variant=f"console_{idx % len(V14_CONSOLE_ACTIONS):02d}"))
    for idx in range(split["web_file_data"]):
        text, route, family = V14_WEB_FILE_ACTIONS[idx % len(V14_WEB_FILE_ACTIONS)]
        cases.append(case_row(f"v14_webfile_{idx + 1:04d}", "web_file_data", f"{text} V14 case {idx + 826}.", route, family, variant=f"webfile_{idx % len(V14_WEB_FILE_ACTIONS):02d}"))
    for idx in range(split["memory_preference"]):
        text, route, family = V14_MEMORY_CASES[idx % len(V14_MEMORY_CASES)]
        cases.append(case_row(f"v14_mem_{idx + 1:04d}", "memory_preference", f"{text} V14 case {idx + 901}.", route, family, variant=f"memory_{idx % len(V14_MEMORY_CASES):02d}"))
    for idx in range(split["messy_voice_typo"]):
        text, route, family = V14_MESSY_PROMPTS[idx % len(V14_MESSY_PROMPTS)]
        cases.append(case_row(f"v14_messy_{idx + 1:04d}", "messy_voice_typo", f"{text} v14 case {idx + 951}", route, family, variant=f"messy_{idx % len(V14_MESSY_PROMPTS):02d}"))
    texts = [case["text"] for case in cases]
    ids = [case["id"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)) or len(ids) != len(set(ids)):
        raise ValueError("router_holdout_1000_v14 generation failed uniqueness or count checks")
    if any(not str(case.get("template_family", "")).startswith("holdout_v14:") for case in cases):
        raise ValueError("router_holdout_1000_v14 requires explicit holdout_v14 template families")
    return cases


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def build_holdout_v14_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR, output_file: str = DEFAULT_OUTPUT_FILE) -> dict[str, Any]:
    cases = [v6.serializable_case(case) for case in build_holdout_v14_cases()]
    output_path = output_dir / output_file
    manifest_path = output_dir / "router_holdout_1000_v14_manifest.json"
    manifest = {
        "dataset": "router_holdout_1000_v14",
        "description": "Fresh router holdout with intent/method metadata and alternate v14 prompts; v14 is clean until inspected or tuned from.",
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
    parser = argparse.ArgumentParser(description="Build the clean router_holdout_1000_v14 JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args(argv)
    print(json.dumps(build_holdout_v14_dataset(args.output_dir, args.output_file), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
