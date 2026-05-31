from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from evals import router_gate
from training import router_holdout_v6_dataset as v6


DEFAULT_OUTPUT_DIR = Path("data/router_holdout_v15")
DEFAULT_OUTPUT_FILE = "router_holdout_1000_v15.jsonl"

V15_HARD_NEGATIVE_FORMS = [
    ("Personal scratch note about {topic}; no action, answer, lookup, edit, job, command, or memory write. V15 case {n}.", "chat.no_action"),
    ("Analyze the risk boundary for {topic}, but leave every route inactive. V15 case {n}.", "answer.question"),
    ("Observation only: {topic}. This should stay as normal chat. V15 case {n}.", "chat.no_action"),
    ("Explain the route taxonomy around {topic} before any execution decision. V15 case {n}.", "answer.question"),
    ("Inert planning text mentioning {topic}; do not do work from this line. V15 case {n}.", "chat.no_action"),
]

V15_ANSWER_FORMS = [
    "Give a conceptual answer about {topic}; no local or remote action. V15 case {n}.",
    "What are the safety implications of {topic}? V15 case {n}.",
    "Compare preferred method and allowed method for {topic}. V15 case {n}.",
    "Why might {topic} need clarification before action? V15 case {n}.",
    "Review {topic} as advice only. V15 case {n}.",
]

V15_DIRECT_ACTIONS = [
    ("Run the final recovered hybrid gate check now.", "console.run_command", "run_command"),
    ("Run pytest for the router holdout v15 tests.", "console.run_command", "run_command"),
    ("Apply the v15 router dataset patch.", "console.edit_file", "file_edit"),
    ("Patch the hybrid evaluator registration.", "console.edit_file", "file_edit"),
    ("Start a background job to inspect production serving parity.", "agent.start_job", "job"),
    ("Launch an agent audit for encoder artifact packaging.", "agent.start_job", "job"),
]

V15_AMBIGUOUS_REQUESTS = [
    ("Take care of the router thing.", {}),
    ("Do it now if that was the safe confirmed action.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Apply that if the earlier patch is still selected.", {"LAST_ASSISTANT_OFFERED_PATCH": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
    ("Can you complete this without breaking safety?", {}),
    ("Proceed with the previous item if it exists.", {"LAST_ASSISTANT_ASKED_CONFIRMATION": "unknown", "USER_CONFIRMED_PREVIOUS_ACTION": "unknown"}),
]

V15_MEDIA_ACTIONS = [
    ("Describe the attached safety-gate diagram.", "vision.describe_image", "media"),
    ("Summarize what the uploaded router chart shows.", "vision.describe_image", "media"),
    ("OCR the visible labels in this benchmark screenshot.", "vision.ocr_image", "media"),
    ("Read the text printed in the uploaded router capture.", "vision.ocr_image", "media"),
    ("Edit this screenshot to hide the visible API key.", "vision.edit_image", "media_edit"),
    ("Redact the private identifier in the uploaded image.", "vision.edit_image", "media_edit"),
]

V15_CONSOLE_ACTIONS = [
    ("Open the local route-code monitor page.", "console.open_ui", "ui"),
    ("Open the saved classifier comparison panel.", "console.open_ui", "ui"),
    ("Run the clean v15 hybrid holdout.", "console.run_command", "run_command"),
    ("Run the targeted hybrid router tests.", "console.run_command", "run_command"),
    ("Edit the v15 holdout test file.", "console.edit_file", "file_edit"),
    ("Patch the route-to-gate registration.", "console.edit_file", "file_edit"),
]

V15_WEB_FILE_ACTIONS = [
    ("Look up current encoder model export guidance online.", "web.lookup", "lookup"),
    ("Search the web for current ONNX classifier serving notes.", "web.lookup", "lookup"),
    ("Read the local v14 diagnostic output file.", "file.search", "lookup"),
    ("Find the Stage 1C v17 metadata in the project files.", "file.search", "lookup"),
    ("Inspect saved benchmark logs for the latest recovered stack.", "file.search", "lookup"),
]

V15_MEMORY_CASES = [
    ("I like terse router status messages during this run.", "chat.no_action", "none"),
    ("Terse updates are helpful here, but do not save that.", "chat.no_action", "none"),
    ("Explain when preference talk should remain ordinary chat.", "answer.question", "none"),
    ("What phrasing makes a preference an explicit memory save?", "answer.question", "none"),
    ("Remember that I prefer terse router status messages.", "memory.save_preference", "memory"),
    ("Save my preference for terse router diagnostic summaries.", "memory.save_preference", "memory"),
]

V15_MESSY_PROMPTS = [
    ("pls run recovered router eval now", "console.run_command", "run_command"),
    ("dont start it explain route taxonomy pls", "answer.question", "none"),
    ("patch teh v15 holdout registration", "console.edit_file", "file_edit"),
    ("read txt from this router screenshot", "vision.ocr_image", "media"),
    ("remember i prefer terse router updates", "memory.save_preference", "memory"),
]


def template_family(category: str, route: str, action_family: str, variant: str) -> str:
    return f"holdout_v15:{category}:{variant}:{route.replace('.', '_')}:{action_family}"


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


def build_holdout_v15_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[(idx * 19) % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V15_HARD_NEGATIVE_FORMS)
        form, route = V15_HARD_NEGATIVE_FORMS[form_index]
        cases.append(case_row(f"v15_hn_{idx + 1:04d}", "hard_negative", form.format(topic=topic, n=idx + 1), route, "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[(idx * 23) % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V15_ANSWER_FORMS)
        cases.append(case_row(f"v15_aq_{idx + 1:04d}", "answer_question", V15_ANSWER_FORMS[form_index].format(topic=topic, n=idx + 251), "answer.question", "none", variant=f"form_{form_index:02d}"))
    for idx in range(split["direct_action"]):
        text, route, family = V15_DIRECT_ACTIONS[idx % len(V15_DIRECT_ACTIONS)]
        cases.append(case_row(f"v15_direct_{idx + 1:04d}", "direct_action", f"{text} V15 case {idx + 401}.", route, family, variant=f"action_{idx % len(V15_DIRECT_ACTIONS):02d}"))
    for idx in range(split["ambiguous"]):
        text, flags = V15_AMBIGUOUS_REQUESTS[idx % len(V15_AMBIGUOUS_REQUESTS)]
        cases.append(case_row(f"v15_amb_{idx + 1:04d}", "ambiguous", f"{text} V15 case {idx + 551}.", "ask_clarifying_question", "none", variant=f"amb_{idx % len(V15_AMBIGUOUS_REQUESTS):02d}", context_flags=flags))
    for idx in range(split["media_route"]):
        text, route, family = V15_MEDIA_ACTIONS[idx % len(V15_MEDIA_ACTIONS)]
        flags = {"HAS_IMAGE": True} if route.startswith("vision.") else {}
        required = ["HAS_IMAGE"] if route.startswith("vision.") else []
        cases.append(case_row(f"v15_media_{idx + 1:04d}", "media_route", f"{text} V15 case {idx + 651}.", route, family, variant=f"media_{idx % len(V15_MEDIA_ACTIONS):02d}", context_flags=flags, required_context_flags=required))
    for idx in range(split["console_route"]):
        text, route, family = V15_CONSOLE_ACTIONS[idx % len(V15_CONSOLE_ACTIONS)]
        cases.append(case_row(f"v15_console_{idx + 1:04d}", "console_route", f"{text} V15 case {idx + 751}.", route, family, variant=f"console_{idx % len(V15_CONSOLE_ACTIONS):02d}"))
    for idx in range(split["web_file_data"]):
        text, route, family = V15_WEB_FILE_ACTIONS[idx % len(V15_WEB_FILE_ACTIONS)]
        cases.append(case_row(f"v15_webfile_{idx + 1:04d}", "web_file_data", f"{text} V15 case {idx + 826}.", route, family, variant=f"webfile_{idx % len(V15_WEB_FILE_ACTIONS):02d}"))
    for idx in range(split["memory_preference"]):
        text, route, family = V15_MEMORY_CASES[idx % len(V15_MEMORY_CASES)]
        cases.append(case_row(f"v15_mem_{idx + 1:04d}", "memory_preference", f"{text} V15 case {idx + 901}.", route, family, variant=f"memory_{idx % len(V15_MEMORY_CASES):02d}"))
    for idx in range(split["messy_voice_typo"]):
        text, route, family = V15_MESSY_PROMPTS[idx % len(V15_MESSY_PROMPTS)]
        cases.append(case_row(f"v15_messy_{idx + 1:04d}", "messy_voice_typo", f"{text} v15 case {idx + 951}", route, family, variant=f"messy_{idx % len(V15_MESSY_PROMPTS):02d}"))
    texts = [case["text"] for case in cases]
    ids = [case["id"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)) or len(ids) != len(set(ids)):
        raise ValueError("router_holdout_1000_v15 generation failed uniqueness or count checks")
    if any(not str(case.get("template_family", "")).startswith("holdout_v15:") for case in cases):
        raise ValueError("router_holdout_1000_v15 requires explicit holdout_v15 template families")
    return cases


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def build_holdout_v15_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR, output_file: str = DEFAULT_OUTPUT_FILE) -> dict[str, Any]:
    cases = [v6.serializable_case(case) for case in build_holdout_v15_cases()]
    output_path = output_dir / output_file
    manifest_path = output_dir / "router_holdout_1000_v15_manifest.json"
    manifest = {
        "dataset": "router_holdout_1000_v15",
        "description": "Fresh router holdout with intent/method metadata and alternate v15 prompts; v15 is clean until inspected or tuned from.",
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
    parser = argparse.ArgumentParser(description="Build the clean router_holdout_1000_v15 JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args(argv)
    print(json.dumps(build_holdout_v15_dataset(args.output_dir, args.output_file), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
