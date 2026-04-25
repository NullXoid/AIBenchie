from __future__ import annotations

import argparse
import copy
import json
import shutil
from pathlib import Path
from typing import Any


CANONICAL_SOURCES = {
    "1.1": "NullXoid LV7 Schema v1.1 Design Note, 2026-04-19",
    "1.2": "NullXoid LV7 Schema v1.2 Design Note, 2026-04-19",
    "1.3": "NullXoid LV7 Schema v1.3 Design Note, 2026-04-19",
    "1.4": "NullXoid LV7 Schema v1.4 Design Note, 2026-04-19",
    "1.5": "NullXoid LV7 Schema v1.5 Design Note, 2026-04-19",
    "1.6": "NullXoid LV7 Schema v1.6 Design Note, 2026-04-19",
    "1.7": "NullXoid LV7 Schema v1.7 Design Note, 2026-04-19",
    "1.8": "NullXoid LV7 Schema v1.8 Design Note, 2026-04-19",
    "1.9": "NullXoid LV7 Schema v1.9 Design Note, 2026-04-20",
}
CANONICAL_SOURCE = CANONICAL_SOURCES["1.1"]


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def sanitize_text(value: Any) -> str:
    return " ".join(str(value).split())


def render_policy_rationale(policy_rationale: dict[str, Any], response: str) -> str:
    fields = {
        "mode": sanitize_text(policy_rationale["mode"]),
        "risk_assessment": sanitize_text(policy_rationale["risk_assessment"]),
        "authority_boundary": sanitize_text(policy_rationale["authority_boundary"]),
        "safe_next_move": sanitize_text(policy_rationale["safe_next_move"]),
    }
    response_text = response.strip()
    return (
        "policy_rationale:\n"
        f"  mode: {fields['mode']}\n"
        f"  risk_assessment: {fields['risk_assessment']}\n"
        f"  authority_boundary: {fields['authority_boundary']}\n"
        f"  safe_next_move: {fields['safe_next_move']}\n"
        "\n"
        "response:\n"
        f"{response_text}"
    )


def build_metadata(record: dict[str, Any]) -> dict[str, Any]:
    metadata = copy.deepcopy(record["metadata"])
    canonical_source = CANONICAL_SOURCES.get(record["schema_version"], CANONICAL_SOURCES["1.1"])
    original_source = metadata.get("source", "")
    if original_source != canonical_source:
        metadata["source_original"] = original_source
    metadata["source"] = canonical_source
    metadata["schema_version"] = record["schema_version"]
    metadata["scenario_name"] = record["scenario_name"]
    metadata["risk_level"] = record["risk_level"]
    metadata["tool_scope_context"] = copy.deepcopy(record["tool_scope_context"])
    metadata["policy_rationale"] = copy.deepcopy(record["policy_rationale"])
    metadata["traceability"] = copy.deepcopy(record["traceability"])
    return metadata


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_sft_record(record: dict[str, Any]) -> dict[str, Any]:
    assistant_content = render_policy_rationale(
        record["policy_rationale"], record["ideal_behavior"]["response"]
    )
    return {
        "id": record["id"],
        "scenario_id": record["scenario_id"],
        "messages": [
            {"role": "user", "content": record["prompt"]},
            {"role": "assistant", "content": assistant_content},
        ],
        "metadata": build_metadata(record),
    }


def build_dpo_record(
    record: dict[str, Any], include_policy_rationale_in_chosen: bool
) -> dict[str, Any]:
    chosen = record["chosen"]
    if include_policy_rationale_in_chosen:
        chosen = render_policy_rationale(record["policy_rationale"], chosen)

    return {
        "id": record["id"],
        "scenario_id": record["scenario_id"],
        "prompt": record["prompt"],
        "chosen": chosen,
        "rejected": record["rejected"],
        "metadata": build_metadata(record),
    }


def convert_records(
    input_path: Path, out_dir: Path, include_policy_rationale_in_chosen: bool = True
) -> dict[str, Any]:
    records = load_jsonl(input_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    source_copy = out_dir / "source_traceable_records.jsonl"
    shutil.copyfile(input_path, source_copy)

    sft_records = [
        build_sft_record(record)
        for record in records
        if record["record_type"] == "sft_trajectory"
    ]
    dpo_records = [
        build_dpo_record(record, include_policy_rationale_in_chosen)
        for record in records
        if record["record_type"] == "dpo_pair"
    ]

    write_jsonl(out_dir / "sft_messages.jsonl", sft_records)
    write_jsonl(out_dir / "dpo_pairs.jsonl", dpo_records)

    return {
        "input_path": str(input_path),
        "source_copy": str(source_copy),
        "sft_count": len(sft_records),
        "dpo_count": len(dpo_records),
        "include_policy_rationale_in_chosen": include_policy_rationale_in_chosen,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert LV7 traceable records into pilot SFT and DPO files."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input JSONL path.")
    parser.add_argument(
        "--out-dir",
        required=True,
        type=Path,
        help="Output directory for pilot JSONL files.",
    )
    parser.add_argument(
        "--include-policy-rationale-in-chosen",
        default=True,
        type=parse_bool,
        help="Whether DPO chosen responses should embed the rendered policy rationale.",
    )
    args = parser.parse_args(argv)

    summary = convert_records(
        input_path=args.input,
        out_dir=args.out_dir,
        include_policy_rationale_in_chosen=args.include_policy_rationale_in_chosen,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
