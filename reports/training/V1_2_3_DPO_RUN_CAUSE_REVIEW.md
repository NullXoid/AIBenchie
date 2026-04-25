# V1.2.3 DPO Run Cause Review

- Accepted adapter: `models/adapters/lv7_sft_smoke_v1_0_5/`
- Blocked experimental adapter: `models/adapters/lv7_dpo_smoke_v1_2/`
- `paraphrase_v0` is a development set after repeated failure-derived patches.
- A future blind holdout is required before broader generalization claims.
- DPO is for preference contrast, not lexical-token repair.

## Evidence

- selected DPO category distribution: `unsafe_compliance_vs_safe_challenge=4`, `overrefusal_vs_bounded_execute=4`, `unnecessary_escalation_vs_low_risk_execute=4`, `audit_evasion_vs_audit_preservation=4`, `shutdown_resistance_vs_halt=4`, `privilege_self_escalation_vs_approved_lease=4`, `hidden_persistence_vs_approved_recovery=4`
- run config: `beta=0.1`, `max_steps=24`, `learning_rate=not recorded in run config`
- train log summary: `final_step=24`, `final_epoch=3.4285714285714284`, `peak_reward_margin=2.997690260410309`
- holdout scores: `strict 30/33 -> 30/33`, `mode_match 32/33 -> 31/33`
- probe results: `unsafe_compliance_vs_safe_challenge=1/2 overrefusal_vs_bounded_execute=1/2 unnecessary_escalation_vs_low_risk_execute=2/2 audit_evasion_vs_audit_preservation=1/2 shutdown_resistance_vs_halt=1/2 privilege_self_escalation_vs_approved_lease=2/2 hidden_persistence_vs_approved_recovery=2/2`

## Primary Cause

- primary cause: `dpo_too_strong`
- contributing causes: `missing_clarify_regression_guard`
- rationale: The 28-pair dataset stayed balanced and valid, but a 24-step, beta=0.1 smoke run pushed preference pressure strongly enough to flip an ambiguous clarify case toward challenge while most other gates held steady.

## Explicit Diagnosis

- DPO overcorrection: `yes`
- missing clarify-specific protection: `yes`
- concrete selected-pair flaw: `no`
- weaker explanation only (variance or evaluator brittleness): `no`
