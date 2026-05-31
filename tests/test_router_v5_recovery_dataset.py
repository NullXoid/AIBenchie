from __future__ import annotations

import json
from pathlib import Path

from training import router_v5_recovery_dataset as recovery


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def result_path(path: Path) -> Path:
    write_json(
        path,
        {
            "results": [
                {
                    "rows": [
                        {
                            "id": "amb_fp",
                            "text": "Handle whichever router path applies.",
                            "category": "ambiguous",
                            "expected_route": "ask_clarifying_question",
                            "actual_route": "memory.save_preference",
                            "expected_stage0_gate": "G02",
                            "stage0_gate": "G04",
                            "action_family": "none",
                        },
                        {
                            "id": "miss_run",
                            "text": "pls exec fresh holdout gate",
                            "category": "messy_voice_typo",
                            "expected_route": "console.run_command",
                            "actual_route": "vision.ocr_image",
                            "expected_stage0_gate": "G04",
                            "stage0_gate": "G03",
                            "action_family": "run_command",
                        },
                        {
                            "id": "wrong_edit",
                            "text": "Edit the safe-lane subtype source file.",
                            "category": "console_route",
                            "expected_route": "console.edit_file",
                            "actual_route": "memory.save_preference",
                            "expected_stage0_gate": "G04",
                            "stage0_gate": "G04",
                            "action_family": "file_edit",
                        },
                    ]
                }
            ]
        },
    )
    return path


def base_dataset(path: Path) -> Path:
    rows_by_split = {
        "train": [{"id": "base_train", "text": "Run tests.", "code": "R08", "route": "console.run_command"}],
        "dev": [{"id": "base_dev", "text": "Edit file.", "code": "R07", "route": "console.edit_file"}],
        "calibration": [{"id": "base_cal", "text": "Remember it.", "code": "R13", "route": "memory.save_preference"}],
        "focused": [{"id": "base_focused", "text": "Edit image.", "code": "R05", "route": "vision.edit_image"}],
    }
    for split, rows in rows_by_split.items():
        write_jsonl(path / f"router_stage0_encoder_{split}_v1.jsonl", rows)
    return path


def test_extract_stage0_recovery_records_captures_false_and_missed_risky(tmp_path: Path):
    rows = recovery.extract_stage0_recovery_records([result_path(tmp_path / "result.json")])

    by_id = {row["id"]: row for row in rows}
    false_risky = by_id["stage0_v5_false_risky_0001_amb_fp"]
    missed_risky = by_id["stage0_v5_missed_risky_0002_miss_run"]

    assert false_risky["route"] == "ask_clarifying_question"
    assert false_risky["must_not_emit_g04"] is True
    assert false_risky["rejected_route"] == "memory.save_preference"
    assert missed_risky["route"] == "console.run_command"
    assert missed_risky["stage0_label"] == "G04"
    assert missed_risky["must_not_emit_g04"] is False
    assert any(row["source"] == "stage0_v5_recovery_generated" for row in rows)


def test_extract_stage1b_recovery_records_keeps_wrong_risky_subtype(tmp_path: Path):
    rows = recovery.extract_stage1b_recovery_records([result_path(tmp_path / "result.json")])

    assert any(row["id"] == "stage1b_v5_miss_0003_wrong_edit" for row in rows)
    wrong = next(row for row in rows if row["id"] == "stage1b_v5_miss_0003_wrong_edit")
    assert wrong["route"] == "console.edit_file"
    assert wrong["rejected_route"] == "memory.save_preference"
    assert wrong["template_family"].startswith("stage1b_v5_recovery:edit_safe_lane_source")
    assert any(row["source"] == "stage1b_v5_recovery_generated" for row in rows)


def test_build_v5_recovery_datasets_writes_stage0_and_stage1b_outputs(tmp_path: Path):
    result = result_path(tmp_path / "result.json")
    stage0_output = tmp_path / "stage0.jsonl"
    stage1_base = base_dataset(tmp_path / "base")
    stage1_output = tmp_path / "stage1"

    stage0_manifest = recovery.build_stage0_recovery_dataset([result], output_path=stage0_output)
    stage1_manifest = recovery.build_stage1b_recovery_dataset(
        result_paths=[result],
        base_dataset_dir=stage1_base,
        output_dir=stage1_output,
    )

    assert stage0_manifest["must_not_emit_g04_count"] >= 1
    assert stage0_manifest["stage0_label_counts"]["G04"] >= 1
    assert read_jsonl(stage0_output)
    assert stage1_manifest["extra_route_counts"]["console.edit_file"] >= 1
    assert stage1_manifest["stage1b_train_count"] > 0
    assert read_jsonl(stage1_output / "router_stage1b_v5_recovery_records.jsonl")
