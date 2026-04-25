# V1.2.3 Smaller DPO Plan

- Accepted adapter: `models/adapters/lv7_sft_smoke_v1_0_5/`
- Blocked experimental adapter: `models/adapters/lv7_dpo_smoke_v1_2/`
- `paraphrase_v0` is a development set after repeated failure-derived patches.
- A future blind holdout is required before broader generalization claims.
- DPO is for preference contrast, not lexical-token repair.

## Proposed v1.2.4 Settings

- `starting_adapter: models/adapters/lv7_sft_smoke_v1_0_5/`
- `output_adapter: models/adapters/lv7_dpo_smoke_v1_2_4/`
- `max_steps: 12`
- `beta: 0.05`
- `learning_rate: 3e-6`
- selected dataset unchanged unless a concrete selected-pair flaw is proven
- preserve current batch size and gradient accumulation
- preserve replay-only evaluation
- preserve all current hard gates
- add explicit pre/post Ambiguous Goal clarify checks

## Execution Notes

- keep `data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl` unchanged for the retry
- preserve `per_device_train_batch_size: 1` and `gradient_accumulation_steps: 4`
- rerun exact suite, development holdout, and v1.2 probes through replay only
- require `ambiguous_goal_001` exact plus all holdout cases to remain `clarify` before accepting the retry
