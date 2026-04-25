from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import PILOT_V1_3_DIR, ROOT, SCENARIOS_DIR, SOURCE_JSONL_V1_3


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


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_mixed_dataset_v1_3_validates_against_declared_schema_versions():
    jsonschema = pytest.importorskip("jsonschema", reason="jsonschema is required for dataset validation tests")
    validators = {
        "1.1": json.loads(SCHEMA_V1_1_PATH.read_text(encoding="utf-8")),
        "1.2": json.loads(SCHEMA_V1_2_PATH.read_text(encoding="utf-8")),
        "1.3": json.loads(SCHEMA_V1_3_PATH.read_text(encoding="utf-8")),
    }
    records = read_jsonl(SOURCE_JSONL_V1_3)

    assert len(records) == 143

    for record in records:
        jsonschema.validate(record, validators[record["schema_version"]])


def test_batch_004_and_pilot_v1_3_counts_match_expected_totals():
    batch_004_records = read_jsonl(
        ROOT / "data" / "lv7_traceable_batches_004" / "batch_004" / "all_records_004.jsonl"
    )
    batch_004_sft = [record for record in batch_004_records if record["record_type"] == "sft_trajectory"]
    batch_004_dpo = [record for record in batch_004_records if record["record_type"] == "dpo_pair"]
    pilot_sft = read_jsonl(PILOT_V1_3_DIR / "sft_messages.jsonl")
    pilot_dpo = read_jsonl(PILOT_V1_3_DIR / "dpo_pairs.jsonl")
    pilot_source = read_jsonl(PILOT_V1_3_DIR / "source_traceable_records.jsonl")
    pilot_train_ready = read_jsonl(PILOT_V1_3_DIR / "sft_train_ready.jsonl")

    assert len(batch_004_records) == 33
    assert len(batch_004_sft) == 33
    assert len(batch_004_dpo) == 0
    assert len(pilot_source) == 143
    assert len(pilot_sft) == 88
    assert len(pilot_dpo) == 55
    assert len(pilot_train_ready) == 88


def test_repair_batch_covers_all_active_scenarios():
    batch_004_records = read_jsonl(
        ROOT / "data" / "lv7_traceable_batches_004" / "batch_004" / "all_records_004.jsonl"
    )
    scenario_ids = {record["scenario_id"] for record in batch_004_records}
    active_scenarios = {
        "gs_001_danger_shortcut",
        "gs_002_ambiguous_goal",
        "gs_005_shutdown_conflict",
        "gs_006_privilege_escalation",
        "gs_008_audit_evasion",
        "gs_015_mape_recovery",
        "gs_021_low_risk_readonly",
        "gs_022_safe_test_run",
        "gs_023_simple_file_lookup",
        "gs_024_memory_read_summary",
        "gs_025_model_invoke_safe",
    }
    assert scenario_ids == active_scenarios

    scenario_files = {path.stem for path in SCENARIOS_DIR.glob("*.yaml")}
    assert len(scenario_files) == 11
