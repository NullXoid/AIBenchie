# LV7 Smoke Dataset v1.3

## Source Batches

- 001R
- 002
- 003
- 004

## Schema Versions

- 1.1
- 1.2
- 1.3

## Counts

- source_traceable_records.jsonl: 143
- sft_messages.jsonl: 88
- dpo_pairs.jsonl: 55
- sft_train_ready.jsonl: 88

## Notes

- This remains an SFT-patch smoke dataset, not a final adapter dataset.
- Batch 003 prevents over-refusal by adding low-risk execute examples.
- Batch 004 teaches exact rubric-token compliance for the strict scorer.
