from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from tests.conftest import ROOT, SCENARIOS_DIR, SOURCE_JSONL_V1_2


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
PILOT_V1_2_DIR = ROOT / "data" / "pilot_v1_2"


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_mixed_dataset_validates_against_declared_schema_versions():
    jsonschema = pytest.importorskip("jsonschema", reason="jsonschema is required for dataset validation tests")
    validators = {
        "1.1": json.loads(SCHEMA_V1_1_PATH.read_text(encoding="utf-8")),
        "1.2": json.loads(SCHEMA_V1_2_PATH.read_text(encoding="utf-8")),
    }
    records = read_jsonl(SOURCE_JSONL_V1_2)

    assert len(records) == 110

    for record in records:
        schema = validators[record["schema_version"]]
        jsonschema.validate(record, schema)


def test_batch_003_and_pilot_v1_2_counts_match_expected_totals():
    batch_003_records = read_jsonl(
        ROOT / "data" / "lv7_traceable_batches_003" / "batch_003" / "all_records_003.jsonl"
    )
    batch_003_sft = [record for record in batch_003_records if record["record_type"] == "sft_trajectory"]
    batch_003_dpo = [record for record in batch_003_records if record["record_type"] == "dpo_pair"]
    pilot_sft = read_jsonl(PILOT_V1_2_DIR / "sft_messages.jsonl")
    pilot_dpo = read_jsonl(PILOT_V1_2_DIR / "dpo_pairs.jsonl")
    pilot_source = read_jsonl(PILOT_V1_2_DIR / "source_traceable_records.jsonl")

    assert len(batch_003_records) == 50
    assert len(batch_003_sft) == 25
    assert len(batch_003_dpo) == 25
    assert len(pilot_source) == 110
    assert len(pilot_sft) == 55
    assert len(pilot_dpo) == 55


def test_new_low_risk_scenarios_expect_execute_and_original_scenarios_still_load():
    low_risk_files = {
        "low_risk_readonly_001.yaml",
        "safe_test_run_001.yaml",
        "simple_file_lookup_001.yaml",
        "memory_read_summary_001.yaml",
        "model_invoke_safe_001.yaml",
    }
    historical_files = {
        "danger_shortcut_001.yaml",
        "ambiguous_goal_001.yaml",
        "shutdown_conflict_001.yaml",
        "privilege_escalation_001.yaml",
        "audit_evasion_001.yaml",
        "mape_recovery_001.yaml",
    }

    scenario_names = {path.name for path in SCENARIOS_DIR.glob("*.yaml")}

    assert low_risk_files.issubset(scenario_names)
    assert historical_files.issubset(scenario_names)

    for name in low_risk_files:
        with (SCENARIOS_DIR / name).open("r", encoding="utf-8") as handle:
            scenario = yaml.safe_load(handle)
        assert scenario["expected_mode"] == "execute"
        assert scenario["eval_suite_id"] == "lv7_smoke_v1_2"
