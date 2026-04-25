# V1.1 DPO Target Taxonomy

- Source of truth: `data/pilot_v1_9/dpo_pairs.jsonl`
- `evals/holdout/paraphrase_v0` remains a development set after repeated failure-derived patches.
- A future blind holdout is required before broader generalization claims.
- DPO is for preference contrast, not lexical-token repair.

## Taxonomy

| category | selection role | linked scenario families | safe candidates | overtraining risk | regression guard |
| --- | --- | --- | --- | --- | --- |
| `unsafe_compliance_vs_safe_challenge` | primary | Danger Shortcut | `5` | Can over-amplify challenge style if used to teach token wording instead of unsafe-compliance preference. | Preserve exact-suite danger behavior and do not let challenge language spread into ambiguous-goal requests. |
| `overrefusal_vs_bounded_execute` | primary | Low-Risk Readonly, Safe Test Run, Simple File Lookup, Memory Read Summary, Model Invoke Safe | `5` | Can make the model too eager if paired with ambiguous or scope-overreach examples. | Low-risk execute retention must remain 15/15 by mode. |
| `unnecessary_escalation_vs_low_risk_execute` | primary | Low-Risk Readonly, Safe Test Run, Simple File Lookup, Memory Read Summary, Model Invoke Safe | `15` | Can blur approval boundaries if low-risk examples are not clearly bounded. | No increase in over-refusal or unnecessary approval friction on low-risk tasks. |
| `audit_evasion_vs_audit_preservation` | primary | Audit Evasion | `4` | Can become lexical if the objective turns into memorizing `logged` rather than preserving audit visibility. | No decrease in audit safety and no audit-evasion acceptance. |
| `shutdown_resistance_vs_halt` | primary | Shutdown Conflict | `5` | Can over-weight halt behavior if it leaks into non-shutdown prompts. | Shutdown prompts must remain halt; ambiguous-goal prompts must not drift toward refusal. |
| `privilege_self_escalation_vs_approved_lease` | primary | Privilege Escalation | `5` | Can produce over-escalation language on low-risk prompts if approval framing spreads. | No decrease in privilege safety and no self-issued authority. |
| `hidden_persistence_vs_approved_recovery` | primary | MAPE-K Recovery | `5` | Can over-index on recovery mechanics if hidden-persistence contrast is weak. | No silent migration, no hidden persistence, and no decrease in recovery safety. |
| `bad_approval_behavior_vs_correct_lease_request` | secondary tag only | Danger Shortcut, Privilege Escalation, MAPE-K Recovery, selected low-risk approval-friction pairs | `--` | Would double-count approval behavior if promoted to a primary bucket in v1.1. | Keep as a secondary tag unless a later dataset is centered on lease misuse. |

## Ambiguous Goal Handling

- All 5 `Ambiguous Goal` pairs are audited but excluded from `dpo_pairs_selected.jsonl`.
- Exclusion reason: clarification behavior is SFT/mode-discipline territory, not a v1.1 DPO smoke target.
- Ambiguous-goal stability remains a regression guard only.
