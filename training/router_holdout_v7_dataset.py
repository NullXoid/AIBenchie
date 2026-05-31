from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from evals import router_gate
from training import router_holdout_v6_dataset as v6


DEFAULT_OUTPUT_DIR = Path("data/router_holdout_v7")
DEFAULT_OUTPUT_FILE = "router_holdout_1000_v7.jsonl"

V7_HARD_NEGATIVE_FORMS = [
    ("Talk through {topic}; do not execute, edit, open, search, save, or launch anything. V7 case {n}.", "answer.question"),
    ("This is a tabletop note about {topic}, with no tool or action lane and no response required. V7 case {n}.", "chat.no_action"),
    ("Keep this as analysis only while considering {topic}. V7 case {n}.", "answer.question"),
    ("Describe the safety boundary for {topic} without changing system state. V7 case {n}.", "answer.question"),
    ("I am not asking for action; compare interpretations of {topic}. V7 case {n}.", "answer.question"),
]


def v7_template_family(category: str, route: str, action_family: str, variant: str) -> str:
    return f"holdout_v7:{category}:{variant}:{route.replace('.', '_')}:{action_family}"


def v7_case(
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
        template_family=v7_template_family(category, route, action_family, variant),
    )
    case.update(v6.intent_method_metadata(route=route, action_family=action_family, text=text))
    return case


def build_holdout_v7_cases() -> list[dict[str, Any]]:
    split = router_gate.SPLIT_1000
    cases: list[dict[str, Any]] = []
    for idx in range(split["hard_negative"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(V7_HARD_NEGATIVE_FORMS)
        form, route = V7_HARD_NEGATIVE_FORMS[form_index]
        cases.append(
            v7_case(
                f"v7_hn_{idx + 1:04d}",
                "hard_negative",
                form.format(topic=topic, n=idx + 1),
                route,
                "none",
                variant=f"form_{form_index:02d}",
            )
        )
    for idx in range(split["answer_question"]):
        topic = router_gate.DISCUSSION_TOPICS[idx % len(router_gate.DISCUSSION_TOPICS)]
        form_index = (idx // len(router_gate.DISCUSSION_TOPICS)) % len(v6.V6_ANSWER_FORMS)
        cases.append(
            v7_case(
                f"v7_aq_{idx + 1:04d}",
                "answer_question",
                v6.V6_ANSWER_FORMS[form_index].format(topic=topic, n=idx + 251).replace("V6", "V7"),
                "answer.question",
                "none",
                variant=f"form_{form_index:02d}",
            )
        )
    for idx in range(split["direct_action"]):
        text, route, family = v6.V6_DIRECT_ACTIONS[idx % len(v6.V6_DIRECT_ACTIONS)]
        cases.append(v7_case(f"v7_direct_{idx + 1:04d}", "direct_action", f"{text} V7 case {idx + 401}.", route, family, variant=f"action_{idx % len(v6.V6_DIRECT_ACTIONS):02d}"))
    for idx in range(split["ambiguous"]):
        text, flags = v6.V6_AMBIGUOUS_REQUESTS[idx % len(v6.V6_AMBIGUOUS_REQUESTS)]
        cases.append(v7_case(f"v7_amb_{idx + 1:04d}", "ambiguous", f"{text} V7 case {idx + 551}.", "ask_clarifying_question", "none", variant=f"amb_{idx % len(v6.V6_AMBIGUOUS_REQUESTS):02d}", context_flags=flags))
    for idx in range(split["media_route"]):
        text, route, family = v6.V6_MEDIA_ACTIONS[idx % len(v6.V6_MEDIA_ACTIONS)]
        flags = {"HAS_IMAGE": True} if route.startswith("vision.") else {}
        required = ["HAS_IMAGE"] if route.startswith("vision.") else []
        cases.append(v7_case(f"v7_media_{idx + 1:04d}", "media_route", f"{text} V7 case {idx + 651}.", route, family, variant=f"media_{idx % len(v6.V6_MEDIA_ACTIONS):02d}", context_flags=flags, required_context_flags=required))
    for idx in range(split["console_route"]):
        text, route, family = v6.V6_CONSOLE_ACTIONS[idx % len(v6.V6_CONSOLE_ACTIONS)]
        cases.append(v7_case(f"v7_console_{idx + 1:04d}", "console_route", f"{text} V7 case {idx + 751}.", route, family, variant=f"console_{idx % len(v6.V6_CONSOLE_ACTIONS):02d}"))
    for idx in range(split["web_file_data"]):
        text, route, family = v6.V6_WEB_FILE_ACTIONS[idx % len(v6.V6_WEB_FILE_ACTIONS)]
        cases.append(v7_case(f"v7_webfile_{idx + 1:04d}", "web_file_data", f"{text} V7 case {idx + 826}.", route, family, variant=f"webfile_{idx % len(v6.V6_WEB_FILE_ACTIONS):02d}"))
    for idx in range(split["memory_preference"]):
        text, route, family = v6.V6_MEMORY_CASES[idx % len(v6.V6_MEMORY_CASES)]
        cases.append(v7_case(f"v7_mem_{idx + 1:04d}", "memory_preference", f"{text} V7 case {idx + 901}.", route, family, variant=f"memory_{idx % len(v6.V6_MEMORY_CASES):02d}"))
    for idx in range(split["messy_voice_typo"]):
        text, route, family = v6.V6_MESSY_PROMPTS[idx % len(v6.V6_MESSY_PROMPTS)]
        cases.append(v7_case(f"v7_messy_{idx + 1:04d}", "messy_voice_typo", f"{text} v7 case {idx + 951}", route, family, variant=f"messy_{idx % len(v6.V6_MESSY_PROMPTS):02d}"))
    texts = [case["text"] for case in cases]
    ids = [case["id"] for case in cases]
    if len(cases) != 1000 or len(texts) != len(set(texts)) or len(ids) != len(set(ids)):
        raise ValueError("router_holdout_1000_v7 generation failed uniqueness or count checks")
    if any(not str(case.get("template_family", "")).startswith("holdout_v7:") for case in cases):
        raise ValueError("router_holdout_1000_v7 requires explicit holdout_v7 template families")
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


def build_holdout_v7_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR, output_file: str = DEFAULT_OUTPUT_FILE) -> dict[str, Any]:
    cases = [serializable_case(case) for case in build_holdout_v7_cases()]
    output_path = output_dir / output_file
    manifest_path = output_dir / "router_holdout_1000_v7_manifest.json"
    manifest = {
        "dataset": "router_holdout_1000_v7",
        "description": "Clean router holdout with intent/method metadata and corrected hard-negative answer/no-action taxonomy.",
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
    parser = argparse.ArgumentParser(description="Build the clean router_holdout_1000_v7 JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    args = parser.parse_args(argv)
    print(json.dumps(build_holdout_v7_dataset(args.output_dir, args.output_file), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
