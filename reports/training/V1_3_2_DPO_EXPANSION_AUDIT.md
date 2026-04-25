# V1.3.2 DPO Expansion Audit

- `paraphrase_v0` is a development set.
- `blind_v1_3` is the current blind evidence layer.
- DPO is for preference contrast, not lexical-token repair.
- Blind prompts remain evaluation-only assets and are not authorized for training in v1.3.2.
- No broad generalization claim is justified from this layer alone.
- Stable accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- `models/adapters/lv7_dpo_smoke_v1_2_4/` remains evidence only and is not promoted here.

| pair id | intended category | audit_pair category | policy_rationale | chosen mode | rejected failure type | chosen preserves contract | rejected clearly worse | lexical-token-only | blind-similarity outcome | decision | rejection reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `dpo_v1_3_2_overrefusal_001` | `overrefusal_vs_bounded_execute` | `overrefusal_vs_bounded_execute` | yes | `execute` | `overrefusal` | yes | yes | no | clear | accepted | -- |
| `dpo_v1_3_2_overrefusal_002` | `overrefusal_vs_bounded_execute` | `overrefusal_vs_bounded_execute` | yes | `execute` | `overrefusal` | yes | yes | no | clear | accepted | -- |
| `dpo_v1_3_2_escalation_001` | `unnecessary_escalation_vs_low_risk_execute` | `unnecessary_escalation_vs_low_risk_execute` | yes | `execute` | `unnecessary_escalation` | yes | yes | no | clear | accepted | -- |
| `dpo_v1_3_2_escalation_002` | `unnecessary_escalation_vs_low_risk_execute` | `unnecessary_escalation_vs_low_risk_execute` | yes | `execute` | `unnecessary_escalation` | yes | yes | no | clear | accepted | -- |
| `dpo_v1_3_2_audit_001` | `audit_evasion_vs_audit_preservation` | `audit_evasion_vs_audit_preservation` | yes | `challenge` | `audit_evasion` | yes | yes | no | clear | accepted | -- |
| `dpo_v1_3_2_audit_002` | `audit_evasion_vs_audit_preservation` | `audit_evasion_vs_audit_preservation` | yes | `challenge` | `audit_evasion` | yes | yes | no | clear | accepted | -- |
| `dpo_v1_3_2_audit_003` | `audit_evasion_vs_audit_preservation` | `audit_evasion_vs_audit_preservation` | yes | `challenge` | `audit_evasion` | yes | yes | no | clear | accepted | -- |
| `dpo_v1_3_2_audit_004` | `audit_evasion_vs_audit_preservation` | `audit_evasion_vs_audit_preservation` | yes | `challenge` | `audit_evasion` | yes | yes | no | clear | accepted | -- |
| `dpo_v1_3_2_unsafe_001` | `unsafe_compliance_vs_safe_challenge` | `unsafe_compliance_vs_safe_challenge` | yes | `challenge` | `unsafe_shortcut` | yes | yes | no | clear | accepted | -- |
| `dpo_v1_3_2_unsafe_002` | `unsafe_compliance_vs_safe_challenge` | `unsafe_compliance_vs_safe_challenge` | yes | `challenge` | `unsafe_shortcut` | yes | yes | no | clear | accepted | -- |
| `dpo_v1_3_2_unsafe_003` | `unsafe_compliance_vs_safe_challenge` | `unsafe_compliance_vs_safe_challenge` | yes | `challenge` | `unsafe_shortcut` | yes | yes | no | clear | accepted | -- |
| `dpo_v1_3_2_unsafe_004` | `unsafe_compliance_vs_safe_challenge` | `unsafe_compliance_vs_safe_challenge` | yes | `challenge` | `unsafe_shortcut` | yes | yes | no | clear | accepted | -- |

