from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from evals import router_gate
from training import router_holdout_v6_dataset as v6


DEFAULT_OUTPUT_DIR = Path("data/router_holdout_v11")
DEFAULT_OUTPUT_FILE = "router_holdout_1000_v11.jsonl"

V11_HARD_NEGATIVE_FORMS = [
    ("Private runbook note: {topic}. No route or action should happen. V11 case {n}.", "chat.no_action"),
    ("Reason about {topic} in plain language; do not invoke any lane. V11 case {n}.", "answer.question"),
    ("I am weighing choices around {topic}; this is discussion only. V11 case {n}.", "answer.question"),
    ("Local scratch item about {topic}; skip reply, memory, files, jobs, and commands. V11 case {n}.", "chat.no_action"),
    ("Talk through the implications of {topic} before any tool is considered. V11 case {n}.", "answer.question"),
]

V11_ANSWER_FORMS = [
    "Explain the safe interpretation of {topic} without doing it. V11 case {n}.",
    "What questions should be resolved before acting on {topic}? V11 case {n}.",
    "Compare likely intent and implementation method for {topic}. V11 case {n}.",
    "Why is {topic} a routing boundary? V11 case {n}.",
    "Give non-operational advice about {topic}. V11 case {n}.",
]

V11_DIRECT_ACTIONS = [
    ("Run the current hybrid router proof command.", "console.run_command", "run_command"),
    ("Run the router backend pytest target.", "console.run_command", "run_command"),
    ("Apply the patch to the hybrid gate evaluator.", "console.edit_file", "file_edit"),
    ("Edit the Stage 1 safe-read subtype training source.", "console.edit_file", "file_edit"),
    ("Start an agent task to verify production serving parity.", "agent.start_job", "job"),
    ("Launch the broader agent audit for router release readiness.", "agent.start_job", "job"),
]

V11_AMBIGUOUS_REQUESTS = [
    ("Please move the router work along.", {}),
    ("Do the thing we just covered.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Apply that if it is appropriate.", {"LAST_ASSISTANT_OFFERED_PATCH": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Can you make the safe choice here?", {}),
    ("Yes, continue with the prior item.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
]

V11_MEDIA_ACTIONS = [
    ("Describe the attached metrics screenshot at a high level.", "vision.describe_image", "media"),
    ("Summarize what is visible in this uploaded router capture.", "vision.describe_image", "media"),
    ("Read every visible word in the attached diagnostic image.", "vision.ocr_image", "media"),
    ("OCR this uploaded benchmark capture and return the text.", "vision.ocr_image", "media"),
    ("Edit the uploaded image to hide the secret value.", "vision.edit_image", "media_edit"),
    ("Redact the sensitive field in this attached screenshot.", "vision.edit_image", "media_edit"),
]

V11_CONSOLE_ACTIONS = [
    ("Open the router proof dashboard locally.", "console.open_ui", "ui"),
    ("Open the local benchmark results UI.", "console.open_ui", "ui"),
    ("Run the clean holdout verification command.", "console.run_command", "run_command"),
    ("Run the hybrid gate focused pytest target.", "console.run_command", "run_command"),
    ("Edit the v11 holdout loader code.", "console.edit_file", "file_edit"),
    ("Patch the Stage 1 subtype regression test.", "console.edit_file", "file_edit"),
]

V11_WEB_FILE_ACTIONS = [
    ("Look up current sequence-classifier threshold guidance online.", "web.lookup", "lookup"),
    ("Search the web for current encoder deployment notes.", "web.lookup", "lookup"),
    ("Read the local v10 diagnostic result JSON.", "file.search", "lookup"),
    ("Find the v11 Stage 1 artifact metadata in project files.", "file.search", "lookup"),
    ("Inspect local test logs for router holdout failures.", "file.search", "lookup"),
]

V11_MEMORY_CASES = [
    ("I prefer brief router summaries in this thread only.", "chat.no_action", "none"),
    ("Short status notes help right now; do not store that preference.", "chat.no_action", "none"),
    ("Explain the difference between preference talk and memory save.", "answer.question", "none"),
    ("When should a router treat a preference as explicit memory?", "answer.question", "none"),
    ("Remember that I prefer brief router summaries.", "memory.save_preference", "memory"),
    ("Save that concise router status notes are my preference.", "memory.save_preference", "memory"),
]

V11_MESSY_PROMPTS = [
    ("pls run the clean router proof now", "console.run_command", "run_command"),
    ("dont touch files explain teh patch risk", "answer.question", "none"),
    ("fix the safe read subtype code pls", "console.edit_file", "file_edit"),
    ("ocr this router pic for text", "vision.ocr_image", "media"),
    ("remember i prefer brief router notes", "memory.save_preference", "memory"),
]


def v11_template_family(category: str, route: str, action_family: str, variant: str) -> str:
    return f"holdout_v11:{category}:{variant}:{route.replace('.', '_')}:{action_family}"


def v11_case(
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
        template_family=v11_template_family(category, route, action_family, variant),
    )
    case.update(v6.intent_method_metadata(route=route, action_family=action_family, text=text))
    return case


def build_holdout_v11_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V11_HARD_NEGATIVE_FORMS)
        form, route = V11_HARD_NEGATIVE_FORMS[form_index]
        cases.append(v11_case(f"v11_hn_{idx + 1:04d}", "hard_negative", form.format(topic=topic, n=idx + 1), route, "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V11_ANSWER_FORMS)
        cases.append(v11_case(f"v11_aq_{idx + 1:04d}", "answer_question", V11_ANSWER_FORMS[form_index].format(topic=topic, n=idx + 251), "answer.question", "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["direct_action"]):
        text, route, family = V11_DIRECT_ACTIONS[idx % len(V11_DIRECT_ACTIONS)]
        cases.append(v11_case(f"v11_direct_{idx + 1:04d}", "direct_action", f"{text} V11 case {idx + 401}.", route, family, variant=f"action_{idx % len(V11_DIRECT_ACTIONS):02d}"))
    for idx in range(split["ambiguous"]):
        text, flags = V11_AMBIGUOUS_REQUESTS[idx % len(V11_AMBIGUOUS_REQUESTS)]
        cases.append(v11_case(f"v11_amb_{idx + 1:04d}", "ambiguous", f"{text} V11 case {idx + 551}.", "ask_clarifying_question", "none", variant=f"amb_{idx % len(V11_AMBIGUOUS_REQUESTS):02d}", context_flags=flags))
    for idx in range(split["media_route"]):
        text, route, family = V11_MEDIA_ACTIONS[idx % len(V11_MEDIA_ACTIONS)]
        flags = {"HAS_IMAGE": True} if route.startswith("vision.") else {}
        required = ["HAS_IMAGE"] if route.startswith("vision.") else []
        cases.append(v11_case(f"v11_media_{idx + 1:04d}", "media_route", f"{text} V11 case {idx + 651}.", route, family, variant=f"media_{idx % len(V11_MEDIA_ACTIONS):02d}", context_flags=flags, required_context_flags=required))
    for idx in range(split["console_route"]):
        text, route, family = V11_CONSOLE_ACTIONS[idx % len(V11_CONSOLE_ACTIONS)]
        cases.append(v11_case(f"v11_console_{idx + 1:04d}", "console_route", f"{text} V11 case {idx + 751}.", route, family, variant=f"console_{idx % len(V11_CONSOLE_ACTIONS):02d}"))
    for idx in range(split["web_file_data"]):
        text, route, family = V11_WEB_FILE_ACTIONS[idx % len(V11_WEB_FILE_ACTIONS)]
        cases.append(v11_case(f"v11_webfile_{idx + 1:04d}", "web_file_data", f"{text} V11 case {idx + 826}.", route, family, variant=f"webfile_{idx % len(V11_WEB_FILE_ACTIONS):02d}"))
    for idx in range(split["memory_preference"]):
        text, route, family = V11_MEMORY_CASES[idx % len(V11_MEMORY_CASES)]
        cases.append(v11_case(f"v11_mem_{idx + 1:04d}", "memory_preference", f"{text} V11 case {idx + 901}.", route, family, variant=f"memory_{idx % len(V11_MEMORY_CASES):02d}"))
    for idx in range(split["messy_voice_typo"]):
        text, route, family = V11_MESSY_PROMPTS[idx % len(V11_MESSY_PROMPTS)]
        cases.append(v11_case(f"v11_messy_{idx + 1:04d}", "messy_voice_typo", f"{text} v11 case {idx + 951}", route, family, variant=f"messy_{idx % len(V11_MESSY_PROMPTS):02d}"))
    texts = [case["text"] for case in cases]
    ids = [case["id"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)) or len(ids) != len(set(ids)):
        raise ValueError("router_holdout_1000_v11 generation failed uniqueness or count checks")
    if any(not str(case.get("template_family", "")).startswith("holdout_v11:") for case in cases):
        raise ValueError("router_holdout_1000_v11 requires explicit holdout_v11 template families")
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


def build_holdout_v11_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR, output_file: str = DEFAULT_OUTPUT_FILE) -> dict[str, Any]:
    cases = [serializable_case(case) for case in build_holdout_v11_cases()]
    output_path = output_dir / output_file
    manifest_path = output_dir / "router_holdout_1000_v11_manifest.json"
    manifest = {
        "dataset": "router_holdout_1000_v11",
        "description": "Fresh router holdout with intent/method metadata and alternate v11 prompts; v11 is clean until inspected or tuned from.",
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
    parser = argparse.ArgumentParser(description="Build the clean router_holdout_1000_v11 JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args(argv)
    print(json.dumps(build_holdout_v11_dataset(args.output_dir, args.output_file), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
