# DPO Readiness Review V1.3.1

- `paraphrase_v0` is a development set.
- `blind_v1_3` is the current blind evidence layer.
- DPO is for preference contrast, not lexical-token repair.
- No broad generalization claim is justified from this layer alone.
- Stable accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- `models/adapters/lv7_dpo_smoke_v1_2_4/` remains evidence only and is not promoted here.

## Summary

- accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`
- DPO evidence checkpoint remains `models/adapters/lv7_dpo_smoke_v1_2_4/`
- DPO blind holdout strict: `26/33`
- SFT blind holdout strict: `27/33`
- DPO blind probes: `7/14`
- SFT blind probes: `9/14`
- selected pairs re-audited clean: `yes`
- v1.2.4 run config: `max_steps=12`, `beta=0.05`, `learning_rate=3e-06`
- v1.2.4 train log summary: `steps=12`, `train_loss=0.5849108546972275`

## Decision Rationale

- The accepted v1.2.4 retry already used the reduced-intensity recipe (`max_steps=12`, `beta=0.05`, `learning_rate=3e-6`), so blind probe losses are less consistent with another pure intensity reduction.
- Selected pairs remain structurally clean and balanced, but the blind failures cluster in categories where the chosen set is too narrow on low-risk execute phrasing, audit logging language, or unsafe-shortcut paraphrase variety.
- DPO still trails SFT on blind probes (`7/14` vs `9/14`), and the underperformance is concentrated in `audit_evasion_vs_audit_preservation`, `unsafe_compliance_vs_safe_challenge`.

## Category Evidence

- categories where DPO underperformed SFT on blind probes: `audit_evasion_vs_audit_preservation`, `unsafe_compliance_vs_safe_challenge`
- categories with the clearest probe-targeted coverage gap:
  - `audit_evasion_vs_audit_preservation` -> `category_under_specification`: The selected category examples preserve the right preference direction but miss blind-required phrasing anchors such as `logged`, which leaves the blind variant under-specified.
  - `overrefusal_vs_bounded_execute` -> `too_few_low_risk_execute_guards`: Development probes were clean, but blind low-risk execute probes dropped to 0/2 while the selected set only has four low-risk pairs spread across several tool shapes.
  - `unnecessary_escalation_vs_low_risk_execute` -> `too_few_low_risk_execute_guards`: Development probes were clean, but blind low-risk execute probes dropped to 0/2 while the selected set only has four low-risk pairs spread across several tool shapes.
  - `unsafe_compliance_vs_safe_challenge` -> `insufficient_variation`: The selected examples cover the core category, but they are too narrow in paraphrase shape to reliably transfer the preference behavior to the blind prompt wording.

## Final Status

NEEDS_DPO_PROBE_TARGETED_EXPANSION