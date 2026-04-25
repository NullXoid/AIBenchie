# LV7 Smoke Dataset v1.4

## Source Batches

- 001R
- 002
- 003
- 004
- 005

## Schema Versions

- 1.1
- 1.2
- 1.3
- 1.4

## Counts

- source_traceable_records.jsonl: 172
- sft_messages.jsonl: 117
- dpo_pairs.jsonl: 55
- sft_train_ready.jsonl: 117

## Notes

- This remains an SFT-patch smoke dataset, not a final adapter dataset.
- Batch 003 prevents over-refusal by adding low-risk execute examples.
- Batch 004 teaches exact rubric-token compliance for the strict scorer.
- Batch 005 targets the remaining six failures and protects the five v0.6 strict passes.
