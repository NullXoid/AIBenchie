# LV7 Smoke Dataset v1.6

## Source Batches

- 001R
- 002
- 003
- 004
- 005
- 006
- 007

## Schema Versions

- 1.1
- 1.2
- 1.3
- 1.4
- 1.5
- 1.6

## Counts

- source_traceable_records.jsonl: 226
- sft_messages.jsonl: 171
- dpo_pairs.jsonl: 55
- sft_train_ready.jsonl: 171

## Notes

- This remains an SFT robustness-patch dataset, not a final adapter dataset.
- Batch 003 prevents over-refusal by adding low-risk execute examples.
- Batch 004 teaches exact rubric-token compliance for the strict scorer.
- Batch 005 repaired the remaining six failures and protected the five v0.6 strict passes.
- Batch 006 repaired the final two safety failures and protected the nine v0.7 strict passes.
- Batch 007 was derived from holdout failure families, not copied holdout prompts.
- After v1.0, `evals/holdout/paraphrase_v0` is treated as a paraphrase development set rather than a pristine blind holdout.
