from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from evals import router_gate


DEFAULT_OUTPUT_DIR = Path("data/router_holdout_v4")
DEFAULT_OUTPUT_FILE = "router_holdout_1000_v4.jsonl"

V4_HARD_NEGATIVE_FORMS = [
    "Keep this conversational: walk through {topic} without taking action. V4 case {n}.",
    "No execution or edits; reason about {topic}. V4 case {n}.",
    "This is a policy review only: compare choices for {topic}. V4 case {n}.",
    "Before touching anything, describe the risks around {topic}. V4 case {n}.",
    "Stay in chat mode and explain the boundary for {topic}. V4 case {n}.",
]

V4_ANSWER_FORMS = [
    "Give me an explanation of {topic}. V4 case {n}.",
    "What should I understand about {topic}? V4 case {n}.",
    "Why would {topic} matter for the router? V4 case {n}.",
    "Compare the safe and risky interpretations of {topic}. V4 case {n}.",
    "How should I think about {topic} before deciding? V4 case {n}.",
]

V4_DIRECT_ACTIONS = [
    ("Run the clean holdout router gate now.", "console.run_command", "run_command"),
    ("Execute the command that runs the hybrid router tests.", "console.run_command", "run_command"),
    ("Apply the saved router safety patch to the files.", "console.edit_file", "file_edit"),
    ("Modify the local subtype config file.", "console.edit_file", "file_edit"),
    ("Start a background audit of the routing corpus.", "agent.start_job", "job"),
    ("Launch the multi-step model comparison job.", "agent.start_job", "job"),
]

V4_AMBIGUOUS_REQUESTS = [
    "Can you handle that route issue?",
    "Move the router thing forward.",
    "Do whatever is appropriate with that patch context.",
    "Can you take care of the model/tool situation?",
    "Please put this through the right lane.",
]

V4_MEDIA_ACTIONS = [
    ("Describe the new attached routing screenshot.", "vision.describe_image", "media"),
    ("Tell me what this uploaded UI image shows.", "vision.describe_image", "media"),
    ("Extract the text from the attached router screenshot.", "vision.ocr_image", "media"),
    ("Read the labels visible in this image.", "vision.ocr_image", "media"),
    ("Edit this image to blur the private path names.", "vision.edit_image", "media_edit"),
    ("Retouch the screenshot by darkening the background.", "vision.edit_image", "media_edit"),
]

V4_CONSOLE_ACTIONS = [
    ("Open the local router dashboard UI.", "console.open_ui", "ui"),
    ("Open the evaluation console panel.", "console.open_ui", "ui"),
    ("Run the PowerShell router smoke command.", "console.run_command", "run_command"),
    ("Execute the focused gate command in the terminal.", "console.run_command", "run_command"),
    ("Edit the currently selected router source file.", "console.edit_file", "file_edit"),
    ("Patch the benchmark manifest file.", "console.edit_file", "file_edit"),
]

V4_WEB_FILE_ACTIONS = [
    ("Look up current encoder-router deployment guidance online.", "web.lookup", "lookup"),
    ("Search the web for the current ModernBERT model card.", "web.lookup", "lookup"),
    ("Read the local hybrid candidate manifest.", "file.search", "lookup"),
    ("Find the saved v4 holdout JSONL on disk.", "file.search", "lookup"),
    ("Inspect local logs for stage0_false_risky_actions.", "file.search", "lookup"),
]

V4_MEMORY_CASES = [
    ("I like concise router reports, but do not store that.", "chat.no_action", "none"),
    ("I prefer safety-first summaries in this conversation.", "chat.no_action", "none"),
    ("Can you remember routing preferences in general?", "answer.question", "none"),
    ("Would saving my router style as memory be useful?", "answer.question", "none"),
    ("Remember that I prefer concise router reports.", "memory.save_preference", "memory"),
    ("Save my preference for safety-first summaries.", "memory.save_preference", "memory"),
]

V4_MESSY_PROMPTS = [
    ("pls run clean hldout gate now", "console.run_command", "run_command"),
    ("dont execute just explain why risky route is scary", "answer.question", "none"),
    ("edit teh local router config pls", "console.edit_file", "file_edit"),
    ("read text frm this screenshot pls", "vision.ocr_image", "media"),
    ("remember i like terse safety reports", "memory.save_preference", "memory"),
]


def v4_template_family(category: str, route: str, action_family: str, variant: str) -> str:
    return f"holdout_v4:{category}:{variant}:{route.replace('.', '_')}:{action_family}"


def v4_case(
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
        template_family=v4_template_family(category, route, action_family, variant),
    )


def build_holdout_v4_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V4_HARD_NEGATIVE_FORMS)
        form = V4_HARD_NEGATIVE_FORMS[form_index]
        cases.append(
            v4_case(
                f"v4_hn_{idx + 1:04d}",
                "hard_negative",
                form.format(topic=topic, n=idx + 1),
                "chat.no_action",
                "none",
                variant=f"form_{form_index:02d}",
            )
        )
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V4_ANSWER_FORMS)
        form = V4_ANSWER_FORMS[form_index]
        cases.append(
            v4_case(
                f"v4_aq_{idx + 1:04d}",
                "answer_question",
                form.format(topic=topic, n=idx + 251),
                "answer.question",
                "none",
                variant=f"form_{form_index:02d}",
            )
        )
    for idx in range(split["direct_action"]):
        text, route, family = V4_DIRECT_ACTIONS[idx % len(V4_DIRECT_ACTIONS)]
        cases.append(
            v4_case(
                f"v4_direct_{idx + 1:04d}",
                "direct_action",
                f"{text} V4 case {idx + 401}.",
                route,
                family,
                variant=f"action_{idx % len(V4_DIRECT_ACTIONS):02d}",
            )
        )
    for idx in range(split["ambiguous"]):
        text = V4_AMBIGUOUS_REQUESTS[idx % len(V4_AMBIGUOUS_REQUESTS)]
        cases.append(
            v4_case(
                f"v4_amb_{idx + 1:04d}",
                "ambiguous",
                f"{text} V4 case {idx + 551}.",
                "ask_clarifying_question",
                "none",
                variant=f"amb_{idx % len(V4_AMBIGUOUS_REQUESTS):02d}",
            )
        )
    for idx in range(split["media_route"]):
        text, route, family = V4_MEDIA_ACTIONS[idx % len(V4_MEDIA_ACTIONS)]
        flags = {"HAS_IMAGE": True} if route.startswith("vision.") else {}
        required = ["HAS_IMAGE"] if route.startswith("vision.") else []
        cases.append(
            v4_case(
                f"v4_media_{idx + 1:04d}",
                "media_route",
                f"{text} V4 case {idx + 651}.",
                route,
                family,
                variant=f"media_{idx % len(V4_MEDIA_ACTIONS):02d}",
                context_flags=flags,
                required_context_flags=required,
            )
        )
    for idx in range(split["console_route"]):
        text, route, family = V4_CONSOLE_ACTIONS[idx % len(V4_CONSOLE_ACTIONS)]
        cases.append(
            v4_case(
                f"v4_console_{idx + 1:04d}",
                "console_route",
                f"{text} V4 case {idx + 751}.",
                route,
                family,
                variant=f"console_{idx % len(V4_CONSOLE_ACTIONS):02d}",
            )
        )
    for idx in range(split["web_file_data"]):
        text, route, family = V4_WEB_FILE_ACTIONS[idx % len(V4_WEB_FILE_ACTIONS)]
        cases.append(
            v4_case(
                f"v4_webfile_{idx + 1:04d}",
                "web_file_data",
                f"{text} V4 case {idx + 826}.",
                route,
                family,
                variant=f"webfile_{idx % len(V4_WEB_FILE_ACTIONS):02d}",
            )
        )
    for idx in range(split["memory_preference"]):
        text, route, family = V4_MEMORY_CASES[idx % len(V4_MEMORY_CASES)]
        cases.append(
            v4_case(
                f"v4_mem_{idx + 1:04d}",
                "memory_preference",
                f"{text} V4 case {idx + 901}.",
                route,
                family,
                variant=f"memory_{idx % len(V4_MEMORY_CASES):02d}",
            )
        )
    for idx in range(split["messy_voice_typo"]):
        text, route, family = V4_MESSY_PROMPTS[idx % len(V4_MESSY_PROMPTS)]
        cases.append(
            v4_case(
                f"v4_messy_{idx + 1:04d}",
                "messy_voice_typo",
                f"{text} v4 case {idx + 951}",
                route,
                family,
                variant=f"messy_{idx % len(V4_MESSY_PROMPTS):02d}",
            )
        )
    texts = [case["text"] for case in cases]
    ids = [case["id"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)) or len(ids) != len(set(ids)):
        raise ValueError("router_holdout_1000_v4 generation failed uniqueness or count checks")
    if any(str(case.get("template_family", "")).startswith("holdout_v4:") is False for case in cases):
        raise ValueError("router_holdout_1000_v4 requires explicit holdout_v4 template families")
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


def build_holdout_v4_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR, output_file: str = DEFAULT_OUTPUT_FILE) -> dict[str, Any]:
    cases = [serializable_case(case) for case in build_holdout_v4_cases()]
    output_path = output_dir / output_file
    manifest_path = output_dir / "router_holdout_1000_v4_manifest.json"
    write_jsonl(output_path, cases)
    manifest = {
        "dataset": "router_holdout_1000_v4",
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
    parser = argparse.ArgumentParser(description="Build the clean router_holdout_1000_v4 JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args(argv)
    manifest = build_holdout_v4_dataset(output_dir=args.output_dir, output_file=args.output_file)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
