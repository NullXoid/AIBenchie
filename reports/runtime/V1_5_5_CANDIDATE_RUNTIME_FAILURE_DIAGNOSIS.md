# V1.5.5 Candidate Runtime Failure Diagnosis

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Candidate checkpoint under test remains `models/adapters/lv7_sft_runtime_repair_v1_5_1/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.
- Wrapper-side runtime packaging is complete and the delivered candidate runtime package is the only diagnosis input.
- No trusted wrapper/runtime failures were found in `v1.5.4`.
- This milestone is analysis-only and does not rerun wrapper code, training, scoring, or packaging.

## Source Evidence

- runtime outputs: `reports/runtime/v1_5_runtime_outputs.jsonl`
- runtime results report: `reports/runtime/V1_5_RUNTIME_EVAL_RESULTS.md`
- execution manifest: `reports/runtime/v1_5_runtime_execution_manifest.json`
- v1.5.4 decision: `reports/runtime/V1_5_4_NEXT_STEP_DECISION.md`
- v1.5.4 model review: `reports/runtime/V1_5_4_MODEL_FAILURE_REVIEW.md`
- v1.5.4 wrapper review: `reports/runtime/V1_5_4_WRAPPER_FAILURE_REVIEW.md`

## Diagnostic Summary

- failed scenarios diagnosed: `0`
- passing scenarios carried forward unchanged: `10`
- milestone status: `V1_5_5_DIAGNOSIS_COMPLETE`

## Dominant Failure Categories

| failure_category | count | recommended_next_lane |
| --- | --- | --- |
| NONE | 0 | NONE |

## Recommended Next Lanes

| recommended_next_lane | failed_scenarios |
| --- | --- |
| NONE | 0 |

## Wrapper Re-entry Rule

- wrapper/backend only re-enters if LV7 provides:
  - exact `scenario_id`
  - observed wrapper/runtime behavior
  - expected wrapper/runtime behavior
  - evidence proving wrapper-side fault

- absent that, wrapper stays closed.
