# LV7 Smoke Dataset v1.8

## Source Batches

- 001R
- 002
- 003
- 004
- 005
- 006
- 007
- 008
- 009

## Schema Versions

- 1.1
- 1.2
- 1.3
- 1.4
- 1.5
- 1.6
- 1.7
- 1.8

## Counts

- source_traceable_records.jsonl: 280
- sft_messages.jsonl: 225
- dpo_pairs.jsonl: 55
- sft_train_ready.jsonl: 225

## Notes

- This remains an SFT micro-patch dataset, not a final adapter dataset.
- Batch 009 was derived from failure families and mode-balance needs, not copied holdout prompts.
- `evals/holdout/paraphrase_v0` is a development set after v1.0 / v1.0.2 / v1.0.3.
- A future blind holdout is required before broader generalization claims.
