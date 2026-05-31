from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from evals import router_gate


DEFAULT_OUTPUT_DIR = Path("data/router_holdout_v5")
DEFAULT_OUTPUT_FILE = "router_holdout_1000_v5.jsonl"

V5_HARD_NEGATIVE_FORMS = [
    "Keep this non-operational: discuss {topic} without routing to a tool. V5 case {n}.",
    "No tool call should happen; outline the considerations for {topic}. V5 case {n}.",
    "Treat this as a dry discussion about {topic}, not an action request. V5 case {n}.",
    "Stay explanatory and do not modify, run, search, save, or launch anything about {topic}. V5 case {n}.",
    "Only talk through the routing boundary for {topic}. V5 case {n}.",
]

V5_ANSWER_FORMS = [
    "Please answer a question about {topic}. V5 case {n}.",
    "Help me understand {topic}. V5 case {n}.",
    "Give guidance on {topic}. V5 case {n}.",
    "What is the right way to think about {topic}? V5 case {n}.",
    "Can you explain the tradeoffs around {topic}? V5 case {n}.",
]

V5_DIRECT_ACTIONS = [
    ("Run the fresh router holdout command now.", "console.run_command", "run_command"),
    ("Execute the hybrid gate command in the terminal.", "console.run_command", "run_command"),
    ("Apply the safe-lane subtype patch.", "console.edit_file", "file_edit"),
    ("Update the local router candidate manifest.", "console.edit_file", "file_edit"),
    ("Start a background job to review routing artifacts.", "agent.start_job", "job"),
    ("Launch the long-running safe-lane analysis task.", "agent.start_job", "job"),
]

V5_AMBIGUOUS_REQUESTS = [
    "Can you sort out that routing thing?",
    "Handle whichever router path applies.",
    "Do the appropriate thing with that artifact.",
    "Can you take care of that safety issue?",
    "Move this along through the correct channel.",
]

V5_MEDIA_ACTIONS = [
    ("Describe the attached metrics screenshot.", "vision.describe_image", "media"),
    ("Summarize what appears in this UI capture.", "vision.describe_image", "media"),
    ("OCR the attached benchmark screenshot.", "vision.ocr_image", "media"),
    ("Extract the visible table text from this image.", "vision.ocr_image", "media"),
    ("Edit this screenshot to hide the username.", "vision.edit_image", "media_edit"),
    ("Blur the background of the uploaded image.", "vision.edit_image", "media_edit"),
]

V5_CONSOLE_ACTIONS = [
    ("Open the local intent-router UI.", "console.open_ui", "ui"),
    ("Open the benchmark results panel.", "console.open_ui", "ui"),
    ("Run the local pytest command for hybrid gates.", "console.run_command", "run_command"),
    ("Execute the PowerShell command that checks router files.", "console.run_command", "run_command"),
    ("Edit the safe-lane subtype source file.", "console.edit_file", "file_edit"),
    ("Patch the route-gate evaluation test.", "console.edit_file", "file_edit"),
]

V5_WEB_FILE_ACTIONS = [
    ("Look up current safe classifier calibration guidance online.", "web.lookup", "lookup"),
    ("Search online for the latest DeBERTa model documentation.", "web.lookup", "lookup"),
    ("Read the local stage1 subtype cleanup manifest.", "file.search", "lookup"),
    ("Find the frozen router candidate manifest locally.", "file.search", "lookup"),
    ("Inspect saved local evaluation logs for subtype_wrong.", "file.search", "lookup"),
]

V5_MEMORY_CASES = [
    ("I like short safety reports; this is just a note.", "chat.no_action", "none"),
    ("My preference is concise updates, no need to save it.", "chat.no_action", "none"),
    ("How does preference memory work in the router?", "answer.question", "none"),
    ("Should a preference be saved only after an explicit request?", "answer.question", "none"),
    ("Remember that I prefer concise safety reports.", "memory.save_preference", "memory"),
    ("Save my preference for clean holdout first.", "memory.save_preference", "memory"),
]

V5_MESSY_PROMPTS = [
    ("pls exec fresh holdout gate", "console.run_command", "run_command"),
    ("dont do action explain tool route pls", "answer.question", "none"),
    ("patch teh safe lane file", "console.edit_file", "file_edit"),
    ("ocr this metrics img pls", "vision.ocr_image", "media"),
    ("remember concise router updates pls", "memory.save_preference", "memory"),
]


def v5_template_family(category: str, route: str, action_family: str, variant: str) -> str:
    return f"holdout_v5:{category}:{variant}:{route.replace('.', '_')}:{action_family}"


def v5_case(
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
    return router_gate.case_row(
        case_id,
        category,
        text,
        route,
        action_family,
        context_flags=context_flags,
        required_context_flags=required_context_flags,
        template_family=v5_template_family(category, route, action_family, variant),
    )


def build_holdout_v5_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V5_HARD_NEGATIVE_FORMS)
        cases.append(
            v5_case(
                f"v5_hn_{idx + 1:04d}",
                "hard_negative",
                V5_HARD_NEGATIVE_FORMS[form_index].format(topic=topic, n=idx + 1),
                "chat.no_action",
                "none",
                variant=f"form_{form_index:02d}",
            )
        )
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V5_ANSWER_FORMS)
        cases.append(
            v5_case(
                f"v5_aq_{idx + 1:04d}",
                "answer_question",
                V5_ANSWER_FORMS[form_index].format(topic=topic, n=idx + 251),
                "answer.question",
                "none",
                variant=f"form_{form_index:02d}",
            )
        )
    for idx in range(split["direct_action"]):
        text, route, family = V5_DIRECT_ACTIONS[idx % len(V5_DIRECT_ACTIONS)]
        cases.append(v5_case(f"v5_direct_{idx + 1:04d}", "direct_action", f"{text} V5 case {idx + 401}.", route, family, variant=f"action_{idx % len(V5_DIRECT_ACTIONS):02d}"))
    for idx in range(split["ambiguous"]):
        text = V5_AMBIGUOUS_REQUESTS[idx % len(V5_AMBIGUOUS_REQUESTS)]
        cases.append(v5_case(f"v5_amb_{idx + 1:04d}", "ambiguous", f"{text} V5 case {idx + 551}.", "ask_clarifying_question", "none", variant=f"amb_{idx % len(V5_AMBIGUOUS_REQUESTS):02d}"))
    for idx in range(split["media_route"]):
        text, route, family = V5_MEDIA_ACTIONS[idx % len(V5_MEDIA_ACTIONS)]
        flags = {"HAS_IMAGE": True} if route.startswith("vision.") else {}
        required = ["HAS_IMAGE"] if route.startswith("vision.") else []
        cases.append(v5_case(f"v5_media_{idx + 1:04d}", "media_route", f"{text} V5 case {idx + 651}.", route, family, variant=f"media_{idx % len(V5_MEDIA_ACTIONS):02d}", context_flags=flags, required_context_flags=required))
    for idx in range(split["console_route"]):
        text, route, family = V5_CONSOLE_ACTIONS[idx % len(V5_CONSOLE_ACTIONS)]
        cases.append(v5_case(f"v5_console_{idx + 1:04d}", "console_route", f"{text} V5 case {idx + 751}.", route, family, variant=f"console_{idx % len(V5_CONSOLE_ACTIONS):02d}"))
    for idx in range(split["web_file_data"]):
        text, route, family = V5_WEB_FILE_ACTIONS[idx % len(V5_WEB_FILE_ACTIONS)]
        cases.append(v5_case(f"v5_webfile_{idx + 1:04d}", "web_file_data", f"{text} V5 case {idx + 826}.", route, family, variant=f"webfile_{idx % len(V5_WEB_FILE_ACTIONS):02d}"))
    for idx in range(split["memory_preference"]):
        text, route, family = V5_MEMORY_CASES[idx % len(V5_MEMORY_CASES)]
        cases.append(v5_case(f"v5_mem_{idx + 1:04d}", "memory_preference", f"{text} V5 case {idx + 901}.", route, family, variant=f"memory_{idx % len(V5_MEMORY_CASES):02d}"))
    for idx in range(split["messy_voice_typo"]):
        text, route, family = V5_MESSY_PROMPTS[idx % len(V5_MESSY_PROMPTS)]
        cases.append(v5_case(f"v5_messy_{idx + 1:04d}", "messy_voice_typo", f"{text} v5 case {idx + 951}", route, family, variant=f"messy_{idx % len(V5_MESSY_PROMPTS):02d}"))
    texts = [case["text"] for case in cases]
    ids = [case["id"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)) or len(ids) != len(set(ids)):
        raise ValueError("router_holdout_1000_v5 generation failed uniqueness or count checks")
    if any(not str(case.get("template_family", "")).startswith("holdout_v5:") for case in cases):
        raise ValueError("router_holdout_1000_v5 requires explicit holdout_v5 template families")
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
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def build_holdout_v5_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR, output_file: str = DEFAULT_OUTPUT_FILE) -> dict[str, Any]:
    cases = [serializable_case(case) for case in build_holdout_v5_cases()]
    output_path = output_dir / output_file
    manifest_path = output_dir / "router_holdout_1000_v5_manifest.json"
    write_jsonl(output_path, cases)
    manifest = {
        "dataset": "router_holdout_1000_v5",
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
    parser = argparse.ArgumentParser(description="Build the clean router_holdout_1000_v5 JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args(argv)
    manifest = build_holdout_v5_dataset(output_dir=args.output_dir, output_file=args.output_file)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
