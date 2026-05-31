from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from evals import router_gate
from training import router_holdout_v6_dataset as v6


DEFAULT_OUTPUT_DIR = Path("data/router_holdout_v16")
DEFAULT_OUTPUT_FILE = "router_holdout_1000_v16.jsonl"

V16_HARD_NEGATIVE_FORMS = [
    ("Dry-run note about {topic}; do not answer, search, edit, run, save, or start anything. V16 case {n}.", "chat.no_action"),
    ("Explain nothing yet: parked reminder mentioning {topic}, with every action lane closed. V16 case {n}.", "chat.no_action"),
    ("Discuss the boundary for {topic} as theory only, not as work to perform. V16 case {n}.", "answer.question"),
    ("This line only references {topic}; it should remain inert chat. V16 case {n}.", "chat.no_action"),
    ("What makes {topic} risky as a routing decision? Advice only. V16 case {n}.", "answer.question"),
]

V16_ANSWER_FORMS = [
    "Explain how NullXoid should reason about {topic} without doing the action. V16 case {n}.",
    "What would happen if someone requested {topic}? V16 case {n}.",
    "Compare intent and execution method for {topic}. V16 case {n}.",
    "Why should a router ask clarification before {topic}? V16 case {n}.",
    "Give guidance about {topic}, but keep this conversational. V16 case {n}.",
]

V16_DIRECT_ACTIONS = [
    ("Run the v16 router recovery tests now.", "console.run_command", "run_command"),
    ("Execute the focused hybrid gate suite.", "console.run_command", "run_command"),
    ("Apply the router v16 registration patch.", "console.edit_file", "file_edit"),
    ("Update the holdout loader code for v16.", "console.edit_file", "file_edit"),
    ("Start an agent job to audit serving parity artifacts.", "agent.start_job", "job"),
    ("Launch a background review of router shadow-mode readiness.", "agent.start_job", "job"),
]

V16_AMBIGUOUS_REQUESTS = [
    ("Handle the router follow-up when you know which one.", {}),
    ("Do that only if the previous confirmation is still valid.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Apply the selected patch if there is still one selected.", {"LAST_ASSISTANT_OFFERED_PATCH": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Finish the previous route task if it is unambiguous.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown"}),
    ("Take the next safe step if the target is still clear.", {}),
]

V16_MEDIA_ACTIONS = [
    ("Describe the uploaded route diagram.", "vision.describe_image", "media"),
    ("Tell me what the attached evaluation chart shows.", "vision.describe_image", "media"),
    ("OCR the text in this router screenshot.", "vision.ocr_image", "media"),
    ("Read the labels visible in the attached benchmark image.", "vision.ocr_image", "media"),
    ("Edit this image to obscure the secret token.", "vision.edit_image", "media_edit"),
    ("Blur the private key shown in the uploaded screenshot.", "vision.edit_image", "media_edit"),
]

V16_CONSOLE_ACTIONS = [
    ("Open the local router diagnostics dashboard.", "console.open_ui", "ui"),
    ("Open the saved holdout comparison view.", "console.open_ui", "ui"),
    ("Run the v16 clean holdout command.", "console.run_command", "run_command"),
    ("Run the hybrid gate regression tests.", "console.run_command", "run_command"),
    ("Edit the v16 dataset test module.", "console.edit_file", "file_edit"),
    ("Patch the hybrid gate choices for v16.", "console.edit_file", "file_edit"),
]

V16_WEB_FILE_ACTIONS = [
    ("Look up current classifier export docs online.", "web.lookup", "lookup"),
    ("Search the web for ONNX encoder serving notes.", "web.lookup", "lookup"),
    ("Read the local v15 diagnostic JSON file.", "file.search", "lookup"),
    ("Find the Stage 0 v21 metadata in the project.", "file.search", "lookup"),
    ("Inspect local benchmark logs for the recovered threshold.", "file.search", "lookup"),
]

V16_MEMORY_CASES = [
    ("I like compact router progress updates during diagnostics.", "chat.no_action", "none"),
    ("Compact updates help, but do not store that as memory.", "chat.no_action", "none"),
    ("Explain when preference wording should stay as chat.", "answer.question", "none"),
    ("What words make preference text an explicit memory request?", "answer.question", "none"),
    ("Remember that I prefer compact router progress updates.", "memory.save_preference", "memory"),
    ("Save my preference for compact router status summaries.", "memory.save_preference", "memory"),
]

V16_MESSY_PROMPTS = [
    ("pls run v16 router chek now", "console.run_command", "run_command"),
    ("dont do it explain risky route first", "answer.question", "none"),
    ("patch teh v16 loader pls", "console.edit_file", "file_edit"),
    ("read text frm this router screenshot", "vision.ocr_image", "media"),
    ("remember i like compact router updates", "memory.save_preference", "memory"),
]


def template_family(category: str, route: str, action_family: str, variant: str) -> str:
    return f"holdout_v16:{category}:{variant}:{route.replace('.', '_')}:{action_family}"


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


def build_holdout_v16_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[(idx * 29) % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V16_HARD_NEGATIVE_FORMS)
        form, route = V16_HARD_NEGATIVE_FORMS[form_index]
        cases.append(case_row(f"v16_hn_{idx + 1:04d}", "hard_negative", form.format(topic=topic, n=idx + 1), route, "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[(idx * 31) % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V16_ANSWER_FORMS)
        cases.append(case_row(f"v16_aq_{idx + 1:04d}", "answer_question", V16_ANSWER_FORMS[form_index].format(topic=topic, n=idx + 251), "answer.question", "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["direct_action"]):
        text, route, family = V16_DIRECT_ACTIONS[idx % len(V16_DIRECT_ACTIONS)]
        cases.append(case_row(f"v16_direct_{idx + 1:04d}", "direct_action", f"{text} V16 case {idx + 401}.", route, family, variant=f"action_{idx % len(V16_DIRECT_ACTIONS):02d}"))
    for idx in range(split["ambiguous"]):
        text, flags = V16_AMBIGUOUS_REQUESTS[idx % len(V16_AMBIGUOUS_REQUESTS)]
        cases.append(case_row(f"v16_amb_{idx + 1:04d}", "ambiguous", f"{text} V16 case {idx + 551}.", "ask_clarifying_question", "none", variant=f"amb_{idx % len(V16_AMBIGUOUS_REQUESTS):02d}", context_flags=flags))
    for idx in range(split["media_route"]):
        text, route, family = V16_MEDIA_ACTIONS[idx % len(V16_MEDIA_ACTIONS)]
        flags = {"HAS_IMAGE": True} if route.startswith("vision.") else {}
        required = ["HAS_IMAGE"] if route.startswith("vision.") else []
        cases.append(case_row(f"v16_media_{idx + 1:04d}", "media_route", f"{text} V16 case {idx + 651}.", route, family, variant=f"media_{idx % len(V16_MEDIA_ACTIONS):02d}", context_flags=flags, required_context_flags=required))
    for idx in range(split["console_route"]):
        text, route, family = V16_CONSOLE_ACTIONS[idx % len(V16_CONSOLE_ACTIONS)]
        cases.append(case_row(f"v16_console_{idx + 1:04d}", "console_route", f"{text} V16 case {idx + 751}.", route, family, variant=f"console_{idx % len(V16_CONSOLE_ACTIONS):02d}"))
    for idx in range(split["web_file_data"]):
        text, route, family = V16_WEB_FILE_ACTIONS[idx % len(V16_WEB_FILE_ACTIONS)]
        cases.append(case_row(f"v16_webfile_{idx + 1:04d}", "web_file_data", f"{text} V16 case {idx + 826}.", route, family, variant=f"webfile_{idx % len(V16_WEB_FILE_ACTIONS):02d}"))
    for idx in range(split["memory_preference"]):
        text, route, family = V16_MEMORY_CASES[idx % len(V16_MEMORY_CASES)]
        cases.append(case_row(f"v16_mem_{idx + 1:04d}", "memory_preference", f"{text} V16 case {idx + 901}.", route, family, variant=f"memory_{idx % len(V16_MEMORY_CASES):02d}"))
    for idx in range(split["messy_voice_typo"]):
        text, route, family = V16_MESSY_PROMPTS[idx % len(V16_MESSY_PROMPTS)]
        cases.append(case_row(f"v16_messy_{idx + 1:04d}", "messy_voice_typo", f"{text} v16 case {idx + 951}", route, family, variant=f"messy_{idx % len(V16_MESSY_PROMPTS):02d}"))
    texts = [case["text"] for case in cases]
    ids = [case["id"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)) or len(ids) != len(set(ids)):
        raise ValueError("router_holdout_1000_v16 generation failed uniqueness or count checks")
    if any(not str(case.get("template_family", "")).startswith("holdout_v16:") for case in cases):
        raise ValueError("router_holdout_1000_v16 requires explicit holdout_v16 template families")
    return cases


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def build_holdout_v16_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR, output_file: str = DEFAULT_OUTPUT_FILE) -> dict[str, Any]:
    cases = [v6.serializable_case(case) for case in build_holdout_v16_cases()]
    output_path = output_dir / output_file
    manifest_path = output_dir / "router_holdout_1000_v16_manifest.json"
    manifest = {
        "dataset": "router_holdout_1000_v16",
        "description": "Fresh router holdout with v16 prompt families, intent/method metadata, and unknown-context ambiguity cases; clean until inspected or tuned from.",
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
    parser = argparse.ArgumentParser(description="Build the clean router_holdout_1000_v16 JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args(argv)
    print(json.dumps(build_holdout_v16_dataset(args.output_dir, args.output_file), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
