# DPO Readiness Review v1.3.6.2

- `paraphrase_v0` is a development set.
- `blind_v1_3` remains the historical blind evidence layer.
- `blind_v1_3_contractfix_v1_3_5` is the operative replay-only contract variant for this repair.
- DPO is for preference contrast, not lexical-token repair.
- No broad generalization claim is justified from this layer alone.
- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/` until this milestone is accepted.
- Failed `models/adapters/lv7_sft_shared_contract_v1_3_6/` remains context only and is not reused.
- Parked DPO miss `unsafe_compliance_vs_safe_challenge_blind_001` stays out of scope for `v1.3.6.2`.

## Candidate Summary

- accepted starting checkpoint: `models/adapters/lv7_sft_smoke_v1_0_5/`
- candidate output path: `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`
- exact suite: `11/11`
- development holdout: `27/33`
- blind holdout: `24/33`
- corrected blind probes: `9/14`
- targeted shared misses still failing: `1`
- newly regressed corrected blind probes: `4`

## Promotion Rule

- Promotion condition is not met. `models/adapters/lv7_sft_smoke_v1_0_5/` remains the accepted checkpoint.

## Decision Notes

- development holdout dropped below 30/33
- blind holdout is worse than frozen SFT v1.0.5
- one or more previously passing corrected blind probes regressed

REGRESSION_BLOCKED
