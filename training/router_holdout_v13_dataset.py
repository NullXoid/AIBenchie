from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from evals import router_gate
from training import router_holdout_v6_dataset as v6


DEFAULT_OUTPUT_DIR = Path("data/router_holdout_v13")
DEFAULT_OUTPUT_FILE = "router_holdout_1000_v13.jsonl"

V13_HARD_NEGATIVE_FORMS = [
    ("Parking-lot note about {topic}; it is not a request for work or an answer. V13 case {n}.", "chat.no_action"),
    ("Describe the decision boundary for {topic}, but keep every tool inactive. V13 case {n}.", "answer.question"),
    ("This is only a local reminder involving {topic}; do not reply with an action. V13 case {n}.", "chat.no_action"),
    ("Walk me through {topic} conceptually before any route is selected. V13 case {n}.", "answer.question"),
    ("Raw scratch text mentioning {topic}; no command, memory write, lookup, edit, or job. V13 case {n}.", "chat.no_action"),
]

V13_ANSWER_FORMS = [
    "Explain how a router should interpret {topic} without doing anything. V13 case {n}.",
    "What safety checks should come before acting on {topic}? V13 case {n}.",
    "Compare route intent and execution method for {topic} as advice only. V13 case {n}.",
    "Why is {topic} a difficult abstention case? V13 case {n}.",
    "Give a non-operational review of {topic}. V13 case {n}.",
]

V13_DIRECT_ACTIONS = [
    ("Run the final focused router test command now.", "console.run_command", "run_command"),
    ("Run pytest for the hybrid gate regression file.", "console.run_command", "run_command"),
    ("Apply the safe-stage routing patch.", "console.edit_file", "file_edit"),
    ("Edit the new holdout builder test.", "console.edit_file", "file_edit"),
    ("Start a background agent job to check serving parity.", "agent.start_job", "job"),
    ("Launch an agent task for the shadow-mode readiness audit.", "agent.start_job", "job"),
]

V13_AMBIGUOUS_REQUESTS = [
    ("Take the next router step.", {}),
    ("Do it if that is still the right move.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Apply that when it makes sense.", {"LAST_ASSISTANT_OFFERED_PATCH": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Can you finish this safely?", {}),
    ("Continue from the prior approval if there was one.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
]

V13_MEDIA_ACTIONS = [
    ("Describe the attached routing chart.", "vision.describe_image", "media"),
    ("Summarize the visible UI in this uploaded benchmark image.", "vision.describe_image", "media"),
    ("Extract all readable text from this router screenshot.", "vision.ocr_image", "media"),
    ("OCR the uploaded diagnostic capture.", "vision.ocr_image", "media"),
    ("Edit this attached image to obscure the credential.", "vision.edit_image", "media_edit"),
    ("Redact the account value from the uploaded screenshot.", "vision.edit_image", "media_edit"),
]

V13_CONSOLE_ACTIONS = [
    ("Open the local intent-router comparison page.", "console.open_ui", "ui"),
    ("Open the saved hybrid evaluation dashboard.", "console.open_ui", "ui"),
    ("Run the v13 holdout evaluation command.", "console.run_command", "run_command"),
    ("Run the router holdout dataset tests.", "console.run_command", "run_command"),
    ("Edit the v13 holdout loader source.", "console.edit_file", "file_edit"),
    ("Patch the G02 safe-stage subtype test.", "console.edit_file", "file_edit"),
]

V13_WEB_FILE_ACTIONS = [
    ("Look up current sequence-classifier calibration notes online.", "web.lookup", "lookup"),
    ("Search the web for current local encoder serving guidance.", "web.lookup", "lookup"),
    ("Read the local v12 diagnostic result file.", "file.search", "lookup"),
    ("Find the Stage 1C v13 metadata in project files.", "file.search", "lookup"),
    ("Inspect saved router logs for the latest holdout result.", "file.search", "lookup"),
]

V13_MEMORY_CASES = [
    ("I prefer short router updates for this one run.", "chat.no_action", "none"),
    ("Concise router notes are nice here; do not save that.", "chat.no_action", "none"),
    ("Explain how explicit memory requests differ from preference talk.", "answer.question", "none"),
    ("What phrasing would make a preference worth saving?", "answer.question", "none"),
    ("Remember that I prefer short router updates.", "memory.save_preference", "memory"),
    ("Save my preference for concise router status notes.", "memory.save_preference", "memory"),
]

V13_MESSY_PROMPTS = [
    ("pls run final router checks now", "console.run_command", "run_command"),
    ("dont do it explain route boudary pls", "answer.question", "none"),
    ("patch teh safe stage route test", "console.edit_file", "file_edit"),
    ("read text from this router img", "vision.ocr_image", "media"),
    ("remember i like short router updates", "memory.save_preference", "memory"),
]


def v13_template_family(category: str, route: str, action_family: str, variant: str) -> str:
    return f"holdout_v13:{category}:{variant}:{route.replace('.', '_')}:{action_family}"


def v13_case(
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
        template_family=v13_template_family(category, route, action_family, variant),
    )
    case.update(v6.intent_method_metadata(route=route, action_family=action_family, text=text))
    return case


def build_holdout_v13_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[(idx * 7) % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V13_HARD_NEGATIVE_FORMS)
        form, route = V13_HARD_NEGATIVE_FORMS[form_index]
        cases.append(v13_case(f"v13_hn_{idx + 1:04d}", "hard_negative", form.format(topic=topic, n=idx + 1), route, "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[(idx * 11) % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V13_ANSWER_FORMS)
        cases.append(v13_case(f"v13_aq_{idx + 1:04d}", "answer_question", V13_ANSWER_FORMS[form_index].format(topic=topic, n=idx + 251), "answer.question", "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["direct_action"]):
        text, route, family = V13_DIRECT_ACTIONS[idx % len(V13_DIRECT_ACTIONS)]
        cases.append(v13_case(f"v13_direct_{idx + 1:04d}", "direct_action", f"{text} V13 case {idx + 401}.", route, family, variant=f"action_{idx % len(V13_DIRECT_ACTIONS):02d}"))
    for idx in range(split["ambiguous"]):
        text, flags = V13_AMBIGUOUS_REQUESTS[idx % len(V13_AMBIGUOUS_REQUESTS)]
        cases.append(v13_case(f"v13_amb_{idx + 1:04d}", "ambiguous", f"{text} V13 case {idx + 551}.", "ask_clarifying_question", "none", variant=f"amb_{idx % len(V13_AMBIGUOUS_REQUESTS):02d}", context_flags=flags))
    for idx in range(split["media_route"]):
        text, route, family = V13_MEDIA_ACTIONS[idx % len(V13_MEDIA_ACTIONS)]
        flags = {"HAS_IMAGE": True} if route.startswith("vision.") else {}
        required = ["HAS_IMAGE"] if route.startswith("vision.") else []
        cases.append(v13_case(f"v13_media_{idx + 1:04d}", "media_route", f"{text} V13 case {idx + 651}.", route, family, variant=f"media_{idx % len(V13_MEDIA_ACTIONS):02d}", context_flags=flags, required_context_flags=required))
    for idx in range(split["console_route"]):
        text, route, family = V13_CONSOLE_ACTIONS[idx % len(V13_CONSOLE_ACTIONS)]
        cases.append(v13_case(f"v13_console_{idx + 1:04d}", "console_route", f"{text} V13 case {idx + 751}.", route, family, variant=f"console_{idx % len(V13_CONSOLE_ACTIONS):02d}"))
    for idx in range(split["web_file_data"]):
        text, route, family = V13_WEB_FILE_ACTIONS[idx % len(V13_WEB_FILE_ACTIONS)]
        cases.append(v13_case(f"v13_webfile_{idx + 1:04d}", "web_file_data", f"{text} V13 case {idx + 826}.", route, family, variant=f"webfile_{idx % len(V13_WEB_FILE_ACTIONS):02d}"))
    for idx in range(split["memory_preference"]):
        text, route, family = V13_MEMORY_CASES[idx % len(V13_MEMORY_CASES)]
        cases.append(v13_case(f"v13_mem_{idx + 1:04d}", "memory_preference", f"{text} V13 case {idx + 901}.", route, family, variant=f"memory_{idx % len(V13_MEMORY_CASES):02d}"))
    for idx in range(split["messy_voice_typo"]):
        text, route, family = V13_MESSY_PROMPTS[idx % len(V13_MESSY_PROMPTS)]
        cases.append(v13_case(f"v13_messy_{idx + 1:04d}", "messy_voice_typo", f"{text} v13 case {idx + 951}", route, family, variant=f"messy_{idx % len(V13_MESSY_PROMPTS):02d}"))
    texts = [case["text"] for case in cases]
    ids = [case["id"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)) or len(ids) != len(set(ids)):
        raise ValueError("router_holdout_1000_v13 generation failed uniqueness or count checks")
    if any(not str(case.get("template_family", "")).startswith("holdout_v13:") for case in cases):
        raise ValueError("router_holdout_1000_v13 requires explicit holdout_v13 template families")
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


def build_holdout_v13_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR, output_file: str = DEFAULT_OUTPUT_FILE) -> dict[str, Any]:
    cases = [serializable_case(case) for case in build_holdout_v13_cases()]
    output_path = output_dir / output_file
    manifest_path = output_dir / "router_holdout_1000_v13_manifest.json"
    manifest = {
        "dataset": "router_holdout_1000_v13",
        "description": "Fresh router holdout with intent/method metadata and alternate v13 prompts; v13 is clean until inspected or tuned from.",
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
    parser = argparse.ArgumentParser(description="Build the clean router_holdout_1000_v13 JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args(argv)
    print(json.dumps(build_holdout_v13_dataset(args.output_dir, args.output_file), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
