# LV7 Smoke Dataset v1.2

## Source Batches

- 001R
- 002
- 003

## Schema Versions

- 1.1
- 1.2

## Counts

- source_traceable_records.jsonl: 110
- sft_messages.jsonl: 55
- dpo_pairs.jsonl: 55

## Notes

- This is a smoke dataset, not a final adapter dataset.
- Batch 003 prevents overtraining toward refusal or challenge behavior by adding low-risk execute examples.
- SFT should teach policy_rationale format and mode selection before any DPO smoke step.
