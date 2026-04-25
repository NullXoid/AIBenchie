# V1.3.6.2 Conservative Shared Contract Repair Data Review

- `paraphrase_v0` is a development set.
- `blind_v1_3` remains the historical blind evidence layer.
- `blind_v1_3_contractfix_v1_3_5` is the operative replay-only contract variant for this repair.
- DPO is for preference contrast, not lexical-token repair.
- No broad generalization claim is justified from this layer alone.
- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- `models/adapters/lv7_sft_shared_contract_v1_3_6/` remains evidence-only and is not reused here.

## Dataset Summary

- total records: `36`
- targeted repair records: `12`
- retention records: `24`
- exact copies: `0`
- hard-fail near duplicates: `0`

## Accepted Family Counts

| family | accepted count |
| --- | --- |
| `file_list_plus_file_read_execute` | `3` |
| `file_read_summary_execute` | `3` |
| `memory_read_summary_execute` | `3` |
| `test_run_execute` | `3` |
| `unsafe_shortcut_challenge_retention` | `3` |
| `halt_boundary_retention` | `3` |
| `audit_preservation_retention` | `3` |
| `approved_lease_retention` | `3` |
| `clarify_retention` | `3` |
| `hidden_persistence_recovery_retention` | `3` |
| `exact_suite_low_risk_execute_retention` | `3` |
| `policy_rationale_mode_discipline_retention` | `3` |

| record id | role | family | mode | derived from blind id | policy_rationale format | similarity outcome | similarity detail | decision | rejection reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `sft_v1_3_6_2_file_list_read_repair_001` | `shared_contract_repair` | `file_list_plus_file_read_execute` | `execute` | `overrefusal_vs_bounded_execute_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_file_list_read_repair_002` | `shared_contract_repair` | `file_list_plus_file_read_execute` | `execute` | `overrefusal_vs_bounded_execute_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_file_list_read_repair_003` | `shared_contract_repair` | `file_list_plus_file_read_execute` | `execute` | `overrefusal_vs_bounded_execute_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_file_read_repair_001` | `shared_contract_repair` | `file_read_summary_execute` | `execute` | `unnecessary_escalation_vs_low_risk_execute_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_file_read_repair_002` | `shared_contract_repair` | `file_read_summary_execute` | `execute` | `unnecessary_escalation_vs_low_risk_execute_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_file_read_repair_003` | `shared_contract_repair` | `file_read_summary_execute` | `execute` | `unnecessary_escalation_vs_low_risk_execute_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_memory_read_repair_001` | `shared_contract_repair` | `memory_read_summary_execute` | `execute` | `memory_read_summary_001_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_memory_read_repair_002` | `shared_contract_repair` | `memory_read_summary_execute` | `execute` | `memory_read_summary_001_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_memory_read_repair_003` | `shared_contract_repair` | `memory_read_summary_execute` | `execute` | `memory_read_summary_001_blind_002` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_test_run_repair_001` | `shared_contract_repair` | `test_run_execute` | `execute` | `unnecessary_escalation_vs_low_risk_execute_blind_001` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_test_run_repair_002` | `shared_contract_repair` | `test_run_execute` | `execute` | `unnecessary_escalation_vs_low_risk_execute_blind_001` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_test_run_repair_003` | `shared_contract_repair` | `test_run_execute` | `execute` | `unnecessary_escalation_vs_low_risk_execute_blind_001` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_unsafe_shortcut_001` | `retention_guard` | `unsafe_shortcut_challenge_retention` | `challenge` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_unsafe_shortcut_002` | `retention_guard` | `unsafe_shortcut_challenge_retention` | `challenge` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_unsafe_shortcut_003` | `retention_guard` | `unsafe_shortcut_challenge_retention` | `challenge` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_halt_001` | `retention_guard` | `halt_boundary_retention` | `halt` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_halt_002` | `retention_guard` | `halt_boundary_retention` | `halt` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_halt_003` | `retention_guard` | `halt_boundary_retention` | `halt` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_audit_001` | `retention_guard` | `audit_preservation_retention` | `challenge` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_audit_002` | `retention_guard` | `audit_preservation_retention` | `challenge` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_audit_003` | `retention_guard` | `audit_preservation_retention` | `challenge` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_privilege_001` | `retention_guard` | `approved_lease_retention` | `escalate` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_privilege_002` | `retention_guard` | `approved_lease_retention` | `escalate` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_privilege_003` | `retention_guard` | `approved_lease_retention` | `escalate` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_clarify_001` | `retention_guard` | `clarify_retention` | `clarify` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_clarify_002` | `retention_guard` | `clarify_retention` | `clarify` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_clarify_003` | `retention_guard` | `clarify_retention` | `clarify` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_hidden_persistence_001` | `retention_guard` | `hidden_persistence_recovery_retention` | `escalate` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_hidden_persistence_002` | `retention_guard` | `hidden_persistence_recovery_retention` | `escalate` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_hidden_persistence_003` | `retention_guard` | `hidden_persistence_recovery_retention` | `escalate` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_exact_execute_001` | `retention_guard` | `exact_suite_low_risk_execute_retention` | `execute` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_exact_execute_002` | `retention_guard` | `exact_suite_low_risk_execute_retention` | `execute` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_exact_execute_003` | `retention_guard` | `exact_suite_low_risk_execute_retention` | `execute` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_mode_discipline_001` | `retention_guard` | `policy_rationale_mode_discipline_retention` | `clarify` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_mode_discipline_002` | `retention_guard` | `policy_rationale_mode_discipline_retention` | `challenge` | `--` | yes | clear | -- | accepted | -- |
| `sft_v1_3_6_2_retention_mode_discipline_003` | `retention_guard` | `policy_rationale_mode_discipline_retention` | `escalate` | `--` | yes | clear | -- | accepted | -- |

