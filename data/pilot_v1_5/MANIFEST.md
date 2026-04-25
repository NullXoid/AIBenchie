# LV7 Smoke Dataset v1.5

## Source Batches

- 001R
- 002
- 003
- 004
- 005
- 006

## Schema Versions

- 1.1
- 1.2
- 1.3
- 1.4
- 1.5

## Counts

- source_traceable_records.jsonl: 191
- sft_messages.jsonl: 136
- dpo_pairs.jsonl: 55
- sft_train_ready.jsonl: 136

## Notes

- This remains an SFT-patch smoke dataset, not a final adapter dataset.
- Batch 003 prevents over-refusal by adding low-risk execute examples.
- Batch 004 teaches exact rubric-token compliance for the strict scorer.
- Batch 005 repaired the remaining six failures and protected the five v0.6 strict passes.
- Batch 006 targets the final two safety failures and protects the nine v0.7 strict passes.
