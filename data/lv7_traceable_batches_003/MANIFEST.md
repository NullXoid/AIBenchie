# NullXoid Level 7-lite Traceable Training Batch 003 and Combined Smoke Dataset

Created: 2026-04-19T20:30:00+00:00

## Purpose

This package adds Batch 003 low-risk execute examples and produces the mixed-version smoke dataset source used for v1.2 smoke preparation. It preserves the existing traceability chain from literature anchors to failure modes, Level 7 attributes, eval harness links, requirement IDs, and paper claims.

## Counts

- Batch 003 SFT trajectories: 25
- Batch 003 DPO pairs: 25
- Batch 003 total: 50
- Combined total: 110
- Combined SFT trajectories: 55
- Combined DPO pairs: 55
- Validation passed: True

## Schema Versions

- Legacy records remain on schema v1.1
- Batch 003 records use schema v1.2
- Combined smoke source contains both schema versions without rewriting historical records

## Files

```text
schema/training_record_schema_v1_2.json
batch_003/sft_trajectories_003.jsonl
batch_003/dpo_pairs_003.jsonl
batch_003/all_records_003.jsonl
combined/all_training_records_v1_2.jsonl
combined/traceability_matrix.csv
validation_report.json
```

## Batch 003 Scenarios

1. gs_021_low_risk_readonly
2. gs_022_safe_test_run
3. gs_023_simple_file_lookup
4. gs_024_memory_read_summary
5. gs_025_model_invoke_safe

## Notes

- Batch 003 exists to prevent overtraining toward refusal, challenge, halt, or escalation.
- The combined smoke source is still a smoke dataset, not a final adapter dataset.
- Historical 6-scenario reports remain preserved separately as lv7_conflict_v0 artifacts.
