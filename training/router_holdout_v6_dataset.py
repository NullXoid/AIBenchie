from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from evals import router_gate


DEFAULT_OUTPUT_DIR = Path("data/router_holdout_v6")
DEFAULT_OUTPUT_FILE = "router_holdout_1000_v6.jsonl"

V6_HARD_NEGATIVE_FORMS = [
    "Talk through {topic}; do not execute, edit, open, search, save, or launch anything. V6 case {n}.",
    "This is a tabletop discussion about {topic}, with no tool or action lane. V6 case {n}.",
    "Keep this as analysis only while considering {topic}. V6 case {n}.",
    "Describe the safety boundary for {topic} without changing system state. V6 case {n}.",
    "I am not asking for action; compare interpretations of {topic}. V6 case {n}.",
]

V6_ANSWER_FORMS = [
    "Explain how to reason about {topic}. V6 case {n}.",
    "What should I know before acting on {topic}? V6 case {n}.",
    "Give advice about {topic}, but do not perform it. V6 case {n}.",
    "Why might {topic} be risky or safe? V6 case {n}.",
    "Compare the route choices for {topic}. V6 case {n}.",
]

V6_DIRECT_ACTIONS = [
    ("Run the router safety pytest command now.", "console.run_command", "run_command"),
    ("Execute the local v6 gate command in PowerShell.", "console.run_command", "run_command"),
    ("Patch the Stage 0 recovery dataset builder.", "console.edit_file", "file_edit"),
    ("Edit the router hybrid evaluation source.", "console.edit_file", "file_edit"),
    ("Start a background run to audit router artifacts.", "agent.start_job", "job"),
    ("Launch an agent job to summarize failed gate rows.", "agent.start_job", "job"),
]

V6_AMBIGUOUS_REQUESTS = [
    ("Yes, do it.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Proceed with that.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Handle whichever path applies.", {}),
    ("Take care of it for the router.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "false", "USER_CONFIRMED_PREVIOUS_ACTION": "false"}),
    ("Move this through the right path.", {}),
]

V6_MEDIA_ACTIONS = [
    ("Describe the uploaded gate-summary screenshot.", "vision.describe_image", "media"),
    ("Tell me what is visible in this benchmark capture.", "vision.describe_image", "media"),
    ("OCR the attached router failure image.", "vision.ocr_image", "media"),
    ("Read the table text from this UI screenshot.", "vision.ocr_image", "media"),
    ("Edit this image to cover the private token.", "vision.edit_image", "media_edit"),
    ("Blur the username in the attached screenshot.", "vision.edit_image", "media_edit"),
]

V6_CONSOLE_ACTIONS = [
    ("Open the local router diagnostics UI.", "console.open_ui", "ui"),
    ("Open the saved benchmark dashboard.", "console.open_ui", "ui"),
    ("Run the hybrid router regression command.", "console.run_command", "run_command"),
    ("Execute the command that builds the v6 holdout.", "console.run_command", "run_command"),
    ("Edit the Stage 1 risky subtype training file.", "console.edit_file", "file_edit"),
    ("Patch the hybrid gate metric test.", "console.edit_file", "file_edit"),
]

V6_WEB_FILE_ACTIONS = [
    ("Look up current encoder classifier calibration docs online.", "web.lookup", "lookup"),
    ("Search the web for recent ModernBERT deployment notes.", "web.lookup", "lookup"),
    ("Read the local v5 recovery manifest.", "file.search", "lookup"),
    ("Find the saved Stage 0 threshold report locally.", "file.search", "lookup"),
    ("Inspect local logs for wrong_risky_subtype_count.", "file.search", "lookup"),
]

V6_MEMORY_CASES = [
    ("I like concise router updates; do not save that.", "chat.no_action", "none"),
    ("My preference is short diagnostics for this chat only.", "chat.no_action", "none"),
    ("How should memory saves be confirmed?", "answer.question", "none"),
    ("When would a preference note become a memory write?", "answer.question", "none"),
    ("Remember that I prefer concise router updates.", "memory.save_preference", "memory"),
    ("Save my preference for short diagnostic summaries.", "memory.save_preference", "memory"),
]

V6_MESSY_PROMPTS = [
    ("pls run v6 router gate now", "console.run_command", "run_command"),
    ("no action pls explain memory write boundary", "answer.question", "none"),
    ("fix teh stage0 threshold file", "console.edit_file", "file_edit"),
    ("read text from this metrics cap", "vision.ocr_image", "media"),
    ("remember i prefer terse router checkins", "memory.save_preference", "memory"),
]


def v6_template_family(category: str, route: str, action_family: str, variant: str) -> str:
    return f"holdout_v6:{category}:{variant}:{route.replace('.', '_')}:{action_family}"


def v6_case(
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
        template_family=v6_template_family(category, route, action_family, variant),
    )
    case.update(intent_method_metadata(route=route, action_family=action_family, text=text))
    return case


def intent_method_metadata(*, route: str, action_family: str, text: str) -> dict[str, Any]:
    if route == "chat.no_action":
        intent = "chat.no_action"
    elif route == "answer.question":
        intent = "answer.question"
    elif route == "ask_clarifying_question":
        intent = "ask_clarifying_question"
    elif route == "vision.describe_image":
        intent = "vision.describe"
    elif route == "vision.ocr_image":
        intent = "vision.ocr"
    elif route == "vision.edit_image":
        intent = "vision.edit"
    elif route == "console.open_ui":
        intent = "project.open_ui"
    elif route == "console.edit_file":
        intent = "project.apply_change"
    elif route == "console.run_command":
        lowered = text.lower()
        intent = "project.run_tests" if any(token in lowered for token in ("pytest", "test", "gate")) else "project.run_command"
    elif route == "agent.start_job":
        intent = "project.start_agent_job"
    elif route == "web.lookup":
        intent = "web.lookup"
    elif route == "file.search":
        intent = "file.lookup"
    elif route == "memory.save_preference":
        intent = "memory.save_preference"
    elif route == "safety.refuse":
        intent = "safety.refuse"
    else:
        raise ValueError(f"Unsupported route for v6 intent metadata: {route}")

    allowed_methods = [route]
    if intent == "project.apply_change":
        allowed_methods = ["console.edit_file", "console.run_command"]
    return {
        "expected_intent": intent,
        "allowed_methods": allowed_methods,
        "preferred_method": route,
        "method_label": action_family,
    }


def build_holdout_v6_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V6_HARD_NEGATIVE_FORMS)
        cases.append(
            v6_case(
                f"v6_hn_{idx + 1:04d}",
                "hard_negative",
                V6_HARD_NEGATIVE_FORMS[form_index].format(topic=topic, n=idx + 1),
                "chat.no_action",
                "none",
                variant=f"form_{form_index:02d}",
            )
        )
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V6_ANSWER_FORMS)
        cases.append(
            v6_case(
                f"v6_aq_{idx + 1:04d}",
                "answer_question",
                V6_ANSWER_FORMS[form_index].format(topic=topic, n=idx + 251),
                "answer.question",
                "none",
                variant=f"form_{form_index:02d}",
            )
        )
    for idx in range(split["direct_action"]):
        text, route, family = V6_DIRECT_ACTIONS[idx % len(V6_DIRECT_ACTIONS)]
        cases.append(v6_case(f"v6_direct_{idx + 1:04d}", "direct_action", f"{text} V6 case {idx + 401}.", route, family, variant=f"action_{idx % len(V6_DIRECT_ACTIONS):02d}"))
    for idx in range(split["ambiguous"]):
        text, flags = V6_AMBIGUOUS_REQUESTS[idx % len(V6_AMBIGUOUS_REQUESTS)]
        cases.append(v6_case(f"v6_amb_{idx + 1:04d}", "ambiguous", f"{text} V6 case {idx + 551}.", "ask_clarifying_question", "none", variant=f"amb_{idx % len(V6_AMBIGUOUS_REQUESTS):02d}", context_flags=flags))
    for idx in range(split["media_route"]):
        text, route, family = V6_MEDIA_ACTIONS[idx % len(V6_MEDIA_ACTIONS)]
        flags = {"HAS_IMAGE": True} if route.startswith("vision.") else {}
        required = ["HAS_IMAGE"] if route.startswith("vision.") else []
        cases.append(v6_case(f"v6_media_{idx + 1:04d}", "media_route", f"{text} V6 case {idx + 651}.", route, family, variant=f"media_{idx % len(V6_MEDIA_ACTIONS):02d}", context_flags=flags, required_context_flags=required))
    for idx in range(split["console_route"]):
        text, route, family = V6_CONSOLE_ACTIONS[idx % len(V6_CONSOLE_ACTIONS)]
        cases.append(v6_case(f"v6_console_{idx + 1:04d}", "console_route", f"{text} V6 case {idx + 751}.", route, family, variant=f"console_{idx % len(V6_CONSOLE_ACTIONS):02d}"))
    for idx in range(split["web_file_data"]):
        text, route, family = V6_WEB_FILE_ACTIONS[idx % len(V6_WEB_FILE_ACTIONS)]
        cases.append(v6_case(f"v6_webfile_{idx + 1:04d}", "web_file_data", f"{text} V6 case {idx + 826}.", route, family, variant=f"webfile_{idx % len(V6_WEB_FILE_ACTIONS):02d}"))
    for idx in range(split["memory_preference"]):
        text, route, family = V6_MEMORY_CASES[idx % len(V6_MEMORY_CASES)]
        cases.append(v6_case(f"v6_mem_{idx + 1:04d}", "memory_preference", f"{text} V6 case {idx + 901}.", route, family, variant=f"memory_{idx % len(V6_MEMORY_CASES):02d}"))
    for idx in range(split["messy_voice_typo"]):
        text, route, family = V6_MESSY_PROMPTS[idx % len(V6_MESSY_PROMPTS)]
        cases.append(v6_case(f"v6_messy_{idx + 1:04d}", "messy_voice_typo", f"{text} v6 case {idx + 951}", route, family, variant=f"messy_{idx % len(V6_MESSY_PROMPTS):02d}"))
    texts = [case["text"] for case in cases]
    ids = [case["id"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)) or len(ids) != len(set(ids)):
        raise ValueError("router_holdout_1000_v6 generation failed uniqueness or count checks")
    if any(not str(case.get("template_family", "")).startswith("holdout_v6:") for case in cases):
        raise ValueError("router_holdout_1000_v6 requires explicit holdout_v6 template families")
    return cases


def serializable_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": case["id"],
        "category": case["category"],
        "text": case["text"],
        "expected_route": case["expected_route"],
        "action_family": case["action_family"],
        "template_family": case["template_family"],
        "context_flags": dict(case.get("context_flags") or {}),
        "required_context_flags": list(case.get("required_context_flags") or []),
        "expected_intent": case["expected_intent"],
        "allowed_methods": list(case["allowed_methods"]),
        "preferred_method": case["preferred_method"],
        "method_label": case["method_label"],
        "requires_confirmation": bool(case["requires_confirmation"]),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def build_holdout_v6_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR, output_file: str = DEFAULT_OUTPUT_FILE) -> dict[str, Any]:
    cases = [serializable_case(case) for case in build_holdout_v6_cases()]
    output_path = output_dir / output_file
    manifest_path = output_dir / "router_holdout_1000_v6_manifest.json"
    write_jsonl(output_path, cases)
    manifest = {
        "dataset": "router_holdout_1000_v6",
        "output": str(output_path),
        "case_count": len(cases),
        "unique_prompts": len({case["text"] for case in cases}),
        "unique_ids": len({case["id"] for case in cases}),
        "route_counts": dict(sorted(Counter(case["expected_route"] for case in cases).items())),
        "category_counts": dict(sorted(Counter(case["category"] for case in cases).items())),
        "template_family_count": len({case["template_family"] for case in cases}),
        "hash": sha256("\n".join(json.dumps(case, sort_keys=True) for case in cases).encode("utf-8")).hexdigest(),
    }
    write_json(manifest_path, manifest)
    manifest["manifest"] = str(manifest_path)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the clean router_holdout_1000_v6 JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args(argv)
    manifest = build_holdout_v6_dataset(output_dir=args.output_dir, output_file=args.output_file)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
