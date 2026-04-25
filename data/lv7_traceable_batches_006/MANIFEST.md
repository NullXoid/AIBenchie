# LV7 Traceable Batch 006

## Contents

- schema/training_record_schema_v1_5.json
- batch_006/sft_trajectories_006.jsonl
- batch_006/all_records_006.jsonl
- combined/all_training_records_v1_5.jsonl
- combined/traceability_matrix.csv
- validation_report.json
- repair_record_scorecheck.json

## Counts

- Batch 006 repair SFT records: 10
- Batch 006 retention SFT records: 9
- Batch 006 total SFT records: 19
- Batch 006 DPO records: 0
- Combined records after Batch 006: 191

## Notes

- Batch 006 is an SFT-only final safety repair package.
- It targets the final two v0.7 failures and adds retention records for the nine v0.7 strict passes.
- `repair_record_scorecheck.json` must pass before training proceeds.
