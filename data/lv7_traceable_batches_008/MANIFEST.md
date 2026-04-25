# LV7 Traceable Batch 008

## Contents

- schema/training_record_schema_v1_7.json
- batch_008/sft_trajectories_008.jsonl
- batch_008/all_records_008.jsonl
- combined/all_training_records_v1_7.jsonl
- combined/traceability_matrix.csv
- validation_report.json
- repair_record_scorecheck.json
- prompt_similarity_report.json

## Counts

- Batch 008 repair SFT records: 18
- Batch 008 retention SFT records: 11
- Batch 008 total SFT records: 29
- Batch 008 DPO records: 0
- Combined records after Batch 008: 255

## Notes

- Batch 008 is an SFT-only token-targeted paraphrase repair package.
- It is derived from v1.0 development-set failure families and token-miss patterns, not copied holdout prompts.
- `repair_record_scorecheck.json` must pass before training proceeds.
- Exact holdout prompt copies fail validation.
- After v1.0 and v1.0.2, `evals/holdout/paraphrase_v0` is treated as a paraphrase development set rather than a pristine blind holdout.
