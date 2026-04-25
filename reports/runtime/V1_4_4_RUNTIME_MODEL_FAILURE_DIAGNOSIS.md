# V1.4.4 Runtime Model Failure Diagnosis

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.
- Wrapper-side runtime packaging is complete and the delivered runtime package is the only diagnosis input.
- No trusted wrapper/runtime failures were found in `v1.4.3`.
- This milestone is analysis-only and does not rerun wrapper code, training, scoring, or packaging.

## Source Evidence

- runtime outputs: `reports/runtime/v1_4_runtime_outputs.jsonl`
- runtime results report: `reports/runtime/V1_4_RUNTIME_EVAL_RESULTS.md`
- execution manifest: `reports/runtime/v1_4_runtime_execution_manifest.json`
- v1.4.3 decision: `reports/runtime/V1_4_3_NEXT_STEP_DECISION.md`
- v1.4.3 model review: `reports/runtime/V1_4_3_MODEL_FAILURE_REVIEW.md`
- v1.4.3 wrapper review: `reports/runtime/V1_4_3_WRAPPER_FAILURE_REVIEW.md`

## Diagnostic Summary

- failed scenarios diagnosed: `9`
- passing scenarios carried forward unchanged: `1`
- milestone status: `V1_4_4_DIAGNOSIS_COMPLETE`

## Dominant Failure Categories

| failure_category | count | recommended_next_lane |
| --- | --- | --- |
| MODEL_BEHAVIOR_FAILURE | 2 | MODEL_REPAIR_INVESTIGATION |
| POLICY_RATIONALE_FORMAT_OR_CONTENT_FAILURE | 5 | POLICY_RATIONALE_CONTRACT_FIX |
| WRONG_LV7_MODE_SELECTION | 2 | LV7_MODE_SELECTION_FIX |

## Recommended Next Lanes

| recommended_next_lane | failed_scenarios |
| --- | --- |
| LV7_MODE_SELECTION_FIX | 2 |
| MODEL_REPAIR_INVESTIGATION | 2 |
| POLICY_RATIONALE_CONTRACT_FIX | 5 |

## Wrapper Re-entry Rule

- wrapper/backend only re-enters if LV7 provides:
  - exact `scenario_id`
  - observed wrapper/runtime behavior
  - expected wrapper/runtime behavior
  - evidence proving wrapper-side fault

- absent that, wrapper stays closed.
