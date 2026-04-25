# NullXoid Level 7-lite Traceable Training Batches 001R and 002

Created: 2026-04-19T00:59:17.101502+00:00

## Purpose

This package upgrades Batch 001 to schema v1.1 and adds Batch 002. It establishes traceability from literature anchors to failure modes, Level 7 attributes, evaluation harness links, requirement IDs, and paper claims.

## Counts

- Batch 001R SFT trajectories: 15
- Batch 001R DPO pairs: 15
- Batch 001R total: 30
- Batch 002 SFT trajectories: 15
- Batch 002 DPO pairs: 15
- Batch 002 total: 30
- Combined total: 60
- Validation passed: True

## Files

```text
schema/training_record_schema_v1_1.json
batch_001R/sft_trajectories_001R.jsonl
batch_001R/dpo_pairs_001R.jsonl
batch_001R/all_records_001R.jsonl
batch_002/sft_trajectories_002.jsonl
batch_002/dpo_pairs_002.jsonl
batch_002/all_records_002.jsonl
combined/all_training_records_v1_1.jsonl
combined/traceability_matrix.csv
paper/training_for_corrigibility.md
validation_report.json
```

## Scenarios

Batch 001R:
1. gs_001_danger_shortcut
2. gs_002_ambiguous_goal
3. gs_005_shutdown_conflict

Batch 002:
1. gs_006_privilege_escalation
2. gs_008_audit_evasion
3. gs_015_mape_recovery

## Notes

- `policy_rationale` replaces the earlier `monologue_reasoning` name.
- `policy_rationale` is an auditable decision summary, not hidden chain-of-thought.
- DPO records include `policy_rationale` and traceability so preference tuning remains connected to the paper's evidence chain.
