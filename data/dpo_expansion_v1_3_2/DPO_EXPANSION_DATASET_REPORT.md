# v1.3.2 DPO Expansion Dataset Report

- `paraphrase_v0` is a development set.
- `blind_v1_3` is the current blind evidence layer.
- DPO is for preference contrast, not lexical-token repair.
- Blind prompts remain evaluation-only assets and are not authorized for training in v1.3.2.
- No broad generalization claim is justified from this layer alone.
- Stable accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- `models/adapters/lv7_dpo_smoke_v1_2_4/` remains evidence only and is not promoted here.

## Summary

- proposed pair count: `12`
- accepted pair count: `12`
- rejected pair count: `0`
- accepted category split: `{'overrefusal_vs_bounded_execute': 2, 'unnecessary_escalation_vs_low_risk_execute': 2, 'audit_evasion_vs_audit_preservation': 4, 'unsafe_compliance_vs_safe_challenge': 4}`
- exact copy count: `0`
- hard-fail near duplicate count: `0`
- original selected dataset checksum before build: `d0eca059e51c406f3697947455f0c0468426fe3ab53e03db856bfae22eb1da6b`
- original selected dataset checksum after build: `d0eca059e51c406f3697947455f0c0468426fe3ab53e03db856bfae22eb1da6b`
- selected dataset unchanged: `True`

## Lower-Threshold Near Duplicates

- none retained; the accepted set was revised until no threshold-level near duplicates remained.

## Category Split

| category | count |
| --- | --- |
| overrefusal_vs_bounded_execute | 2 |
| unnecessary_escalation_vs_low_risk_execute | 2 |
| audit_evasion_vs_audit_preservation | 4 |
| unsafe_compliance_vs_safe_challenge | 4 |

