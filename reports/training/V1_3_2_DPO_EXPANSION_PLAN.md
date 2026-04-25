# V1.3.2 DPO Expansion Plan

- `paraphrase_v0` is a development set.
- `blind_v1_3` is the current blind evidence layer.
- DPO is for preference contrast, not lexical-token repair.
- Blind prompts remain evaluation-only assets and are not authorized for training in v1.3.2.
- No broad generalization claim is justified from this layer alone.
- Stable accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- `models/adapters/lv7_dpo_smoke_v1_2_4/` remains evidence only and is not promoted here.

- This milestone is data-only and does not authorize a DPO run.
- Stable accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- `models/adapters/lv7_dpo_smoke_v1_2_4/` remains evidence only.

## Expansion Scope

- accepted expansion size: `12` pairs
- combined dataset size: `40` pairs
- fixed accepted split: `2/2/4/4` across overrefusal, unnecessary escalation, audit, and unsafe shortcut categories
- original `data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl` remains unchanged
- blind prompts remain evaluation-only and are excluded from training data

## Future Retry Config

- `training/dpo_smoke_config_v1_3_2.yaml` is plan-only.
- it points to `data/dpo_expansion_v1_3_2/dpo_pairs_selected_plus_expansion.jsonl`.
- it preserves the smaller DPO settings from the accepted v1.2.4 smoke retry.

