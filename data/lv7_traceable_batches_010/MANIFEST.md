# LV7 Traceable Batch 010

## Contents

- schema/training_record_schema_v1_9.json
- batch_010/sft_trajectories_010.jsonl
- batch_010/all_records_010.jsonl
- combined/all_training_records_v1_9.jsonl
- combined/traceability_matrix.csv
- validation_report.json
- repair_record_scorecheck.json
- prompt_similarity_report.json

## Counts

- Batch 010 regressed lexical repairs: 8
- Batch 010 unchanged shutdown light repair: 1
- Batch 010 improved-case retention records: 2
- Batch 010 exact-suite retention records: 11
- Batch 010 total SFT records: 22
- Batch 010 DPO records: 0
- Combined records after Batch 010: 302

## Notes

- Batch 010 is an SFT-only tiny lexical-retention patch.
- It is smaller than Batch 009 and targets only the four regressed strict cases, one light shutdown repair, and minimal retention.
- Batch 010 was derived from failure families and lexical-retention needs, not copied holdout prompts.
- Exact holdout prompt copies fail validation.
- `repair_record_scorecheck.json` must pass before training proceeds.
- `evals/holdout/paraphrase_v0` is a development set after repeated failure-derived patches.
