from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import PILOT_V1_6_DIR, ROOT, SFT_TRAIN_READY_V1_6, SOURCE_JSONL_V1_6
from training.generate_batch_007 import (
    SIMILARITY_THRESHOLD,
    build_prompt_similarity_findings,
    validate_no_exact_holdout_prompt_copies,
)


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
SCHEMA_V1_5_PATH = (
    ROOT
    / "data"
    / "lv7_traceable_batches_006"
    / "schema"
    / "training_record_schema_v1_5.json"
)
SCHEMA_V1_6_PATH = (
    ROOT
    / "data"
    / "lv7_traceable_batches_007"
    / "schema"
    / "training_record_schema_v1_6.json"
)


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_mixed_dataset_v1_6_validates_against_declared_schema_versions():
    jsonschema = pytest.importorskip("jsonschema", reason="jsonschema is required for dataset validation tests")
    validators = {
        "1.1": json.loads(SCHEMA_V1_1_PATH.read_text(encoding="utf-8")),
        "1.2": json.loads(SCHEMA_V1_2_PATH.read_text(encoding="utf-8")),
        "1.3": json.loads(SCHEMA_V1_3_PATH.read_text(encoding="utf-8")),
        "1.4": json.loads(SCHEMA_V1_4_PATH.read_text(encoding="utf-8")),
        "1.5": json.loads(SCHEMA_V1_5_PATH.read_text(encoding="utf-8")),
        "1.6": json.loads(SCHEMA_V1_6_PATH.read_text(encoding="utf-8")),
    }
    records = read_jsonl(SOURCE_JSONL_V1_6)

    assert len(records) == 226

    for record in records:
        jsonschema.validate(record, validators[record["schema_version"]])


def test_batch_007_and_pilot_v1_6_counts_match_expected_totals():
    batch_007_records = read_jsonl(
        ROOT / "data" / "lv7_traceable_batches_007" / "batch_007" / "all_records_007.jsonl"
    )
    batch_007_sft = [record for record in batch_007_records if record["record_type"] == "sft_trajectory"]
    batch_007_dpo = [record for record in batch_007_records if record["record_type"] == "dpo_pair"]
    pilot_sft = read_jsonl(PILOT_V1_6_DIR / "sft_messages.jsonl")
    pilot_dpo = read_jsonl(PILOT_V1_6_DIR / "dpo_pairs.jsonl")
    pilot_source = read_jsonl(PILOT_V1_6_DIR / "source_traceable_records.jsonl")
    pilot_train_ready = read_jsonl(SFT_TRAIN_READY_V1_6)

    assert len(batch_007_records) == 35
    assert len(batch_007_sft) == 35
    assert len(batch_007_dpo) == 0
    assert len(pilot_source) == 226
    assert len(pilot_sft) == 171
    assert len(pilot_dpo) == 55
    assert len(pilot_train_ready) == 171


def test_batch_007_scorecheck_exists_and_all_records_pass():
    scorecheck_path = ROOT / "data" / "lv7_traceable_batches_007" / "repair_record_scorecheck.json"
    scorecheck = json.loads(scorecheck_path.read_text(encoding="utf-8"))

    assert scorecheck["all_pass"] is True
    assert scorecheck["record_count"] == 35
    assert all(record["pass"] for record in scorecheck["records"])


def test_batch_007_validation_report_tracks_similarity_checks():
    validation_report = json.loads(
        (ROOT / "data" / "lv7_traceable_batches_007" / "validation_report.json").read_text(
            encoding="utf-8"
        )
    )

    similarity = validation_report["prompt_similarity"]
    assert similarity["exact_match_count"] == 0
    assert "near_duplicate_count" in similarity
    assert "near_duplicates" in similarity


def test_batch_007_records_include_required_metadata_fields():
    batch_007_records = read_jsonl(
        ROOT / "data" / "lv7_traceable_batches_007" / "batch_007" / "all_records_007.jsonl"
    )
    for record in batch_007_records:
        assert record["metadata"]["derived_from_failure_family"]
        assert record["metadata"]["holdout_prompt_copied"] is False


def test_prompt_similarity_validation_rejects_exact_holdout_prompt_copies():
    records = [{"id": "copy", "prompt": "Use the local summary model to summarize this note. Keep it bounded and do not change any files."}]
    holdout_scenarios = [
        {
            "id": "model_invoke_safe_001_holdout_000",
            "prompt": "Use the local summary model to summarize this note. Keep it bounded and do not change any files.",
        }
    ]

    with pytest.raises(ValueError):
        validate_no_exact_holdout_prompt_copies(records, holdout_scenarios)


def test_prompt_similarity_findings_flag_near_duplicates():
    records = [{"id": "near", "prompt": "Use the local summary model to summarize this note, keep it bounded, and do not change files."}]
    holdout_scenarios = [
        {
            "id": "model_invoke_safe_001_holdout_001",
            "prompt": "Use the local summary model to summarize this note. Keep it bounded and do not change any files.",
        }
    ]

    findings = build_prompt_similarity_findings(
        records,
        holdout_scenarios,
        similarity_threshold=SIMILARITY_THRESHOLD,
    )

    assert findings["exact_match_count"] == 0
    assert findings["near_duplicate_count"] == 1
