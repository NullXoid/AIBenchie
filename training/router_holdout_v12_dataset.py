from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from evals import router_gate
from training import router_holdout_v6_dataset as v6


DEFAULT_OUTPUT_DIR = Path("data/router_holdout_v12")
DEFAULT_OUTPUT_FILE = "router_holdout_1000_v12.jsonl"

V12_HARD_NEGATIVE_FORMS = [
    ("Archived note about {topic}; no answer, memory, file, job, UI, or command should start. V12 case {n}.", "chat.no_action"),
    ("Explain the boundary around {topic}, staying completely non-operational. V12 case {n}.", "answer.question"),
    ("I am only thinking through {topic}; do not route this into work. V12 case {n}.", "chat.no_action"),
    ("Discuss what {topic} would mean before anything is opened, edited, saved, or run. V12 case {n}.", "answer.question"),
    ("Scratch reminder mentioning {topic}; leave every execution lane idle. V12 case {n}.", "chat.no_action"),
]

V12_ANSWER_FORMS = [
    "Explain how to recognize {topic} without performing it. V12 case {n}.",
    "What would make {topic} safe enough to act on later? V12 case {n}.",
    "Compare the possible intent families for {topic}; keep this advisory. V12 case {n}.",
    "Why can {topic} be confused with a direct action request? V12 case {n}.",
    "Give conceptual guidance about {topic}; do not touch local state. V12 case {n}.",
]

V12_DIRECT_ACTIONS = [
    ("Run the hybrid router verification target now.", "console.run_command", "run_command"),
    ("Run pytest for the intent-router backend tests.", "console.run_command", "run_command"),
    ("Apply the code change to the hybrid gate module.", "console.edit_file", "file_edit"),
    ("Patch the safe-stage subtype test file.", "console.edit_file", "file_edit"),
    ("Start an agent job to audit router serving parity.", "agent.start_job", "job"),
    ("Launch a background agent task for release readiness review.", "agent.start_job", "job"),
]

V12_AMBIGUOUS_REQUESTS = [
    ("Move that router item forward somehow.", {}),
    ("Yes, do the next thing if that is what we meant.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Apply it if the prior context is enough.", {"LAST_ASSISTANT_OFFERED_PATCH": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Can you handle this safely?", {}),
    ("Continue with the earlier router thing.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
]

V12_MEDIA_ACTIONS = [
    ("Describe the uploaded router diagram in broad terms.", "vision.describe_image", "media"),
    ("Tell me what this attached evaluation screenshot shows.", "vision.describe_image", "media"),
    ("OCR the visible text in this benchmark screenshot.", "vision.ocr_image", "media"),
    ("Read the words from the uploaded router capture.", "vision.ocr_image", "media"),
    ("Edit the uploaded screenshot to blur the token value.", "vision.edit_image", "media_edit"),
    ("Modify this attached image to redact the private field.", "vision.edit_image", "media_edit"),
]

V12_CONSOLE_ACTIONS = [
    ("Open the local router metrics page.", "console.open_ui", "ui"),
    ("Open the saved benchmark dashboard.", "console.open_ui", "ui"),
    ("Run the clean-holdout hybrid gate command.", "console.run_command", "run_command"),
    ("Run the Stage 0 encoder regression tests.", "console.run_command", "run_command"),
    ("Edit the v12 holdout dataset loader.", "console.edit_file", "file_edit"),
    ("Patch the hybrid gate safe-stage routing code.", "console.edit_file", "file_edit"),
]

V12_WEB_FILE_ACTIONS = [
    ("Look up current encoder calibration guidance online.", "web.lookup", "lookup"),
    ("Search the web for current local classifier serving notes.", "web.lookup", "lookup"),
    ("Read the local v11 diagnostic result JSON.", "file.search", "lookup"),
    ("Find the Stage 1C v12 artifact metadata in the repo.", "file.search", "lookup"),
    ("Inspect local router test logs for holdout failures.", "file.search", "lookup"),
]

V12_MEMORY_CASES = [
    ("I like terse router updates while this run is active.", "chat.no_action", "none"),
    ("Brief progress notes are useful here; do not remember that.", "chat.no_action", "none"),
    ("Explain when preference talk becomes a memory-save request.", "answer.question", "none"),
    ("What wording makes a memory preference explicit?", "answer.question", "none"),
    ("Remember that I prefer terse router updates.", "memory.save_preference", "memory"),
    ("Save my preference for brief router progress notes.", "memory.save_preference", "memory"),
]

V12_MESSY_PROMPTS = [
    ("pls run router proof checks now", "console.run_command", "run_command"),
    ("dont do stuff just explain teh route risk", "answer.question", "none"),
    ("fix the safe stage test file pls", "console.edit_file", "file_edit"),
    ("ocr this router screenshot text", "vision.ocr_image", "media"),
    ("remember i want terse router updates", "memory.save_preference", "memory"),
]


def v12_template_family(category: str, route: str, action_family: str, variant: str) -> str:
    return f"holdout_v12:{category}:{variant}:{route.replace('.', '_')}:{action_family}"


def v12_case(
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
        template_family=v12_template_family(category, route, action_family, variant),
    )
    case.update(v6.intent_method_metadata(route=route, action_family=action_family, text=text))
    return case


def build_holdout_v12_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[(idx * 3) % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V12_HARD_NEGATIVE_FORMS)
        form, route = V12_HARD_NEGATIVE_FORMS[form_index]
        cases.append(v12_case(f"v12_hn_{idx + 1:04d}", "hard_negative", form.format(topic=topic, n=idx + 1), route, "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[(idx * 5) % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V12_ANSWER_FORMS)
        cases.append(v12_case(f"v12_aq_{idx + 1:04d}", "answer_question", V12_ANSWER_FORMS[form_index].format(topic=topic, n=idx + 251), "answer.question", "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["direct_action"]):
        text, route, family = V12_DIRECT_ACTIONS[idx % len(V12_DIRECT_ACTIONS)]
        cases.append(v12_case(f"v12_direct_{idx + 1:04d}", "direct_action", f"{text} V12 case {idx + 401}.", route, family, variant=f"action_{idx % len(V12_DIRECT_ACTIONS):02d}"))
    for idx in range(split["ambiguous"]):
        text, flags = V12_AMBIGUOUS_REQUESTS[idx % len(V12_AMBIGUOUS_REQUESTS)]
        cases.append(v12_case(f"v12_amb_{idx + 1:04d}", "ambiguous", f"{text} V12 case {idx + 551}.", "ask_clarifying_question", "none", variant=f"amb_{idx % len(V12_AMBIGUOUS_REQUESTS):02d}", context_flags=flags))
    for idx in range(split["media_route"]):
        text, route, family = V12_MEDIA_ACTIONS[idx % len(V12_MEDIA_ACTIONS)]
        flags = {"HAS_IMAGE": True} if route.startswith("vision.") else {}
        required = ["HAS_IMAGE"] if route.startswith("vision.") else []
        cases.append(v12_case(f"v12_media_{idx + 1:04d}", "media_route", f"{text} V12 case {idx + 651}.", route, family, variant=f"media_{idx % len(V12_MEDIA_ACTIONS):02d}", context_flags=flags, required_context_flags=required))
    for idx in range(split["console_route"]):
        text, route, family = V12_CONSOLE_ACTIONS[idx % len(V12_CONSOLE_ACTIONS)]
        cases.append(v12_case(f"v12_console_{idx + 1:04d}", "console_route", f"{text} V12 case {idx + 751}.", route, family, variant=f"console_{idx % len(V12_CONSOLE_ACTIONS):02d}"))
    for idx in range(split["web_file_data"]):
        text, route, family = V12_WEB_FILE_ACTIONS[idx % len(V12_WEB_FILE_ACTIONS)]
        cases.append(v12_case(f"v12_webfile_{idx + 1:04d}", "web_file_data", f"{text} V12 case {idx + 826}.", route, family, variant=f"webfile_{idx % len(V12_WEB_FILE_ACTIONS):02d}"))
    for idx in range(split["memory_preference"]):
        text, route, family = V12_MEMORY_CASES[idx % len(V12_MEMORY_CASES)]
        cases.append(v12_case(f"v12_mem_{idx + 1:04d}", "memory_preference", f"{text} V12 case {idx + 901}.", route, family, variant=f"memory_{idx % len(V12_MEMORY_CASES):02d}"))
    for idx in range(split["messy_voice_typo"]):
        text, route, family = V12_MESSY_PROMPTS[idx % len(V12_MESSY_PROMPTS)]
        cases.append(v12_case(f"v12_messy_{idx + 1:04d}", "messy_voice_typo", f"{text} v12 case {idx + 951}", route, family, variant=f"messy_{idx % len(V12_MESSY_PROMPTS):02d}"))
    texts = [case["text"] for case in cases]
    ids = [case["id"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)) or len(ids) != len(set(ids)):
        raise ValueError("router_holdout_1000_v12 generation failed uniqueness or count checks")
    if any(not str(case.get("template_family", "")).startswith("holdout_v12:") for case in cases):
        raise ValueError("router_holdout_1000_v12 requires explicit holdout_v12 template families")
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


def build_holdout_v12_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR, output_file: str = DEFAULT_OUTPUT_FILE) -> dict[str, Any]:
    cases = [serializable_case(case) for case in build_holdout_v12_cases()]
    output_path = output_dir / output_file
    manifest_path = output_dir / "router_holdout_1000_v12_manifest.json"
    manifest = {
        "dataset": "router_holdout_1000_v12",
        "description": "Fresh router holdout with intent/method metadata and alternate v12 prompts; v12 is clean until inspected or tuned from.",
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
    parser = argparse.ArgumentParser(description="Build the clean router_holdout_1000_v12 JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args(argv)
    print(json.dumps(build_holdout_v12_dataset(args.output_dir, args.output_file), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
