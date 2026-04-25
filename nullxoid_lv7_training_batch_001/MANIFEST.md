# NullXoid Level 7-lite Synthetic Training Batch 001

Created: 2026-04-19T00:19:44.414716+00:00

## Contents

- `training_record_schema.json` — combined schema for SFT trajectory and DPO pair records.
- `sft_trajectories.jsonl` — 15 SFT trajectory records.
- `dpo_pairs.jsonl` — 15 DPO preference-pair records.
- `all_training_records.jsonl` — all 30 records in one JSONL file.
- `validation_report.json` — basic validation report.

## Golden Scenarios

1. `gs_001_danger_shortcut`
2. `gs_002_ambiguous_goal`
3. `gs_005_shutdown_conflict`

## Counts

- SFT trajectories: 15
- DPO pairs: 15
- Total records: 30
- Validation passed: True

## Note on monologue_reasoning

The `monologue_reasoning` block is a synthetic operational rationale for training.
It is not hidden chain-of-thought. It gives the model high-level, inspectable policy reasoning:
risk, authority boundary, and next safe move.
