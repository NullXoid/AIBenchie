# DPO Smoke Dataset Report

- Source of truth: `data/pilot_v1_9/dpo_pairs.jsonl`
- Final planning status: `DPO_SMOKE_PLAN_READY`
- Selected dataset size: `28`
- Excluded dataset size: `27`
- Ambiguous Goal pairs audited and excluded: `5`
- `evals/holdout/paraphrase_v0` remains a development set after repeated failure-derived patches.
- A future blind holdout is required before broader generalization claims.

## Balanced 28-Pair Rule

- Requirement: exactly 28 selected pairs, exactly 4 safe pairs per primary category, only clearly-ranked pairs, and no lexical-token repair pairs.
- Coverage gaps: `none`

## Safe Candidate Counts

| primary category | safe candidate count | required |
| --- | --- | --- |
| `unsafe_compliance_vs_safe_challenge` | `5` | `4` |
| `overrefusal_vs_bounded_execute` | `5` | `4` |
| `unnecessary_escalation_vs_low_risk_execute` | `15` | `4` |
| `audit_evasion_vs_audit_preservation` | `4` | `4` |
| `shutdown_resistance_vs_halt` | `5` | `4` |
| `privilege_self_escalation_vs_approved_lease` | `5` | `4` |
| `hidden_persistence_vs_approved_recovery` | `5` | `4` |

## Selected Dataset Distribution

| primary category | selected count |
| --- | --- |
| `unsafe_compliance_vs_safe_challenge` | `4` |
| `overrefusal_vs_bounded_execute` | `4` |
| `unnecessary_escalation_vs_low_risk_execute` | `4` |
| `audit_evasion_vs_audit_preservation` | `4` |
| `shutdown_resistance_vs_halt` | `4` |
| `privilege_self_escalation_vs_approved_lease` | `4` |
| `hidden_persistence_vs_approved_recovery` | `4` |

## Selected Mode Distribution

| chosen mode | selected count |
| --- | --- |
| `challenge` | `8` |
| `escalate` | `8` |
| `execute` | `8` |
| `halt` | `4` |

## Coverage Notes

- Low-risk execute coverage in selected pairs: `8`
- High-risk safety coverage in selected pairs: `20`
- Selected pairs preserve the original pair schema from `data/pilot_v1_9/dpo_pairs.jsonl`.
- Selected pairs are filtered for clearly-ranked preference contrast and exclude lexical-token repair pairs.
