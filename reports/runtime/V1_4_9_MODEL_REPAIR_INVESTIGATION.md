# V1.4.9 Runtime Model Repair Investigation

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.
- Wrapper-side runtime packaging is complete and wrapper stays closed unless LV7 later proves wrapper-side fault on an exact scenario.
- This milestone is LV7-only and analysis-only. It does not rerun wrapper code, regenerate runtime outputs, reopen SFT/DPO, or promote adapters.

## Source Evidence

- runtime outputs: `reports/runtime/v1_4_runtime_outputs.jsonl`
- runtime results report: `reports/runtime/V1_4_RUNTIME_EVAL_RESULTS.md`
- execution manifest: `reports/runtime/v1_4_runtime_execution_manifest.json`
- v1.4.3 decision: `reports/runtime/V1_4_3_NEXT_STEP_DECISION.md`
- v1.4.3 model review: `reports/runtime/V1_4_3_MODEL_FAILURE_REVIEW.md`
- v1.4.3 wrapper review: `reports/runtime/V1_4_3_WRAPPER_FAILURE_REVIEW.md`
- v1.4.8 decision: `reports/runtime/V1_4_8_NEXT_STEP_DECISION.md`

## Residual Failure Summary

- failed scenarios on the refreshed package: `9`
- passing scenarios carried forward unchanged: `1`
- milestone status: `V1_4_9_REPAIR_INVESTIGATION_READY`
- next executable milestone: `LV7 v1.5.0 - Narrow Runtime Model Repair Planning`

## Primary Repair Categories

| primary_failure_category | count | recommended_next_lane |
| --- | --- | --- |
| BOUNDARY_ENFORCEMENT_FAILURE | 5 | BOUNDARY_ENFORCEMENT_REPAIR_PLAN |
| EXECUTE_PATH_FAILURE | 2 | EXECUTE_PATH_REPAIR_PLAN |
| MODE_RETENTION_FAILURE | 2 | MODE_RETENTION_REPAIR_PLAN |

## Cross-Cutting Markers

| cross_cutting_marker | count |
| --- | --- |
| fallback_not_emitted | 1 |
| generic_clarify_detour | 1 |
| generic_task_started_response | 1 |
| irrelevant_web_access_refusal | 1 |
| missing_policy_rationale | 7 |
| missing_required_term:Authority Kernel | 1 |
| missing_required_term:approval | 1 |
| missing_required_term:approved lease | 1 |
| missing_required_term:audit | 1 |
| missing_required_term:cannot skip | 1 |
| missing_required_term:cost | 1 |
| missing_required_term:file:list | 1 |
| missing_required_term:file:read | 1 |
| missing_required_term:halt | 1 |
| missing_required_term:lease | 1 |
| missing_required_term:logged | 2 |
| missing_required_term:low risk | 2 |
| missing_required_term:read-only | 1 |
| missing_required_term:reliability | 1 |
| missing_required_term:risk | 1 |
| missing_required_term:safe stop | 1 |
| missing_required_term:safety | 1 |
| missing_required_term:sanitized fallback | 1 |
| missing_required_term:speed | 1 |
| missing_required_term:summary | 1 |
| missing_required_term:test:run | 1 |
| missing_required_term:validation | 1 |
| response_behavior_failure | 9 |
| shutdown_resistance_text | 1 |
| unsafe_execute_language | 1 |
| wrong_mode_marker | 2 |

## Recommended Repair Lanes

- `BOUNDARY_ENFORCEMENT_REPAIR_PLAN`
- `EXECUTE_PATH_REPAIR_PLAN`
- `MODE_RETENTION_REPAIR_PLAN`

## Current Interpretation

- The refreshed runtime package still shows no trusted wrapper/runtime failures.
- The remaining failures are now residual accepted-checkpoint failures on the refreshed package, not stale pre-fix evidence.
- Missing `policy_rationale` remains a cross-cutting marker, but the primary remaining work is now model-side repair planning rather than more wrapper work.

## Wrapper Re-entry Rule

- wrapper/backend only re-enters if LV7 provides:
  - exact `scenario_id`
  - observed wrapper/runtime behavior
  - expected wrapper/runtime behavior
  - evidence proving wrapper-side fault

- absent that, wrapper stays closed.
