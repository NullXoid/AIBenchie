from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evals import router_gate, router_hybrid_gate
from training import router_embedding_classifier as classifier
from training import router_template_splits


DEFAULT_MISS_AUDIT = Path(".suite/local/router_hybrid_miss_audit_hybrid_classifier_v1.json")
DEFAULT_FRONTIER_REPORTS = (
    Path(".suite/local/router_hybrid_stage0_frontier_console_semantics_350_hybrid_classifier_v1.json"),
    Path(".suite/local/router_hybrid_stage0_frontier_direct_action_boundaries_500_hybrid_classifier_v1.json"),
)
DEFAULT_OUTPUT_DIR = Path("data/router_stage0_hard_positive_v1")
SPLIT_ID = "router_stage0_hard_positive_v1"
RISKY_CODES = ("R05", "R07", "R08", "R10", "R13")
CONTEXT_FLAGS = (
    "HAS_IMAGE",
    "ACTIVE_FILE",
    "LAST_ASSISTANT_OFFERED_PATCH",
    "USER_CONFIRMED_PREVIOUS_ACTION",
    "LAST_ASSISTANT_ASKED_CONFIRMATION",
)


PAIRED_ROUTE_EXAMPLES: dict[str, dict[str, list[dict[str, Any]]]] = {
    "R05": {
        "positive": [
            {"text": "Edit this image to blur the background.", "context_flags": {"HAS_IMAGE": "true"}},
            {"text": "Remove the background from the attached image.", "context_flags": {"HAS_IMAGE": "true"}},
            {"text": "Make this picture brighter and crop it.", "context_flags": {"HAS_IMAGE": "true"}},
            {"text": "Change the image so the background is darker.", "context_flags": {"HAS_IMAGE": "true"}},
            {"text": "Retouch this photo and remove the glare.", "context_flags": {"HAS_IMAGE": "true"}},
            {"text": "Add a soft shadow to the uploaded picture.", "context_flags": {"HAS_IMAGE": "true"}},
            {"text": "Resize the attached image and sharpen it.", "context_flags": {"HAS_IMAGE": "true"}},
            {"text": "Modify this screenshot to highlight the button.", "context_flags": {"HAS_IMAGE": "true"}},
            {"text": "Erase the watermark from this image.", "context_flags": {"HAS_IMAGE": "true"}},
            {"text": "Make the foreground subject larger in the image.", "context_flags": {"HAS_IMAGE": "true"}},
        ],
        "negative": [
            {"text": "Can you describe how you would edit this image?", "code": "R01", "context_flags": {"HAS_IMAGE": "true"}},
            {"text": "What would happen if we changed the image background?", "code": "R01", "context_flags": {"HAS_IMAGE": "true"}},
            {"text": "I am thinking about image editing tools.", "code": "R00", "context_flags": {"HAS_IMAGE": "unknown"}},
        ],
    },
    "R07": {
        "positive": [
            {"text": "Apply the patch we discussed.", "context_flags": {"LAST_ASSISTANT_OFFERED_PATCH": "true"}},
            {"text": "Edit the selected file to fix that bug.", "context_flags": {"ACTIVE_FILE": "true"}},
            {"text": "Change the router test file to cover that case.", "context_flags": {"ACTIVE_FILE": "true"}},
        ],
        "negative": [
            {"text": "Would applying the patch fix it?", "code": "R01", "context_flags": {"LAST_ASSISTANT_OFFERED_PATCH": "true"}},
            {"text": "Explain whether editing the file would help.", "code": "R01", "context_flags": {"ACTIVE_FILE": "true"}},
            {"text": "Talk about patch safety without changing files.", "code": "R00", "context_flags": {"ACTIVE_FILE": "unknown"}},
        ],
    },
    "R08": {
        "positive": [
            {"text": "Run the backend tests now."},
            {"text": "Execute npm test in the project."},
            {"text": "Install the package with pip now."},
        ],
        "negative": [
            {"text": "Explain what would happen if we ran the backend tests.", "code": "R01"},
            {"text": "Would running npm test help here?", "code": "R01"},
            {"text": "I was thinking about command safety.", "code": "R00"},
        ],
    },
    "R10": {
        "positive": [
            {"text": "Start the repo inspection job."},
            {"text": "Kick off a background agent to audit the codebase."},
            {"text": "Begin the long-running migration analysis task."},
        ],
        "negative": [
            {"text": "What would the repo inspection job do?", "code": "R01"},
            {"text": "Should we start a background job for this?", "code": "R01"},
            {"text": "I am considering an agent workflow.", "code": "R00"},
        ],
    },
    "R13": {
        "positive": [
            {"text": "Remember that I prefer short answers."},
            {"text": "Save this preference: use compact router reports."},
            {"text": "Please remember that I do not want holdout artifacts committed."},
        ],
        "negative": [
            {"text": "I prefer short answers.", "code": "R00"},
            {"text": "My preference is probably shorter replies.", "code": "R00"},
            {"text": "Explain how memory preferences are saved.", "code": "R01"},
        ],
    },
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def route_code(route: str) -> str:
    return router_gate.ROUTE_TO_CODE[route]


def context_flags_for_code(code: str, explicit: dict[str, Any] | None = None) -> dict[str, str]:
    flags = {flag: "unknown" for flag in CONTEXT_FLAGS}
    if code in {"R03", "R04", "R05"}:
        flags["HAS_IMAGE"] = "true"
    if code == "R07":
        flags["ACTIVE_FILE"] = "true"
    for key, value in (explicit or {}).items():
        if key in flags:
            flags[key] = classifier.normalize_context_flag_value(value)
    return flags


def record(
    *,
    record_id: str,
    text: str,
    code: str,
    source: str,
    training_role: str,
    template_family: str,
    must_not_emit_g04: bool = False,
    context_flags: dict[str, Any] | None = None,
    required_context_flags: list[str] | None = None,
) -> dict[str, Any]:
    route = router_gate.ROUTE_CODES[code]
    return {
        "id": record_id,
        "text": text,
        "code": code,
        "route": route,
        "expected_stage0_gate": router_hybrid_gate.code_to_gate(code),
        "source": source,
        "training_role": training_role,
        "must_not_emit_g04": bool(must_not_emit_g04),
        "template_family": template_family,
        "context_flags": context_flags_for_code(code, context_flags),
        "required_context_flags": list(required_context_flags or []),
    }


def load_clear_direct_action_misses(miss_audit_path: Path) -> list[dict[str, Any]]:
    audit = read_json(miss_audit_path)
    records: list[dict[str, Any]] = []
    for row in audit.get("rows", []):
        if row.get("miss_reason") != "clear_direct_action_no_context":
            continue
        expected_route = str(row["expected_route"])
        code = route_code(expected_route)
        records.append(
            record(
                record_id=f"stage0_miss_{row['id']}",
                text=str(row["text"]),
                code=code,
                source="hybrid_miss_audit_clear_direct_action",
                training_role="hard_positive" if code in RISKY_CODES else "positive",
                template_family=str(row.get("template_family") or "legacy_unknown_family"),
                context_flags=row.get("context_flags"),
                required_context_flags=row.get("required_context_flags"),
            )
        )
    return records


def _thresholds_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def load_frontier_first_false_positives(frontier_paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in frontier_paths:
        payload = read_json(path)
        first_fp_threshold = (payload.get("frontier") or {}).get("threshold_at_first_false_positive")
        if not first_fp_threshold:
            continue
        for result in payload.get("results", []):
            if not _thresholds_match(dict(result.get("thresholds") or {}), dict(first_fp_threshold)):
                continue
            for row in result.get("rows", []):
                if row.get("stage0_gate") != "G04" or row.get("expected_stage0_gate") == "G04":
                    continue
                key = (str(row["id"]), str(row["text"]))
                if key in seen:
                    continue
                seen.add(key)
                expected_route = str(row["expected_route"])
                records.append(
                    record(
                        record_id=f"frontier_fp_{path.stem}_{row['id']}",
                        text=str(row["text"]),
                        code=route_code(expected_route),
                        source="frontier_first_false_positive",
                        training_role="hard_negative",
                        template_family=str(row.get("template_family") or "legacy_unknown_family"),
                        must_not_emit_g04=True,
                    )
                )
            break
    return records


def paired_route_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for code, examples in PAIRED_ROUTE_EXAMPLES.items():
        for index, example in enumerate(examples["positive"], start=1):
            records.append(
                record(
                    record_id=f"paired_{code.lower()}_positive_{index:03d}",
                    text=str(example["text"]),
                    code=code,
                    source="paired_route_specific_examples",
                    training_role="hard_positive",
                    template_family=f"paired:{code}:positive:{index}",
                    context_flags=example.get("context_flags"),
                )
            )
        for index, example in enumerate(examples["negative"], start=1):
            negative_code = str(example["code"])
            records.append(
                record(
                    record_id=f"paired_{code.lower()}_negative_{index:03d}",
                    text=str(example["text"]),
                    code=negative_code,
                    source="paired_route_specific_examples",
                    training_role="hard_negative",
                    template_family=f"paired:{code}:negative:{index}",
                    must_not_emit_g04=True,
                    context_flags=example.get("context_flags"),
                )
            )
    return records


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in records:
        key = (str(item["text"]), str(item["code"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def build_stage0_hard_positive_dataset(
    *,
    miss_audit_path: Path = DEFAULT_MISS_AUDIT,
    frontier_paths: list[Path] | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    split_id: str = SPLIT_ID,
) -> dict[str, Any]:
    frontier_paths = frontier_paths or list(DEFAULT_FRONTIER_REPORTS)
    clear_misses = load_clear_direct_action_misses(miss_audit_path)
    frontier_negatives = load_frontier_first_false_positives(frontier_paths)
    paired = paired_route_records()
    all_records = dedupe_records(clear_misses + frontier_negatives + paired)
    splits = router_template_splits.split_cases_by_template_family(all_records, split_id=split_id)
    router_template_splits.assert_no_template_family_overlap(splits)
    train_records = splits["train"] + splits["focused"] + splits["holdout"]
    dev_records = splits["dev"]

    train_path = output_dir / "router_stage0_hard_positive_train_v1.jsonl"
    dev_path = output_dir / "router_stage0_hard_positive_dev_v1.jsonl"
    frontier_path = output_dir / "router_stage0_frontier_hard_negatives_v1.jsonl"
    manifest_path = output_dir / "router_stage0_hard_positive_manifest_v1.json"
    write_jsonl(train_path, train_records)
    write_jsonl(dev_path, dev_records)
    write_jsonl(frontier_path, frontier_negatives)

    route_counts = Counter(record["code"] for record in all_records)
    role_counts = Counter(record["training_role"] for record in all_records)
    source_counts = Counter(record["source"] for record in all_records)
    summary = {
        "dataset": "router_stage0_hard_positive_v1",
        "miss_audit_path": str(miss_audit_path),
        "frontier_paths": [str(path) for path in frontier_paths],
        "output_dir": str(output_dir),
        "split_id": split_id,
        "clear_direct_action_miss_count": len(clear_misses),
        "frontier_first_false_positive_count": len(frontier_negatives),
        "paired_example_count": len(paired),
        "total_count": len(all_records),
        "train_count": len(train_records),
        "dev_count": len(dev_records),
        "route_counts": dict(sorted(route_counts.items())),
        "training_role_counts": dict(sorted(role_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "split_summary": router_template_splits.split_summary(splits),
        "paths": {
            "train": str(train_path),
            "dev": str(dev_path),
            "frontier_hard_negatives": str(frontier_path),
            "manifest": str(manifest_path),
        },
    }
    write_json(manifest_path, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Stage 0 hard-positive recovery data.")
    parser.add_argument("--miss-audit", type=Path, default=DEFAULT_MISS_AUDIT)
    parser.add_argument("--frontier-report", type=Path, action="append")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--split-id", default=SPLIT_ID)
    args = parser.parse_args(argv)
    summary = build_stage0_hard_positive_dataset(
        miss_audit_path=args.miss_audit,
        frontier_paths=args.frontier_report,
        output_dir=args.output_dir,
        split_id=args.split_id,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
