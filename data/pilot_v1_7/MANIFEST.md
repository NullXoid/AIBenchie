# LV7 Smoke Dataset v1.7

## Source Batches

- 001R
- 002
- 003
- 004
- 005
- 006
- 007
- 008

## Schema Versions

- 1.1
- 1.2
- 1.3
- 1.4
- 1.5
- 1.6
- 1.7

## Counts

- source_traceable_records.jsonl: 255
- sft_messages.jsonl: 200
- dpo_pairs.jsonl: 55
- sft_train_ready.jsonl: 200

## Notes

- This remains an SFT robustness-patch dataset, not a final adapter dataset.
- Batch 008 was derived from holdout failure families and token-miss patterns, not copied holdout prompts.
- `evals/holdout/paraphrase_v0` is a development set after v1.0.
- A future new blind holdout is required before broader generalization claims.
