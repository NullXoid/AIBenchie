# DPO Readiness Review v1.2.3

- Accepted adapter: `models/adapters/lv7_sft_smoke_v1_0_5/`
- Blocked experimental adapter: `models/adapters/lv7_dpo_smoke_v1_2/`
- `paraphrase_v0` is a development set after repeated failure-derived patches.
- A future blind holdout is required before broader generalization claims.
- DPO is for preference contrast, not lexical-token repair.

## Decision Summary

- primary cause: `dpo_too_strong`
- contributing causes: `missing_clarify_regression_guard`
- recommendation: The selected data still looks valid and the main regression pattern is DPO overcorrection, so the next step should be a smaller DPO retry from the frozen v1.0.5 adapter.

## Final Status

NEEDS_SMALLER_DPO_RUN
