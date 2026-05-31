from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from evals import router_gate
from training import router_holdout_v6_dataset as v6


DEFAULT_OUTPUT_DIR = Path("data/router_holdout_v9")
DEFAULT_OUTPUT_FILE = "router_holdout_1000_v9.jsonl"

V9_HARD_NEGATIVE_FORMS = [
    ("Talk me through {topic} at a high level; keep tools and actions out of it. V9 case {n}.", "answer.question"),
    ("Personal scratch note: {topic}. No answer needed and no system action. V9 case {n}.", "chat.no_action"),
    ("Help me understand {topic} before anybody does anything. V9 case {n}.", "answer.question"),
    ("Compare interpretations of {topic} while leaving the workspace untouched. V9 case {n}.", "answer.question"),
    ("Status note for myself about {topic}; do not analyze, save, open, run, or edit. V9 case {n}.", "chat.no_action"),
]

V9_ANSWER_FORMS = [
    "Explain the routing considerations around {topic}. V9 case {n}.",
    "What should I check before deciding about {topic}? V9 case {n}.",
    "Give guidance for {topic}, but keep it advisory. V9 case {n}.",
    "Why could {topic} be a risky boundary? V9 case {n}.",
    "Contrast the safe and action routes for {topic}. V9 case {n}.",
]

V9_DIRECT_ACTIONS = [
    ("Run the router holdout verification command now.", "console.run_command", "run_command"),
    ("Run the local hybrid gate smoke command.", "console.run_command", "run_command"),
    ("Apply the safe-stage classifier patch.", "console.edit_file", "file_edit"),
    ("Edit the router holdout dataset builder.", "console.edit_file", "file_edit"),
    ("Start a background job to audit the router evidence.", "agent.start_job", "job"),
    ("Launch an agent task to review holdout readiness.", "agent.start_job", "job"),
]

V9_AMBIGUOUS_REQUESTS = [
    ("Please take the next router step.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Yes, proceed with that route.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Can you sort out that routing item?", {}),
    ("Move it forward if it is safe.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "false", "USER_CONFIRMED_PREVIOUS_ACTION": "false"}),
    ("Handle the thing we were discussing.", {}),
]

V9_MEDIA_ACTIONS = [
    ("Describe the contents of this attached benchmark screenshot.", "vision.describe_image", "media"),
    ("Summarize what the uploaded router image shows.", "vision.describe_image", "media"),
    ("OCR the visible text in this gate screenshot.", "vision.ocr_image", "media"),
    ("Transcribe the words from the attached UI capture.", "vision.ocr_image", "media"),
    ("Edit the attached image to remove the secret token.", "vision.edit_image", "media_edit"),
    ("Blur the sensitive area in this uploaded screenshot.", "vision.edit_image", "media_edit"),
]

V9_CONSOLE_ACTIONS = [
    ("Open the local hybrid router dashboard.", "console.open_ui", "ui"),
    ("Open the saved evaluation UI page.", "console.open_ui", "ui"),
    ("Run the focused router pytest command.", "console.run_command", "run_command"),
    ("Run the holdout manifest verification command.", "console.run_command", "run_command"),
    ("Edit the Stage 1 safe-stage recovery source.", "console.edit_file", "file_edit"),
    ("Patch the hybrid router test file.", "console.edit_file", "file_edit"),
]

V9_WEB_FILE_ACTIONS = [
    ("Look up current sequence-classifier calibration notes online.", "web.lookup", "lookup"),
    ("Search online for current ModernBERT deployment guidance.", "web.lookup", "lookup"),
    ("Read the local router v8 manifest.", "file.search", "lookup"),
    ("Find the saved Stage 1C artifact metadata locally.", "file.search", "lookup"),
    ("Inspect local diagnostics for wrong risky subtype counts.", "file.search", "lookup"),
]

V9_MEMORY_CASES = [
    ("I like compact router updates for this exchange only.", "chat.no_action", "none"),
    ("Short diagnostic notes are easier for this chat; do not save that.", "chat.no_action", "none"),
    ("Explain when a preference statement should be saved.", "answer.question", "none"),
    ("What confirmation should memory writes require?", "answer.question", "none"),
    ("Remember that I prefer compact router updates.", "memory.save_preference", "memory"),
    ("Save that I prefer short router diagnostic summaries.", "memory.save_preference", "memory"),
]

V9_MESSY_PROMPTS = [
    ("pls run the hybrid check rn", "console.run_command", "run_command"),
    ("dont act just explain file edit safety", "answer.question", "none"),
    ("fix teh holdout builder file", "console.edit_file", "file_edit"),
    ("grab text outta this metrics image", "vision.ocr_image", "media"),
    ("remember i want compact router notes", "memory.save_preference", "memory"),
]


def v9_template_family(category: str, route: str, action_family: str, variant: str) -> str:
    return f"holdout_v9:{category}:{variant}:{route.replace('.', '_')}:{action_family}"


def v9_case(
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
        template_family=v9_template_family(category, route, action_family, variant),
    )
    case.update(v6.intent_method_metadata(route=route, action_family=action_family, text=text))
    return case


def build_holdout_v9_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V9_HARD_NEGATIVE_FORMS)
        form, route = V9_HARD_NEGATIVE_FORMS[form_index]
        cases.append(v9_case(f"v9_hn_{idx + 1:04d}", "hard_negative", form.format(topic=topic, n=idx + 1), route, "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V9_ANSWER_FORMS)
        cases.append(v9_case(f"v9_aq_{idx + 1:04d}", "answer_question", V9_ANSWER_FORMS[form_index].format(topic=topic, n=idx + 251), "answer.question", "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["direct_action"]):
        text, route, family = V9_DIRECT_ACTIONS[idx % len(V9_DIRECT_ACTIONS)]
        cases.append(v9_case(f"v9_direct_{idx + 1:04d}", "direct_action", f"{text} V9 case {idx + 401}.", route, family, variant=f"action_{idx % len(V9_DIRECT_ACTIONS):02d}"))
    for idx in range(split["ambiguous"]):
        text, flags = V9_AMBIGUOUS_REQUESTS[idx % len(V9_AMBIGUOUS_REQUESTS)]
        cases.append(v9_case(f"v9_amb_{idx + 1:04d}", "ambiguous", f"{text} V9 case {idx + 551}.", "ask_clarifying_question", "none", variant=f"amb_{idx % len(V9_AMBIGUOUS_REQUESTS):02d}", context_flags=flags))
    for idx in range(split["media_route"]):
        text, route, family = V9_MEDIA_ACTIONS[idx % len(V9_MEDIA_ACTIONS)]
        flags = {"HAS_IMAGE": True} if route.startswith("vision.") else {}
        required = ["HAS_IMAGE"] if route.startswith("vision.") else []
        cases.append(v9_case(f"v9_media_{idx + 1:04d}", "media_route", f"{text} V9 case {idx + 651}.", route, family, variant=f"media_{idx % len(V9_MEDIA_ACTIONS):02d}", context_flags=flags, required_context_flags=required))
    for idx in range(split["console_route"]):
        text, route, family = V9_CONSOLE_ACTIONS[idx % len(V9_CONSOLE_ACTIONS)]
        cases.append(v9_case(f"v9_console_{idx + 1:04d}", "console_route", f"{text} V9 case {idx + 751}.", route, family, variant=f"console_{idx % len(V9_CONSOLE_ACTIONS):02d}"))
    for idx in range(split["web_file_data"]):
        text, route, family = V9_WEB_FILE_ACTIONS[idx % len(V9_WEB_FILE_ACTIONS)]
        cases.append(v9_case(f"v9_webfile_{idx + 1:04d}", "web_file_data", f"{text} V9 case {idx + 826}.", route, family, variant=f"webfile_{idx % len(V9_WEB_FILE_ACTIONS):02d}"))
    for idx in range(split["memory_preference"]):
        text, route, family = V9_MEMORY_CASES[idx % len(V9_MEMORY_CASES)]
        cases.append(v9_case(f"v9_mem_{idx + 1:04d}", "memory_preference", f"{text} V9 case {idx + 901}.", route, family, variant=f"memory_{idx % len(V9_MEMORY_CASES):02d}"))
    for idx in range(split["messy_voice_typo"]):
        text, route, family = V9_MESSY_PROMPTS[idx % len(V9_MESSY_PROMPTS)]
        cases.append(v9_case(f"v9_messy_{idx + 1:04d}", "messy_voice_typo", f"{text} v9 case {idx + 951}", route, family, variant=f"messy_{idx % len(V9_MESSY_PROMPTS):02d}"))
    texts = [case["text"] for case in cases]
    ids = [case["id"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)) or len(ids) != len(set(ids)):
        raise ValueError("router_holdout_1000_v9 generation failed uniqueness or count checks")
    if any(not str(case.get("template_family", "")).startswith("holdout_v9:") for case in cases):
        raise ValueError("router_holdout_1000_v9 requires explicit holdout_v9 template families")
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


def build_holdout_v9_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR, output_file: str = DEFAULT_OUTPUT_FILE) -> dict[str, Any]:
    cases = [serializable_case(case) for case in build_holdout_v9_cases()]
    output_path = output_dir / output_file
    manifest_path = output_dir / "router_holdout_1000_v9_manifest.json"
    manifest = {
        "dataset": "router_holdout_1000_v9",
        "description": "Fresh router holdout with intent/method metadata and alternate v9 prompts; v9 is clean until inspected or tuned from.",
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
    parser = argparse.ArgumentParser(description="Build the clean router_holdout_1000_v9 JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args(argv)
    print(json.dumps(build_holdout_v9_dataset(args.output_dir, args.output_file), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
