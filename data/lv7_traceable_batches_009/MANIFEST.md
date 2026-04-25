# LV7 Traceable Batch 009

## Contents

- schema/training_record_schema_v1_8.json
- batch_009/sft_trajectories_009.jsonl
- batch_009/all_records_009.jsonl
- combined/all_training_records_v1_8.jsonl
- combined/traceability_matrix.csv
- validation_report.json
- repair_record_scorecheck.json
- prompt_similarity_report.json

## Counts

- Batch 009 ambiguous clarify repairs: 6
- Batch 009 shutdown halt repairs: 3
- Batch 009 danger-shortcut strict repairs: 2
- Batch 009 exact-suite retention records: 11
- Batch 009 development-holdout retention records: 3
- Batch 009 total SFT records: 25
- Batch 009 DPO records: 0
- Combined records after Batch 009: 280

## Notes

- Batch 009 is an SFT-only ambiguity mode-stability micro patch.
- It is derived from v1.0.2 failure families and mode-balance needs, not copied holdout prompts.
- Exact holdout prompt copies fail validation.
- `repair_record_scorecheck.json` must pass before training proceeds.
- `evals/holdout/paraphrase_v0` is a development set after v1.0 / v1.0.2 / v1.0.3.
