# DPO Readiness Review v1.3.2

- `paraphrase_v0` is a development set.
- `blind_v1_3` is the current blind evidence layer.
- DPO is for preference contrast, not lexical-token repair.
- Blind prompts remain evaluation-only assets and are not authorized for training in v1.3.2.
- No broad generalization claim is justified from this layer alone.
- Stable accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- `models/adapters/lv7_dpo_smoke_v1_2_4/` remains evidence only and is not promoted here.

## Summary

- accepted expansion pairs: `12`
- combined dataset pairs: `40`
- accepted category split: `{'overrefusal_vs_bounded_execute': 2, 'unnecessary_escalation_vs_low_risk_execute': 2, 'audit_evasion_vs_audit_preservation': 4, 'unsafe_compliance_vs_safe_challenge': 4}`
- exact prompt copies: `0`
- hard-fail near duplicates: `0`
- original selected dataset checksum unchanged: `True`

## Aggregate Issues

- none

## Decision

- `DPO_EXPANSION_READY_FOR_SMOKE` only if all 12 expansion pairs pass audit, similarity gates pass, the original 28-pair dataset checksum is unchanged, the combined dataset totals exactly 40, and the accepted split is exactly `2/2/4/4`.
- `NEEDS_EXPANSION_REVISION` for any audit failure, category-count miss, similarity failure, or blind-prompt leakage issue.

DPO_EXPANSION_READY_FOR_SMOKE
