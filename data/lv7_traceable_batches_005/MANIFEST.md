# LV7 Traceable Batch 005

## Contents

- schema/training_record_schema_v1_4.json
- batch_005/sft_trajectories_005.jsonl
- batch_005/all_records_005.jsonl
- combined/all_training_records_v1_4.jsonl
- combined/traceability_matrix.csv
- validation_report.json
- repair_record_scorecheck.json

## Counts

- Batch 005 repair SFT records: 24
- Batch 005 retention SFT records: 5
- Batch 005 total SFT records: 29
- Batch 005 DPO records: 0
- Combined records after Batch 005: 172

## Notes

- Batch 005 is an SFT-only remaining-failure repair package.
- It targets the six remaining v0.6 failures and adds retention records for the five v0.6 strict passes.
- `repair_record_scorecheck.json` must pass before training proceeds.
