# LV7 Traceable Batch 007

## Contents

- schema/training_record_schema_v1_6.json
- batch_007/sft_trajectories_007.jsonl
- batch_007/all_records_007.jsonl
- combined/all_training_records_v1_6.jsonl
- combined/traceability_matrix.csv
- validation_report.json
- repair_record_scorecheck.json

## Counts

- Batch 007 repair SFT records: 24
- Batch 007 retention SFT records: 11
- Batch 007 total SFT records: 35
- Batch 007 DPO records: 0
- Combined records after Batch 007: 226

## Notes

- Batch 007 is an SFT-only paraphrase repair package.
- It is derived from v0.9 holdout failure families, not copied holdout prompts.
- `repair_record_scorecheck.json` must pass before training proceeds.
- After v1.0, `evals/holdout/paraphrase_v0` is treated as a paraphrase development set rather than a pristine blind holdout.
