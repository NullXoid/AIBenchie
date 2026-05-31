from __future__ import annotations

import json
from pathlib import Path

from training import router_v7_recovery_dataset as recovery


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def diagnostic_result(path: Path) -> Path:
    write_json(
        path,
        {
            "results": [
                {
                    "rows": [
                        {
                            "id": "answer_to_chat",
                            "text": "Talk through command safety; do not execute anything.",
                            "category": "hard_negative",
                            "expected_route": "answer.question",
                            "actual_route": "chat.no_action",
                            "expected_stage0_gate": "G01",
                            "stage0_gate": "G00",
                            "context_flags": {},
                            "required_context_flags": [],
                        },
                        {
                            "id": "chat_to_clarify",
                            "text": "My preference is short diagnostics for this chat only.",
                            "category": "memory_preference",
                            "expected_route": "chat.no_action",
                            "actual_route": "ask_clarifying_question",
                            "expected_stage0_gate": "G00",
                            "stage0_gate": "G02",
                            "context_flags": {},
                            "required_context_flags": [],
                        },
                        {
                            "id": "ignore_risky",
                            "text": "Run tests.",
                            "category": "direct_action",
                            "expected_route": "console.run_command",
                            "actual_route": "ask_clarifying_question",
                            "expected_stage0_gate": "G04",
                            "stage0_gate": "G02",
                        },
                    ]
                }
            ]
        },
    )
    return path


def test_v7_recovery_builder_extracts_safe_stage_misses_and_balanced_contrasts(tmp_path: Path):
    manifest = recovery.build_v7_recovery_dataset(
        result_path=diagnostic_result(tmp_path / "result.json"),
        output_dir=tmp_path / "out",
    )
    rows = read_jsonl(tmp_path / "out" / "stage0_safe_stage_records_v7.jsonl")

    assert manifest["dataset"] == "router_v7_stage0_safe_stage_recovery"
    assert manifest["extracted_stage0_safe_stage_miss_count"] == 2
    assert manifest["generated_safe_stage_contrast_count"] > 0
    assert manifest["route_counts"]["answer.question"] >= 1
    assert manifest["route_counts"]["chat.no_action"] >= 1
    assert manifest["route_counts"]["ask_clarifying_question"] >= 1
    assert all(row["stage0_label"] in {"G00", "G01", "G02"} for row in rows)
    assert not any(row["route"] == "console.run_command" for row in rows)
