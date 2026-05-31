from __future__ import annotations

import json
from pathlib import Path

from training import router_direct_action_boundaries_dataset as builder


def write_result(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps({"results": [{"rows": rows}]}), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_extract_false_direct_records_keeps_actual_risky_rejection(tmp_path: Path):
    path = tmp_path / "holdout_v2.json"
    write_result(
        path,
        [
            {
                "id": "image_bad",
                "text": "Edit this image.",
                "expected_output": "R05",
                "expected_route": "vision.edit_image",
                "actual_route": "console.edit_file",
                "category": "media_route",
                "action_family": "media_edit",
            },
            {
                "id": "missed_job",
                "text": "Start job.",
                "expected_output": "R10",
                "expected_route": "agent.start_job",
                "actual_route": "answer.question",
                "category": "direct_action",
                "action_family": "job",
            },
        ],
    )

    records = builder.extract_false_direct_records(path)

    assert len(records) == 1
    assert records[0]["chosen_route"] == "vision.edit_image"
    assert records[0]["rejected_route"] == "console.edit_file"
    assert records[0]["category"] == "vision_edit_not_file_edit"


def test_build_direct_action_boundaries_dataset_outputs_balanced_artifacts(tmp_path: Path):
    false_r08 = tmp_path / "false_r08.json"
    holdout_v2 = tmp_path / "holdout_v2.json"
    output_dir = tmp_path / "router_direct_action_boundaries_v2"
    write_result(
        false_r08,
        [
            {
                "id": "bad_run_question",
                "text": "Explain run command safety.",
                "expected_output": "R01",
                "expected_route": "answer.question",
                "actual_route": "console.run_command",
                "category": "answer_question",
                "action_family": "none",
            },
            {
                "id": "bad_run_edit",
                "text": "Apply the patch.",
                "expected_output": "R07",
                "expected_route": "console.edit_file",
                "actual_route": "console.run_command",
                "category": "console_edit_file",
                "action_family": "file_edit",
            },
            {
                "id": "bad_run_search",
                "text": "Search the repo.",
                "expected_output": "R12",
                "expected_route": "file.search",
                "actual_route": "console.run_command",
                "category": "file_search",
                "action_family": "lookup",
            },
        ],
    )
    write_result(
        holdout_v2,
        [
            {
                "id": "bad_file_edit",
                "text": "Edit this image.",
                "expected_output": "R05",
                "expected_route": "vision.edit_image",
                "actual_route": "console.edit_file",
                "category": "media_route",
                "action_family": "media_edit",
            }
        ],
    )

    summary = builder.build_router_direct_action_boundaries_dataset(
        false_r08_result_path=false_r08,
        holdout_v2_result_path=holdout_v2,
        output_dir=output_dir,
        ollama_show_text="Model\n  quantization        Q4_K_M\n",
    )

    train = read_jsonl(output_dir / "router_lora_train_v2.jsonl")
    dev = read_jsonl(output_dir / "router_lora_dev_direct_action_boundaries_v2.jsonl")
    dpo = read_jsonl(output_dir / "router_lora_dpo_pairs_v2.jsonl")
    holdout = read_jsonl(output_dir / "router_holdout_1000_v3.jsonl")
    categories = {record["category"] for record in dpo}

    assert summary["false_r08_count"] == 3
    assert summary["false_direct_count"] == 1
    assert summary["balanced_positive_count"] == 1100
    assert len(train) == 1104
    assert len(dev) == 500
    assert len(dpo) == 1104
    assert len(holdout) == 1000
    assert summary["chosen_route_counts"]["vision.edit_image"] == 101
    assert "vision_edit_not_file_edit" in categories
    assert "file_edit_not_run_command" in categories
    assert "file_search_not_run_command" in categories
    assert "preference_talk_not_memory_write" in categories
    assert "explicit_memory_save" in categories
