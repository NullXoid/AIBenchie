# V1.1 DPO Smoke Plan

- Current planning status: `DPO_SMOKE_PLAN_READY`
- This milestone is planning-only; no DPO run occurs in v1.1.
- DPO's role is to improve preference behavior while preserving the SFT-learned LV7 structure.
- DPO must not be used for lexical-token repair.
- `evals/holdout/paraphrase_v0` remains a development set after repeated failure-derived patches.
- A future blind holdout is required before broader generalization claims.

## Planned Smoke Inputs

- Base model: `Qwen/Qwen2.5-1.5B-Instruct`
- Starting adapter: `models/adapters/lv7_sft_smoke_v1_0_5/`
- Planned selected DPO dataset: `data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl`
- Planned output adapter: `models/adapters/lv7_dpo_smoke_v1_1/`
- Current selected dataset size: `28`

## Future Post-DPO Evaluation Scope

- exact suite
- development holdout
- future blind holdout
- over-refusal probes
- unsafe-compliance probes

## Next-Step Rule

- If v1.1 ends `DPO_SMOKE_PLAN_READY`, the next milestone is v1.2 DPO smoke execution approval/planning, not automatic execution.
- If v1.1 ends `NEEDS_DPO_DATA_REWRITE`, rewrite or replace weak DPO pairs before planning execution.
