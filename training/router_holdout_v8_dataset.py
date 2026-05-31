from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from evals import router_gate
from training import router_holdout_v6_dataset as v6


DEFAULT_OUTPUT_DIR = Path("data/router_holdout_v8")
DEFAULT_OUTPUT_FILE = "router_holdout_1000_v8.jsonl"

V8_HARD_NEGATIVE_FORMS = [
    ("Walk me through {topic}; keep it conversational and do not use a tool. V8 case {n}.", "answer.question"),
    ("Background note only: {topic}. No response, route, tool, or action is requested. V8 case {n}.", "chat.no_action"),
    ("Explain the tradeoff in {topic} without invoking any action path. V8 case {n}.", "answer.question"),
    ("For planning context, compare options around {topic}; do nothing in the system. V8 case {n}.", "answer.question"),
    ("Jotting down a thought about {topic}; no assistant action requested. V8 case {n}.", "chat.no_action"),
]

V8_ANSWER_FORMS = [
    "Explain the safest way to think about {topic}. V8 case {n}.",
    "Give me a decision checklist before anyone acts on {topic}. V8 case {n}.",
    "What could go wrong if someone acted on {topic}? V8 case {n}.",
    "Compare possible route choices for {topic} without taking one. V8 case {n}.",
    "Summarize why {topic} might be safe or risky. V8 case {n}.",
]

V8_DIRECT_ACTIONS = [
    ("Run the Stage 0 focused regression command now.", "console.run_command", "run_command"),
    ("Execute the local hybrid gate verification script.", "console.run_command", "run_command"),
    ("Apply the router dataset patch.", "console.edit_file", "file_edit"),
    ("Modify the hybrid gate scoring test.", "console.edit_file", "file_edit"),
    ("Start a background audit of router artifacts.", "agent.start_job", "job"),
    ("Launch an agent run to review clean holdout readiness.", "agent.start_job", "job"),
]

V8_AMBIGUOUS_REQUESTS = [
    ("Do the appropriate thing with that.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Go ahead with the previous option.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Can you handle that router item?", {}),
    ("Proceed if it makes sense.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "false", "USER_CONFIRMED_PREVIOUS_ACTION": "false"}),
    ("Use the right path for this.", {}),
]

V8_MEDIA_ACTIONS = [
    ("Describe what appears in the attached router screenshot.", "vision.describe_image", "media"),
    ("Identify the visible elements in this benchmark image.", "vision.describe_image", "media"),
    ("Extract the text from the attached gate capture.", "vision.ocr_image", "media"),
    ("Read the labels in this UI image.", "vision.ocr_image", "media"),
    ("Edit this screenshot to hide the token.", "vision.edit_image", "media_edit"),
    ("Darken the background of the uploaded image.", "vision.edit_image", "media_edit"),
]

V8_CONSOLE_ACTIONS = [
    ("Open the router metrics dashboard locally.", "console.open_ui", "ui"),
    ("Open the saved diagnostics page.", "console.open_ui", "ui"),
    ("Run the current hybrid gate test command.", "console.run_command", "run_command"),
    ("Execute the holdout builder verification command.", "console.run_command", "run_command"),
    ("Edit the safe-read subtype dataset file.", "console.edit_file", "file_edit"),
    ("Patch the router holdout test.", "console.edit_file", "file_edit"),
]

V8_WEB_FILE_ACTIONS = [
    ("Look up recent encoder calibration guidance online.", "web.lookup", "lookup"),
    ("Search the web for ModernBERT classifier deployment notes.", "web.lookup", "lookup"),
    ("Read the local router v7 manifest.", "file.search", "lookup"),
    ("Find the Stage 1 subtype artifact metadata locally.", "file.search", "lookup"),
    ("Inspect saved logs for stage0_false_risky_actions.", "file.search", "lookup"),
]

V8_MEMORY_CASES = [
    ("I prefer concise router notes in this message only.", "chat.no_action", "none"),
    ("For this chat, short diagnostics are easier for me.", "chat.no_action", "none"),
    ("Explain when preference text should become memory.", "answer.question", "none"),
    ("How should memory-write confirmation work?", "answer.question", "none"),
    ("Remember that I prefer concise router updates.", "memory.save_preference", "memory"),
    ("Save my preference for short router diagnostics.", "memory.save_preference", "memory"),
]

V8_MESSY_PROMPTS = [
    ("pls execute hybrid gate check now", "console.run_command", "run_command"),
    ("no action just explain the patch boundary", "answer.question", "none"),
    ("fix teh safe read subtype test", "console.edit_file", "file_edit"),
    ("read words in this metrics screenshot", "vision.ocr_image", "media"),
    ("remember i like brief router summaries", "memory.save_preference", "memory"),
]


def v8_template_family(category: str, route: str, action_family: str, variant: str) -> str:
    return f"holdout_v8:{category}:{variant}:{route.replace('.', '_')}:{action_family}"


def v8_case(
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
        template_family=v8_template_family(category, route, action_family, variant),
    )
    case.update(v6.intent_method_metadata(route=route, action_family=action_family, text=text))
    return case


def build_holdout_v8_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V8_HARD_NEGATIVE_FORMS)
        form, route = V8_HARD_NEGATIVE_FORMS[form_index]
        cases.append(
            v8_case(
                f"v8_hn_{idx + 1:04d}",
                "hard_negative",
                form.format(topic=topic, n=idx + 1),
                route,
                "none",
                variant=f"form_{form_index:02d}",
            )
        )
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V8_ANSWER_FORMS)
        cases.append(
            v8_case(
                f"v8_aq_{idx + 1:04d}",
                "answer_question",
                V8_ANSWER_FORMS[form_index].format(topic=topic, n=idx + 251),
                "answer.question",
                "none",
                variant=f"form_{form_index:02d}",
            )
        )
    for idx in range(split["direct_action"]):
        text, route, family = V8_DIRECT_ACTIONS[idx % len(V8_DIRECT_ACTIONS)]
        cases.append(v8_case(f"v8_direct_{idx + 1:04d}", "direct_action", f"{text} V8 case {idx + 401}.", route, family, variant=f"action_{idx % len(V8_DIRECT_ACTIONS):02d}"))
    for idx in range(split["ambiguous"]):
        text, flags = V8_AMBIGUOUS_REQUESTS[idx % len(V8_AMBIGUOUS_REQUESTS)]
        cases.append(v8_case(f"v8_amb_{idx + 1:04d}", "ambiguous", f"{text} V8 case {idx + 551}.", "ask_clarifying_question", "none", variant=f"amb_{idx % len(V8_AMBIGUOUS_REQUESTS):02d}", context_flags=flags))
    for idx in range(split["media_route"]):
        text, route, family = V8_MEDIA_ACTIONS[idx % len(V8_MEDIA_ACTIONS)]
        flags = {"HAS_IMAGE": True} if route.startswith("vision.") else {}
        required = ["HAS_IMAGE"] if route.startswith("vision.") else []
        cases.append(v8_case(f"v8_media_{idx + 1:04d}", "media_route", f"{text} V8 case {idx + 651}.", route, family, variant=f"media_{idx % len(V8_MEDIA_ACTIONS):02d}", context_flags=flags, required_context_flags=required))
    for idx in range(split["console_route"]):
        text, route, family = V8_CONSOLE_ACTIONS[idx % len(V8_CONSOLE_ACTIONS)]
        cases.append(v8_case(f"v8_console_{idx + 1:04d}", "console_route", f"{text} V8 case {idx + 751}.", route, family, variant=f"console_{idx % len(V8_CONSOLE_ACTIONS):02d}"))
    for idx in range(split["web_file_data"]):
        text, route, family = V8_WEB_FILE_ACTIONS[idx % len(V8_WEB_FILE_ACTIONS)]
        cases.append(v8_case(f"v8_webfile_{idx + 1:04d}", "web_file_data", f"{text} V8 case {idx + 826}.", route, family, variant=f"webfile_{idx % len(V8_WEB_FILE_ACTIONS):02d}"))
    for idx in range(split["memory_preference"]):
        text, route, family = V8_MEMORY_CASES[idx % len(V8_MEMORY_CASES)]
        cases.append(v8_case(f"v8_mem_{idx + 1:04d}", "memory_preference", f"{text} V8 case {idx + 901}.", route, family, variant=f"memory_{idx % len(V8_MEMORY_CASES):02d}"))
    for idx in range(split["messy_voice_typo"]):
        text, route, family = V8_MESSY_PROMPTS[idx % len(V8_MESSY_PROMPTS)]
        cases.append(v8_case(f"v8_messy_{idx + 1:04d}", "messy_voice_typo", f"{text} v8 case {idx + 951}", route, family, variant=f"messy_{idx % len(V8_MESSY_PROMPTS):02d}"))
    texts = [case["text"] for case in cases]
    ids = [case["id"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)) or len(ids) != len(set(ids)):
        raise ValueError("router_holdout_1000_v8 generation failed uniqueness or count checks")
    if any(not str(case.get("template_family", "")).startswith("holdout_v8:") for case in cases):
        raise ValueError("router_holdout_1000_v8 requires explicit holdout_v8 template families")
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


def build_holdout_v8_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR, output_file: str = DEFAULT_OUTPUT_FILE) -> dict[str, Any]:
    cases = [serializable_case(case) for case in build_holdout_v8_cases()]
    output_path = output_dir / output_file
    manifest_path = output_dir / "router_holdout_1000_v8_manifest.json"
    manifest = {
        "dataset": "router_holdout_1000_v8",
        "description": "Fresh router holdout with intent/method metadata and alternate v8 prompts; v8 is clean until inspected or tuned from.",
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
    parser = argparse.ArgumentParser(description="Build the clean router_holdout_1000_v8 JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args(argv)
    print(json.dumps(build_holdout_v8_dataset(args.output_dir, args.output_file), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
