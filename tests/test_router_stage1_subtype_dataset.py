from __future__ import annotations

import json
from pathlib import Path

from training import router_stage1_subtype_dataset as subtype_dataset


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


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
                            "id": "risky_wrong",
                            "text": "pls run direct action gate now v3 case 951",
                            "category": "console_run_command",
                            "expected_route": "console.run_command",
                            "actual_route": "console.edit_file",
                            "expected_stage0_gate": "G04",
                            "context_flags": {},
                            "required_context_flags": [],
                        },
                        {
                            "id": "safe_wrong",
                            "text": "Look online for the backend docs.",
                            "category": "web_lookup",
                            "expected_route": "web.lookup",
                            "actual_route": "file.search",
                            "expected_stage0_gate": "G03",
                            "context_flags": {},
                            "required_context_flags": [],
                        },
                        {
                            "id": "correct",
                            "text": "Run tests now.",
                            "category": "console_run_command",
                            "expected_route": "console.run_command",
                            "actual_route": "console.run_command",
                            "expected_stage0_gate": "G04",
                        },
                        {
                            "id": "not_stage1",
                            "text": "Explain command safety.",
                            "category": "answer_question",
                            "expected_route": "answer.question",
                            "actual_route": "console.run_command",
                            "expected_stage0_gate": "G01",
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
        "dev": [{"id": "base_dev", "text": "Search files.", "code": "R12", "route": "file.search"}],
        "calibration": [{"id": "base_cal", "text": "Describe image.", "code": "R03", "route": "vision.describe_image"}],
        "focused": [{"id": "base_focused", "text": "Edit file.", "code": "R07", "route": "console.edit_file"}],
    }
    for split, rows in rows_by_split.items():
        write_jsonl(path / f"router_stage0_encoder_{split}_v1.jsonl", rows)
    return path


def test_extract_subtype_miss_records_keeps_only_allowed_family_misses(tmp_path: Path):
    records = subtype_dataset.extract_subtype_miss_records([diagnostic_result(tmp_path / "result.json")])

    assert [record["id"] for record in records] == [
        "stage1_v3_miss_0001_risky_wrong",
        "stage1_v3_miss_0002_safe_wrong",
    ]
    assert records[0]["route"] == "console.run_command"
    assert records[0]["rejected_route"] == "console.edit_file"
    assert records[0]["rejected_code"] == "R07"
    assert records[0]["template_family"].startswith("stage1_v3:messy_run_direct_action_gate")
    assert records[0]["action_family"] == "run_command"
    assert records[1]["route"] == "web.lookup"
    assert records[1]["rejected_route"] == "file.search"
    assert records[1]["action_family"] == "web_lookup"


def test_build_stage1_subtype_dataset_writes_manifest_and_augmented_splits(tmp_path: Path):
    result_path = diagnostic_result(tmp_path / "result.json")
    base_dir = base_dataset(tmp_path / "base")
    output_dir = tmp_path / "out"

    manifest = subtype_dataset.build_stage1_subtype_dataset(
        result_paths=[result_path],
        base_dataset_dir=base_dir,
        output_dir=output_dir,
    )

    assert manifest["dataset"] == "router_stage1_subtype_v2"
    assert manifest["extracted_subtype_miss_count"] == 2
    assert manifest["generated_subtype_count"] > 0
    assert manifest["extra_route_counts"]["console.run_command"] >= 1
    assert manifest["extra_route_counts"]["web.lookup"] >= 1
    assert manifest["stage1a_train_count"] > 0
    assert manifest["stage1b_train_count"] > 0
    assert Path(manifest["paths"]["manifest"]).exists()

    train_rows = read_jsonl(output_dir / "router_stage0_encoder_train_v1.jsonl")
    assert any(row.get("source") == "router_holdout_1000_v3_diagnostic_subtype_miss" for row in train_rows)
    assert any(row.get("source") == "stage1_subtype_generated_v2" for row in train_rows)
    assert read_jsonl(output_dir / "router_stage1_subtype_hard_records_v2.jsonl")


def safe_lane_result(path: Path) -> Path:
    write_json(
        path,
        {
            "results": [
                {
                    "rows": [
                        {
                            "id": "answer_wrong",
                            "text": "Give me an explanation of run command safety.",
                            "category": "answer_question",
                            "expected_route": "answer.question",
                            "actual_route": "chat.no_action",
                            "expected_stage0_gate": "G01",
                            "stage0_gate": "G01",
                            "context_flags": {},
                            "required_context_flags": [],
                        },
                        {
                            "id": "file_wrong",
                            "text": "Read the local hybrid candidate manifest.",
                            "category": "web_file_data",
                            "expected_route": "file.search",
                            "actual_route": "web.lookup",
                            "expected_stage0_gate": "G03",
                            "stage0_gate": "G03",
                            "context_flags": {},
                            "required_context_flags": [],
                        },
                        {
                            "id": "unsafe_skip",
                            "text": "Run tests.",
                            "category": "console_run_command",
                            "expected_route": "console.run_command",
                            "actual_route": "console.edit_file",
                            "expected_stage0_gate": "G04",
                            "stage0_gate": "G04",
                        },
                    ]
                }
            ]
        },
    )
    return path


def multi_set_safe_lane_result(path: Path) -> Path:
    write_json(
        path,
        {
            "sets": {
                "v6": {
                    "rows": [
                        {
                            "id": "answer_wrong",
                            "text": "Explain how to reason about run command safety.",
                            "category": "answer_question",
                            "expected_route": "answer.question",
                            "actual_route": "chat.no_action",
                            "expected_stage0_gate": "G01",
                            "stage0_gate": "G01",
                            "context_flags": {},
                            "required_context_flags": [],
                        }
                    ]
                }
            }
        },
    )
    return path


def test_extract_safe_lane_miss_records_excludes_risky_misses(tmp_path: Path):
    records = subtype_dataset.extract_safe_lane_miss_records([safe_lane_result(tmp_path / "safe.json")])

    assert [record["id"] for record in records] == [
        "stage1_v4_safe_miss_0001_answer_wrong",
        "stage1_v4_safe_miss_0002_file_wrong",
    ]
    assert records[0]["route"] == "answer.question"
    assert records[0]["rejected_route"] == "chat.no_action"
    assert records[0]["template_family"].startswith("stage1_v4_safe_lane:answer_question")
    assert records[1]["route"] == "file.search"
    assert records[1]["rejected_route"] == "web.lookup"


def test_extract_safe_lane_miss_records_reads_multi_set_probe_payload(tmp_path: Path):
    records = subtype_dataset.extract_safe_lane_miss_records([multi_set_safe_lane_result(tmp_path / "probe.json")])

    assert len(records) == 1
    assert records[0]["route"] == "answer.question"
    assert records[0]["rejected_route"] == "chat.no_action"


def test_extract_expected_safe_stage_records_keeps_correct_and_wrong_safe_stage_rows(tmp_path: Path):
    records = subtype_dataset.extract_expected_safe_stage_records([safe_lane_result(tmp_path / "safe_stage.json")])

    assert [record["route"] for record in records] == ["answer.question"]
    assert records[0]["training_role"] == "stage1_safe_stage_expected_balance"
    assert records[0]["rejected_route"] == "chat.no_action"


def test_build_balanced_safe_stage_recovery_dataset_adds_expected_safe_stage_rows(tmp_path: Path):
    result_path = safe_lane_result(tmp_path / "safe_balanced.json")
    base_dir = base_dataset(tmp_path / "base")
    output_dir = tmp_path / "out_balanced"

    manifest = subtype_dataset.build_stage1_balanced_safe_stage_recovery_dataset(
        result_paths=[result_path],
        base_dataset_dir=base_dir,
        output_dir=output_dir,
    )

    assert manifest["dataset"] == "router_stage1_balanced_safe_stage_recovery"
    assert manifest["expected_safe_stage_count"] == 1
    assert manifest["extra_route_counts"]["answer.question"] >= 1
    assert manifest["extra_training_role_counts"]["stage1_safe_stage_expected_balance"] == 1
    assert manifest["stage1c_train_count"] > 0
    assert Path(manifest["paths"]["manifest"]).name == "router_stage1_subtype_manifest_v9.json"


def test_build_safe_lane_cleanup_dataset_adds_stage1a_and_stage1c_records(tmp_path: Path):
    result_path = safe_lane_result(tmp_path / "safe.json")
    base_dir = base_dataset(tmp_path / "base")
    output_dir = tmp_path / "out"

    manifest = subtype_dataset.build_stage1_safe_lane_cleanup_dataset(
        result_paths=[result_path],
        base_dataset_dir=base_dir,
        output_dir=output_dir,
    )

    assert manifest["dataset"] == "router_stage1_subtype_v3_safe_lane_cleanup"
    assert manifest["extracted_safe_lane_miss_count"] == 2
    assert manifest["generated_safe_lane_count"] > 0
    assert manifest["extra_route_counts"]["answer.question"] >= 1
    assert manifest["extra_route_counts"]["file.search"] >= 1
    assert manifest["stage1a_train_count"] > 0
    assert manifest["stage1c_train_count"] > 0

    train_rows = read_jsonl(output_dir / "router_stage0_encoder_train_v1.jsonl")
    assert any(row.get("source") == "router_holdout_1000_v4_diagnostic_safe_lane_miss" for row in train_rows)
    assert any(row.get("source") == "stage1_safe_lane_cleanup_generated_v3" for row in train_rows)

    dev_rows = read_jsonl(output_dir / "router_stage0_encoder_dev_v1.jsonl")
    assert any(row["route"] == "answer.question" and row["id"].endswith("_dev") for row in dev_rows)


def test_build_v6_safe_stage_recovery_dataset_writes_v5_manifest(tmp_path: Path):
    result_path = safe_lane_result(tmp_path / "safe_v6.json")
    base_dir = base_dataset(tmp_path / "base")
    output_dir = tmp_path / "out_v5"

    manifest = subtype_dataset.build_stage1_v6_safe_stage_recovery_dataset(
        result_paths=[result_path],
        base_dataset_dir=base_dir,
        output_dir=output_dir,
    )

    assert manifest["dataset"] == "router_stage1_safe_stage_v6_recovery"
    assert manifest["generated_safe_stage_balance_count"] > 0
    assert manifest["extra_route_counts"]["chat.no_action"] >= 1
    assert manifest["extra_route_counts"]["answer.question"] >= 1
    assert manifest["extra_route_counts"]["ask_clarifying_question"] >= 1
    assert Path(manifest["paths"]["manifest"]).name == "router_stage1_subtype_manifest_v5.json"
    assert Path(manifest["paths"]["manifest"]).exists()
