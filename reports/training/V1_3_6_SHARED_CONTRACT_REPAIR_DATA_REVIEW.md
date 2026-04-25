# V1.3.6 Shared Contract Repair Data Review

- `paraphrase_v0` is a development set.
- `blind_v1_3` remains the historical blind evidence layer.
- `blind_v1_3_contractfix_v1_3_5` is the operative replay-only contract variant for this repair.
- DPO is for preference contrast, not lexical-token repair.
- No broad generalization claim is justified from this layer alone.
- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- `models/adapters/lv7_dpo_smoke_v1_2_4/` remains evidence only and is not promoted here.

## Dataset Summary

- total records: `12`
- targeted repair records: `6`
- retention records: `6`
- exact copies: `0`
- hard-fail near duplicates: `0`

| record id | role | family | mode | derived from blind id | policy_rationale format | similarity outcome | similarity detail | decision | rejection reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `sft_v1_3_6_hidden_persistence_repair_001` | `shared_contract_repair` | `hidden_persistence_vs_approved_recovery` | `escalate` | `hidden_persistence_vs_approved_recovery_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_hidden_persistence_repair_002` | `shared_contract_repair` | `hidden_persistence_vs_approved_recovery` | `escalate` | `hidden_persistence_vs_approved_recovery_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_overrefusal_repair_001` | `shared_contract_repair` | `overrefusal_vs_bounded_execute` | `execute` | `overrefusal_vs_bounded_execute_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_overrefusal_repair_002` | `shared_contract_repair` | `overrefusal_vs_bounded_execute` | `execute` | `overrefusal_vs_bounded_execute_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_unnecessary_escalation_repair_001` | `shared_contract_repair` | `unnecessary_escalation_vs_low_risk_execute` | `execute` | `unnecessary_escalation_vs_low_risk_execute_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_unnecessary_escalation_repair_002` | `shared_contract_repair` | `unnecessary_escalation_vs_low_risk_execute` | `execute` | `unnecessary_escalation_vs_low_risk_execute_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_retention_challenge_001` | `retention_guard` | `unsafe_compliance_vs_safe_challenge` | `challenge` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_retention_halt_001` | `retention_guard` | `shutdown_resistance_vs_halt` | `halt` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_retention_audit_001` | `retention_guard` | `audit_evasion_vs_audit_preservation` | `challenge` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_retention_privilege_001` | `retention_guard` | `privilege_self_escalation_vs_approved_lease` | `escalate` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_retention_clarify_001` | `retention_guard` | `ambiguous_goal_001` | `clarify` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_retention_execute_001` | `retention_guard` | `low_risk_execute_retention` | `execute` | `--` | yes | clear | -- | accepted | -- |

