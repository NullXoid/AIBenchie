# LV7 Smoke Dataset v1.9

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
- 010

## Schema Versions

- 1.1
- 1.2
- 1.3
- 1.4
- 1.5
- 1.6
- 1.7
- 1.8
- 1.9

## Counts

- source_traceable_records.jsonl: 302
- sft_messages.jsonl: 247
- dpo_pairs.jsonl: 55
- sft_train_ready.jsonl: 247

## Notes

- This remains an SFT lexical-retention patch dataset, not a final adapter dataset.
- Batch 010 was derived from failure families and lexical-retention needs, not copied holdout prompts.
- `evals/holdout/paraphrase_v0` is a development set after repeated failure-derived patches.
- A future blind holdout is required before broader generalization claims.
