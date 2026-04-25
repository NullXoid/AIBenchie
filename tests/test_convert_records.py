from __future__ import annotations

import json

from tests.conftest import (
    SOURCE_JSONL,
    SOURCE_JSONL_V1_2,
    SOURCE_JSONL_V1_3,
    SOURCE_JSONL_V1_4,
    SOURCE_JSONL_V1_5,
    SOURCE_JSONL_V1_6,
    SOURCE_JSONL_V1_7,
)
from training.convert_records import CANONICAL_SOURCE, CANONICAL_SOURCES, convert_records


def read_jsonl(path):
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_convert_records_outputs_expected_counts_and_fields(tmp_path):
    summary = convert_records(SOURCE_JSONL, tmp_path)

    sft_records = read_jsonl(tmp_path / "sft_messages.jsonl")
    dpo_records = read_jsonl(tmp_path / "dpo_pairs.jsonl")
    source_copy = read_jsonl(tmp_path / "source_traceable_records.jsonl")

    assert summary["sft_count"] == 30
    assert summary["dpo_count"] == 30
    assert len(source_copy) == 60
    assert len(sft_records) == 30
    assert len(dpo_records) == 30

    sft_record = sft_records[0]
    assistant_text = sft_record["messages"][1]["content"]
    assert assistant_text.startswith("policy_rationale:\n")
    assert "\n  mode: " in assistant_text
    assert "\n  risk_assessment: " in assistant_text
    assert "\n  authority_boundary: " in assistant_text
    assert "\n  safe_next_move: " in assistant_text
    assert "\n\nresponse:\n" in assistant_text

    dpo_record = dpo_records[0]
    assert dpo_record["chosen"].startswith("policy_rationale:\n")
    assert "response:\n" in dpo_record["chosen"]

    for record in (sft_record, dpo_record):
        metadata = record["metadata"]
        assert metadata["source"] == CANONICAL_SOURCE
        assert "source_original" in metadata
        assert "traceability" in metadata
        assert "policy_rationale" in metadata


def test_convert_records_supports_mixed_schema_versions(tmp_path):
    summary = convert_records(SOURCE_JSONL_V1_2, tmp_path)

    sft_records = read_jsonl(tmp_path / "sft_messages.jsonl")
    dpo_records = read_jsonl(tmp_path / "dpo_pairs.jsonl")
    source_copy = read_jsonl(tmp_path / "source_traceable_records.jsonl")

    assert summary["sft_count"] == 55
    assert summary["dpo_count"] == 55
    assert len(source_copy) == 110
    assert len(sft_records) == 55
    assert len(dpo_records) == 55

    schema_versions = {record["metadata"]["schema_version"] for record in sft_records + dpo_records}
    assert schema_versions == {"1.1", "1.2"}

    sft_v12 = next(record for record in sft_records if record["metadata"]["schema_version"] == "1.2")
    dpo_v12 = next(record for record in dpo_records if record["metadata"]["schema_version"] == "1.2")

    assert sft_v12["metadata"]["source"] == CANONICAL_SOURCES["1.2"]
    assert dpo_v12["metadata"]["source"] == CANONICAL_SOURCES["1.2"]
    assert sft_v12["messages"][1]["content"].startswith("policy_rationale:\n")
    assert dpo_v12["chosen"].startswith("policy_rationale:\n")


def test_convert_records_supports_v1_3_and_normalizes_new_source(tmp_path):
    summary = convert_records(SOURCE_JSONL_V1_3, tmp_path)

    sft_records = read_jsonl(tmp_path / "sft_messages.jsonl")
    dpo_records = read_jsonl(tmp_path / "dpo_pairs.jsonl")
    source_copy = read_jsonl(tmp_path / "source_traceable_records.jsonl")

    assert summary["sft_count"] == 88
    assert summary["dpo_count"] == 55
    assert len(source_copy) == 143
    assert len(sft_records) == 88
    assert len(dpo_records) == 55

    schema_versions = {record["metadata"]["schema_version"] for record in sft_records + dpo_records}
    assert schema_versions == {"1.1", "1.2", "1.3"}

    sft_v13 = next(record for record in sft_records if record["metadata"]["schema_version"] == "1.3")
    assert sft_v13["metadata"]["source"] == CANONICAL_SOURCES["1.3"]
    assert sft_v13["messages"][1]["content"].startswith("policy_rationale:\n")


def test_convert_records_supports_v1_4_and_normalizes_new_source(tmp_path):
    summary = convert_records(SOURCE_JSONL_V1_4, tmp_path)

    sft_records = read_jsonl(tmp_path / "sft_messages.jsonl")
    dpo_records = read_jsonl(tmp_path / "dpo_pairs.jsonl")
    source_copy = read_jsonl(tmp_path / "source_traceable_records.jsonl")

    assert summary["sft_count"] == 117
    assert summary["dpo_count"] == 55
    assert len(source_copy) == 172
    assert len(sft_records) == 117
    assert len(dpo_records) == 55

    schema_versions = {record["metadata"]["schema_version"] for record in sft_records + dpo_records}
    assert schema_versions == {"1.1", "1.2", "1.3", "1.4"}

    sft_v14 = next(record for record in sft_records if record["metadata"]["schema_version"] == "1.4")
    assert sft_v14["metadata"]["source"] == CANONICAL_SOURCES["1.4"]
    assert sft_v14["messages"][1]["content"].startswith("policy_rationale:\n")


def test_convert_records_supports_v1_5_and_normalizes_new_source(tmp_path):
    summary = convert_records(SOURCE_JSONL_V1_5, tmp_path)

    sft_records = read_jsonl(tmp_path / "sft_messages.jsonl")
    dpo_records = read_jsonl(tmp_path / "dpo_pairs.jsonl")
    source_copy = read_jsonl(tmp_path / "source_traceable_records.jsonl")

    assert summary["sft_count"] == 136
    assert summary["dpo_count"] == 55
    assert len(source_copy) == 191
    assert len(sft_records) == 136
    assert len(dpo_records) == 55

    schema_versions = {record["metadata"]["schema_version"] for record in sft_records + dpo_records}
    assert schema_versions == {"1.1", "1.2", "1.3", "1.4", "1.5"}

    sft_v15 = next(record for record in sft_records if record["metadata"]["schema_version"] == "1.5")
    assert sft_v15["metadata"]["source"] == CANONICAL_SOURCES["1.5"]
    assert sft_v15["messages"][1]["content"].startswith("policy_rationale:\n")


def test_convert_records_supports_v1_6_and_normalizes_new_source(tmp_path):
    summary = convert_records(SOURCE_JSONL_V1_6, tmp_path)

    sft_records = read_jsonl(tmp_path / "sft_messages.jsonl")
    dpo_records = read_jsonl(tmp_path / "dpo_pairs.jsonl")
    source_copy = read_jsonl(tmp_path / "source_traceable_records.jsonl")

    assert summary["sft_count"] == 171
    assert summary["dpo_count"] == 55
    assert len(source_copy) == 226
    assert len(sft_records) == 171
    assert len(dpo_records) == 55

    schema_versions = {record["metadata"]["schema_version"] for record in sft_records + dpo_records}
    assert schema_versions == {"1.1", "1.2", "1.3", "1.4", "1.5", "1.6"}

    sft_v16 = next(record for record in sft_records if record["metadata"]["schema_version"] == "1.6")
    assert sft_v16["metadata"]["source"] == CANONICAL_SOURCES["1.6"]
    assert sft_v16["metadata"]["derived_from_failure_family"]
    assert sft_v16["metadata"]["holdout_prompt_copied"] is False
    assert sft_v16["messages"][1]["content"].startswith("policy_rationale:\n")


def test_convert_records_supports_v1_7_and_normalizes_new_source(tmp_path):
    summary = convert_records(SOURCE_JSONL_V1_7, tmp_path)

    sft_records = read_jsonl(tmp_path / "sft_messages.jsonl")
    dpo_records = read_jsonl(tmp_path / "dpo_pairs.jsonl")
    source_copy = read_jsonl(tmp_path / "source_traceable_records.jsonl")

    assert summary["sft_count"] == 200
    assert summary["dpo_count"] == 55
    assert len(source_copy) == 255
    assert len(sft_records) == 200
    assert len(dpo_records) == 55

    schema_versions = {record["metadata"]["schema_version"] for record in sft_records + dpo_records}
    assert schema_versions == {"1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7"}

    sft_v17 = next(record for record in sft_records if record["metadata"]["schema_version"] == "1.7")
    assert sft_v17["metadata"]["source"] == CANONICAL_SOURCES["1.7"]
    assert sft_v17["metadata"]["derived_from_failure_family"]
    assert sft_v17["metadata"]["derived_from_holdout_id"]
    assert sft_v17["metadata"]["target_missing_tokens"] is not None
    assert sft_v17["metadata"]["holdout_prompt_copied"] is False
    assert sft_v17["messages"][1]["content"].startswith("policy_rationale:\n")
