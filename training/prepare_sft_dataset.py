from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "pilot_v1_6" / "sft_messages.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "pilot_v1_6" / "sft_train_ready.jsonl"


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


def render_messages_as_text(messages: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for message in messages:
        role = str(message["role"]).strip()
        content = str(message["content"]).strip()
        blocks.append(f"{role}:\n{content}")
    return "\n\n".join(blocks).strip()


def build_train_ready_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "scenario_id": record["scenario_id"],
        "messages": record["messages"],
        "metadata": record["metadata"],
        "text": render_messages_as_text(record["messages"]),
    }


def prepare_sft_dataset(input_path: Path, output_path: Path) -> dict[str, Any]:
    source_records = load_jsonl(input_path)
    prepared_records = [build_train_ready_record(record) for record in source_records]
    write_jsonl(output_path, prepared_records)
    return {
        "input_path": str(input_path),
        "output_path": str(output_path),
        "count": len(prepared_records),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare inspectable LV7 SFT smoke records for QLoRA training."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    summary = prepare_sft_dataset(args.input, args.output)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
