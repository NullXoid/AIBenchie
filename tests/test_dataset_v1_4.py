from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import PILOT_V1_4_DIR, ROOT, SOURCE_JSONL_V1_4


SCHEMA_V1_1_PATH = (
    ROOT
    / "data"
    / "lv7_traceable_batches_001R_002"
    / "schema"
    / "training_record_schema_v1_1.json"
)
SCHEMA_V1_2_PATH = (
    ROOT
    / "data"
    / "lv7_traceable_batches_003"
    / "schema"
    / "training_record_schema_v1_2.json"
)
SCHEMA_V1_3_PATH = (
    ROOT
    / "data"
    / "lv7_traceable_batches_004"
    / "schema"
    / "training_record_schema_v1_3.json"
)
SCHEMA_V1_4_PATH = (
    ROOT
    / "data"
    / "lv7_traceable_batches_005"
    / "schema"
    / "training_record_schema_v1_4.json"
)


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_mixed_dataset_v1_4_validates_against_declared_schema_versions():
    jsonschema = pytest.importorskip("jsonschema", reason="jsonschema is required for dataset validation tests")
    validators = {
        "1.1": json.loads(SCHEMA_V1_1_PATH.read_text(encoding="utf-8")),
        "1.2": json.loads(SCHEMA_V1_2_PATH.read_text(encoding="utf-8")),
        "1.3": json.loads(SCHEMA_V1_3_PATH.read_text(encoding="utf-8")),
        "1.4": json.loads(SCHEMA_V1_4_PATH.read_text(encoding="utf-8")),
    }
    records = read_jsonl(SOURCE_JSONL_V1_4)

    assert len(records) == 172

    for record in records:
        jsonschema.validate(record, validators[record["schema_version"]])


def test_batch_005_and_pilot_v1_4_counts_match_expected_totals():
    batch_005_records = read_jsonl(
        ROOT / "data" / "lv7_traceable_batches_005" / "batch_005" / "all_records_005.jsonl"
    )
    batch_005_sft = [record for record in batch_005_records if record["record_type"] == "sft_trajectory"]
    batch_005_dpo = [record for record in batch_005_records if record["record_type"] == "dpo_pair"]
    pilot_sft = read_jsonl(PILOT_V1_4_DIR / "sft_messages.jsonl")
    pilot_dpo = read_jsonl(PILOT_V1_4_DIR / "dpo_pairs.jsonl")
    pilot_source = read_jsonl(PILOT_V1_4_DIR / "source_traceable_records.jsonl")
    pilot_train_ready = read_jsonl(PILOT_V1_4_DIR / "sft_train_ready.jsonl")

    assert len(batch_005_records) == 29
    assert len(batch_005_sft) == 29
    assert len(batch_005_dpo) == 0
    assert len(pilot_source) == 172
    assert len(pilot_sft) == 117
    assert len(pilot_dpo) == 55
    assert len(pilot_train_ready) == 117


def test_batch_005_scorecheck_exists_and_all_records_pass():
    scorecheck_path = ROOT / "data" / "lv7_traceable_batches_005" / "repair_record_scorecheck.json"
    scorecheck = json.loads(scorecheck_path.read_text(encoding="utf-8"))

    assert scorecheck["all_pass"] is True
    assert scorecheck["record_count"] == 29
    assert all(record["pass"] for record in scorecheck["records"])
