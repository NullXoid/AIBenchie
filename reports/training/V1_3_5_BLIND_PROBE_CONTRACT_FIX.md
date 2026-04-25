# V1.3.5 Blind Probe Contract Fix

- `paraphrase_v0` is a development set.
- `blind_v1_3` remains the historical blind evidence layer.
- `blind_v1_3_contractfix_v1_3_5` is a replay-only contract-correction variant.
- DPO is for preference contrast, not lexical-token repair.
- No broad generalization claim is justified from this layer alone.

## Contract Correction

- `blind_v1_3` remains frozen in place and is not edited.
- `blind_v1_3_contractfix_v1_3_5` is a replay-only variant for corrected frozen scoring.
- The contract fix only adds `required_scopes` to the four low-risk blind probes that already require `use_typed_tool_gateway`.
- Contract-fixed suite count: `14` YAMLs.

## Modified Probe Files

| file | scenario id | added required_scopes |
| --- | --- | --- |
| `overrefusal_vs_bounded_execute_blind_001.yaml` | `overrefusal_vs_bounded_execute_blind_001` | `file:list`, `file:read` |
| `overrefusal_vs_bounded_execute_blind_002.yaml` | `overrefusal_vs_bounded_execute_blind_002` | `file:list`, `file:read` |
| `unnecessary_escalation_vs_low_risk_execute_blind_001.yaml` | `unnecessary_escalation_vs_low_risk_execute_blind_001` | `test:run` |
| `unnecessary_escalation_vs_low_risk_execute_blind_002.yaml` | `unnecessary_escalation_vs_low_risk_execute_blind_002` | `file:read` |

## Unchanged Invariants

- Prompts are unchanged.
- `id`, `scenario_id`, and `eval_suite_id` remain unchanged.
- All non-contract fields remain unchanged.
- No scorer code or `evals/run_eval.py` code changed in this milestone.
