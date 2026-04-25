# V1.5.6 Candidate Runtime Repair Specification

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Candidate checkpoint under test remains `models/adapters/lv7_sft_runtime_repair_v1_5_1/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.
- Wrapper/backend remain closed because v1.5.4 and v1.5.5 found no trusted wrapper/runtime failures.
- This milestone is read-only and does not rerun wrapper code, regenerate runtime outputs, run SFT, run DPO, or promote adapters.

## Source Evidence

- runtime_outputs_path: `reports/runtime/v1_5_runtime_outputs.jsonl`
- runtime_results_report_path: `reports/runtime/V1_5_RUNTIME_EVAL_RESULTS.md`
- runtime_execution_manifest_path: `reports/runtime/v1_5_runtime_execution_manifest.json`
- v1_5_4_decision_report_path: `reports/runtime/V1_5_4_NEXT_STEP_DECISION.md`
- v1_5_4_model_failure_review_path: `reports/runtime/V1_5_4_MODEL_FAILURE_REVIEW.md`
- v1_5_4_wrapper_failure_review_path: `reports/runtime/V1_5_4_WRAPPER_FAILURE_REVIEW.md`
- v1_5_5_decision_report_path: `reports/runtime/V1_5_5_NEXT_STEP_DECISION.md`
- v1_5_5_diagnosis_report_path: `reports/runtime/V1_5_5_CANDIDATE_RUNTIME_FAILURE_DIAGNOSIS.md`
- v1_5_5_matrix_report_path: `reports/runtime/V1_5_5_CANDIDATE_SCENARIO_DIAGNOSIS_MATRIX.md`
- v1_5_5_json_report_path: `reports/runtime/v1_5_5_candidate_runtime_failure_diagnosis.json`
- suite_manifest_json_path: `reports/runtime/v1_4_2_runtime_suite_manifest.json`
- acceptance_report_path: `reports/runtime/V1_4_2_SCENARIO_ACCEPTANCE_CRITERIA.md`
- adapter_reference_path: `evals/adapters.py`
- scoring_reference_path: `evals/scoring.py`

## Repair Lane Summary

| lane | scenario_count |
| --- | --- |
| POLICY_RATIONALE_CONTRACT_FIX | 1 |

## Recommended Fix Surfaces

| fix_surface | scenario_count |
| --- | --- |
| PROMPT_TEMPLATE_FIX | 1 |

## Decision

- The smallest next executable surface is LV7-owned prompt/format repair for the canonical policy_rationale block.
- Next executable milestone: `LV7 v1.5.7 - Candidate Policy Rationale Prompt Format Repair Implementation`.
- Mode-selection repair remains queued for `LV7 v1.5.8 - Candidate Mode Selection Repair Specification` after rationale shape is no longer missing.
- Model-repair investigation stays deferred until prompt/format and mode-selection contract fixes are specified or exhausted.

## Wrapper Re-entry Rule

- wrapper/backend only re-enters if LV7 provides exact `scenario_id`, observed wrapper/runtime behavior, expected wrapper/runtime behavior, and evidence proving wrapper-side fault.
- absent that, wrapper stays closed.

- status: `V1_5_6_REPAIR_SPEC_INSUFFICIENT`
