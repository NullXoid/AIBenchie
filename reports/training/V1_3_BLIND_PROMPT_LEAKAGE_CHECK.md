# V1.3 Blind Prompt Leakage Check

- `paraphrase_v0` is a development set.
- `blind_v1_3` is the new blind evidence layer.
- DPO is for preference contrast, not lexical-token repair.
- Blind prompts remain evaluation-only assets and must not be added to SFT, DPO, repair batches, or future training datasets during v1.3.

## Summary

- similarity threshold: `0.88`
- hard-fail threshold: `0.96`
- exact copies: `0`
- near duplicates: `11`
- hard-fail near duplicates: `0`

## Source Breakdown

| source | prompt_count | exact_copies | near_duplicates | hard_fail_near_duplicates |
| --- | --- | --- | --- | --- |
| `evals/holdout/paraphrase_v0` | `33` | `0` | `0` | `0` |
| `evals/dpo_probes/v1_2` | `14` | `0` | `0` | `0` |
| `data/pilot_v1_9/dpo_pairs.jsonl` | `55` | `0` | `1` | `0` |
| `data/pilot_v1_9/sft_messages.jsonl` | `247` | `0` | `2` | `0` |
| `data/pilot_v1_9/sft_train_ready.jsonl` | `247` | `0` | `2` | `0` |
| `data/pilot_v1_9/source_traceable_records.jsonl` | `302` | `0` | `3` | `0` |
| `data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl` | `28` | `0` | `0` | `0` |
| `data/lv7_traceable_batches_001R_002/batch_001R/all_records_001R.jsonl` | `30` | `0` | `0` | `0` |
| `data/lv7_traceable_batches_001R_002/batch_002/all_records_002.jsonl` | `30` | `0` | `0` | `0` |
| `data/lv7_traceable_batches_003/batch_003/all_records_003.jsonl` | `50` | `0` | `2` | `0` |
| `data/lv7_traceable_batches_004/batch_004/all_records_004.jsonl` | `33` | `0` | `1` | `0` |
| `data/lv7_traceable_batches_005/batch_005/all_records_005.jsonl` | `29` | `0` | `0` | `0` |
| `data/lv7_traceable_batches_006/batch_006/all_records_006.jsonl` | `19` | `0` | `0` | `0` |
| `data/lv7_traceable_batches_007/batch_007/all_records_007.jsonl` | `35` | `0` | `0` | `0` |
| `data/lv7_traceable_batches_008/batch_008/all_records_008.jsonl` | `29` | `0` | `0` | `0` |
| `data/lv7_traceable_batches_009/batch_009/all_records_009.jsonl` | `25` | `0` | `0` | `0` |
| `data/lv7_traceable_batches_010/batch_010/all_records_010.jsonl` | `22` | `0` | `0` | `0` |

## Lower-Threshold Near Duplicates

| blind_id | source | source_id | similarity | justification |
| --- | --- | --- | --- | --- |
| `simple_file_lookup_001_blind_001` | `data/pilot_v1_9/dpo_pairs.jsonl` | `dpo_gs_023_simple_file_lookup_002_003` | `0.8929` | Retained only because the phrasing diverges materially from the source while preserving the same scenario family. This remained below the hard-fail threshold and was reviewed as evaluation-only. |
| `simple_file_lookup_001_blind_001` | `data/pilot_v1_9/sft_messages.jsonl` | `sft_messages.jsonl::0042::user::001` | `0.8929` | Retained only because the phrasing diverges materially from the source while preserving the same scenario family. This remained below the hard-fail threshold and was reviewed as evaluation-only. |
| `simple_file_lookup_001_blind_001` | `data/pilot_v1_9/sft_messages.jsonl` | `sft_messages.jsonl::0081::user::001` | `0.9524` | Retained only because the phrasing diverges materially from the source while preserving the same scenario family. This remained below the hard-fail threshold and was reviewed as evaluation-only. |
| `simple_file_lookup_001_blind_001` | `data/pilot_v1_9/sft_train_ready.jsonl` | `sft_train_ready.jsonl::0042::user::001` | `0.8929` | Retained only because the phrasing diverges materially from the source while preserving the same scenario family. This remained below the hard-fail threshold and was reviewed as evaluation-only. |
| `simple_file_lookup_001_blind_001` | `data/pilot_v1_9/sft_train_ready.jsonl` | `sft_train_ready.jsonl::0081::user::001` | `0.9524` | Retained only because the phrasing diverges materially from the source while preserving the same scenario family. This remained below the hard-fail threshold and was reviewed as evaluation-only. |
| `simple_file_lookup_001_blind_001` | `data/pilot_v1_9/source_traceable_records.jsonl` | `sft_gs_023_simple_file_lookup_002_003` | `0.8929` | Retained only because the phrasing diverges materially from the source while preserving the same scenario family. This remained below the hard-fail threshold and was reviewed as evaluation-only. |
| `simple_file_lookup_001_blind_001` | `data/pilot_v1_9/source_traceable_records.jsonl` | `dpo_gs_023_simple_file_lookup_002_003` | `0.8929` | Retained only because the phrasing diverges materially from the source while preserving the same scenario family. This remained below the hard-fail threshold and was reviewed as evaluation-only. |
| `simple_file_lookup_001_blind_001` | `data/pilot_v1_9/source_traceable_records.jsonl` | `sft_gs_023_simple_file_lookup_002_004` | `0.9524` | Retained only because the phrasing diverges materially from the source while preserving the same scenario family. This remained below the hard-fail threshold and was reviewed as evaluation-only. |
| `simple_file_lookup_001_blind_001` | `data/lv7_traceable_batches_003/batch_003/all_records_003.jsonl` | `sft_gs_023_simple_file_lookup_002_003` | `0.8929` | Retained only because the phrasing diverges materially from the source while preserving the same scenario family. This remained below the hard-fail threshold and was reviewed as evaluation-only. |
| `simple_file_lookup_001_blind_001` | `data/lv7_traceable_batches_003/batch_003/all_records_003.jsonl` | `dpo_gs_023_simple_file_lookup_002_003` | `0.8929` | Retained only because the phrasing diverges materially from the source while preserving the same scenario family. This remained below the hard-fail threshold and was reviewed as evaluation-only. |
| `simple_file_lookup_001_blind_001` | `data/lv7_traceable_batches_004/batch_004/all_records_004.jsonl` | `sft_gs_023_simple_file_lookup_002_004` | `0.9524` | Retained only because the phrasing diverges materially from the source while preserving the same scenario family. This remained below the hard-fail threshold and was reviewed as evaluation-only. |

## Rule Check

- exact copies = `0`: `yes`
- hard-fail near duplicates revised: `yes`

