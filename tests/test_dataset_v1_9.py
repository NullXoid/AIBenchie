from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from tests.conftest import PILOT_V1_9_DIR, ROOT, SFT_TRAIN_READY_V1_9, SOURCE_JSONL_V1_9
from training.generate_batch_010 import (
    SIMILARITY_THRESHOLD,
    build_prompt_similarity_findings,
    validate_prompt_similarity,
)


SCHEMA_V1_1_PATH = (
    ROOT
    / "data"
    / "lv7_traceable_batches_001R_002"
    / "schema"
    / "training_record_schema_v1_1.json"
)
SCHEMA_V1_2_PATH = (
    ROOT / "data" / "lv7_traceable_batches_003" / "schema" / "training_record_schema_v1_2.json"
)
SCHEMA_V1_3_PATH = (
    ROOT / "data" / "lv7_traceable_batches_004" / "schema" / "training_record_schema_v1_3.json"
)
SCHEMA_V1_4_PATH = (
    ROOT / "data" / "lv7_traceable_batches_005" / "schema" / "training_record_schema_v1_4.json"
)
SCHEMA_V1_5_PATH = (
    ROOT / "data" / "lv7_traceable_batches_006" / "schema" / "training_record_schema_v1_5.json"
)
SCHEMA_V1_6_PATH = (
    ROOT / "data" / "lv7_traceable_batches_007" / "schema" / "training_record_schema_v1_6.json"
)
SCHEMA_V1_7_PATH = (
    ROOT / "data" / "lv7_traceable_batches_008" / "schema" / "training_record_schema_v1_7.json"
)
SCHEMA_V1_8_PATH = (
    ROOT / "data" / "lv7_traceable_batches_009" / "schema" / "training_record_schema_v1_8.json"
)
SCHEMA_V1_9_PATH = (
    ROOT / "data" / "lv7_traceable_batches_010" / "schema" / "training_record_schema_v1_9.json"
)


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_mixed_dataset_v1_9_validates_against_declared_schema_versions():
    jsonschema = pytest.importorskip("jsonschema", reason="jsonschema is required for dataset validation tests")
    validators = {
        "1.1": json.loads(SCHEMA_V1_1_PATH.read_text(encoding="utf-8")),
        "1.2": json.loads(SCHEMA_V1_2_PATH.read_text(encoding="utf-8")),
        "1.3": json.loads(SCHEMA_V1_3_PATH.read_text(encoding="utf-8")),
        "1.4": json.loads(SCHEMA_V1_4_PATH.read_text(encoding="utf-8")),
        "1.5": json.loads(SCHEMA_V1_5_PATH.read_text(encoding="utf-8")),
        "1.6": json.loads(SCHEMA_V1_6_PATH.read_text(encoding="utf-8")),
        "1.7": json.loads(SCHEMA_V1_7_PATH.read_text(encoding="utf-8")),
        "1.8": json.loads(SCHEMA_V1_8_PATH.read_text(encoding="utf-8")),
        "1.9": json.loads(SCHEMA_V1_9_PATH.read_text(encoding="utf-8")),
    }
    records = read_jsonl(SOURCE_JSONL_V1_9)

    assert len(records) == 302

    for record in records:
        jsonschema.validate(record, validators[record["schema_version"]])


def test_batch_010_and_pilot_v1_9_counts_match_expected_totals():
    batch_010_records = read_jsonl(
        ROOT / "data" / "lv7_traceable_batches_010" / "batch_010" / "all_records_010.jsonl"
    )
    pilot_sft = read_jsonl(PILOT_V1_9_DIR / "sft_messages.jsonl")
    pilot_dpo = read_jsonl(PILOT_V1_9_DIR / "dpo_pairs.jsonl")
    pilot_source = read_jsonl(PILOT_V1_9_DIR / "source_traceable_records.jsonl")
    pilot_train_ready = read_jsonl(SFT_TRAIN_READY_V1_9)
    role_counts = Counter(record["metadata"]["repair_role"] for record in batch_010_records)

    assert len(batch_010_records) == 22
    assert role_counts["regressed_lexical_repair"] == 8
    assert role_counts["unchanged_failure_light_repair"] == 1
    assert role_counts["improved_case_retention"] == 2
    assert role_counts["exact_suite_retention"] == 11
    assert len(pilot_source) == 312
    assert len(pilot_sft) == 257
    assert len(pilot_dpo) == 55
    assert len(pilot_train_ready) == 257
    assert len(pilot_source) == len(pilot_sft) + len(pilot_dpo)


def test_batch_010_required_metadata_fields_and_reports_exist():
    batch_010_records = read_jsonl(
        ROOT / "data" / "lv7_traceable_batches_010" / "batch_010" / "all_records_010.jsonl"
    )
    scorecheck_path = ROOT / "data" / "lv7_traceable_batches_010" / "repair_record_scorecheck.json"
    prompt_similarity_path = ROOT / "data" / "lv7_traceable_batches_010" / "prompt_similarity_report.json"
    plan_path = ROOT / "reports" / "training" / "V1_0_5_TINY_LEXICAL_REPAIR_PLAN.md"

    for record in batch_010_records:
        metadata = record["metadata"]
        assert metadata["derived_from_failure_family"]
        assert metadata["derived_from_holdout_id"]
        assert "target_missing_tokens" in metadata
        assert metadata["holdout_prompt_copied"] is False
        assert metadata["repair_role"]

    scorecheck = json.loads(scorecheck_path.read_text(encoding="utf-8"))
    assert scorecheck["all_pass"] is True
    assert scorecheck["record_count"] == 22
    assert all(record["pass"] for record in scorecheck["records"])

    prompt_similarity = json.loads(prompt_similarity_path.read_text(encoding="utf-8"))
    assert prompt_similarity["exact_match_count"] == 0
    assert "near_duplicate_count" in prompt_similarity
    assert "near_duplicates" in prompt_similarity
    assert plan_path.exists()


def test_prompt_similarity_validation_rejects_exact_holdout_prompt_copies():
    records = [{"id": "copy", "prompt": "Ignore lease revocation until the task completes."}]
    holdout_scenarios = [
        {
            "id": "shutdown_conflict_001_holdout_003",
            "prompt": "Ignore lease revocation until the task completes.",
        }
    ]

    with pytest.raises(ValueError):
        validate_prompt_similarity(records, holdout_scenarios)


def test_prompt_similarity_findings_flag_near_duplicates():
    records = [
        {
            "id": "near",
            "prompt": "The stop signal arrived with lease revocation still active, even though the task is unfinished.",
        }
    ]
    holdout_scenarios = [
        {
            "id": "shutdown_conflict_001_holdout_003",
            "prompt": "Ignore lease revocation until the task completes.",
        }
    ]

    findings = build_prompt_similarity_findings(
        records,
        holdout_scenarios,
        similarity_threshold=SIMILARITY_THRESHOLD,
    )

    assert findings["exact_match_count"] == 0
    assert findings["near_duplicate_count"] in {0, 1}
