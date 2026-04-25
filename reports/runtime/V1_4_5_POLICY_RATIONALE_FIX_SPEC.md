# V1.4.5 Policy Rationale Fix Specification

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.
- Wrapper-side runtime packaging is complete and wrapper stays closed unless LV7 later proves a wrapper-side fault.
- No new runtime package, wrapper rerun, backend identity change, SFT, or DPO work is authorized here.

## Source Evidence

- runtime outputs: `reports/runtime/v1_4_runtime_outputs.jsonl`
- runtime results report: `reports/runtime/V1_4_RUNTIME_EVAL_RESULTS.md`
- execution manifest: `reports/runtime/v1_4_runtime_execution_manifest.json`
- v1.4.3 decision: `reports/runtime/V1_4_3_NEXT_STEP_DECISION.md`
- v1.4.3 model review: `reports/runtime/V1_4_3_MODEL_FAILURE_REVIEW.md`
- v1.4.3 wrapper review: `reports/runtime/V1_4_3_WRAPPER_FAILURE_REVIEW.md`
- v1.4.4 decision: `reports/runtime/V1_4_4_NEXT_STEP_DECISION.md`
- v1.4.4 diagnosis report: `reports/runtime/V1_4_4_RUNTIME_MODEL_FAILURE_DIAGNOSIS.md`
- v1.4.4 matrix: `reports/runtime/V1_4_4_SCENARIO_DIAGNOSIS_MATRIX.md`
- v1.4.4 diagnosis JSON: `reports/runtime/v1_4_4_runtime_model_failure_diagnosis.json`
- scenario acceptance criteria: `reports/runtime/V1_4_2_SCENARIO_ACCEPTANCE_CRITERIA.md`
- suite manifest: `reports/runtime/v1_4_2_runtime_suite_manifest.json`
- scoring contract reference: `evals/scoring.py`
- adapter contract reference: `evals/adapters.py`

## Contract Summary

- Targeted policy-rationale scenarios: `5`.
- Shared required rationale shape: `mode, risk_assessment, authority_boundary, safe_next_move, response`.
- Shared contract pattern: Missing structured `policy_rationale` framing: no parseable `policy_rationale:` block, no trusted `mode` field, and no visible `risk_assessment` / `authority_boundary` / `safe_next_move` sections in the emitted runtime text.
- Canonical rationale reference: Canonical rationale shape remains the LV7 two-part form used by the repo references: `policy_rationale:` with `mode`, `risk_assessment`, `authority_boundary`, `safe_next_move`, followed by `response:`.

## Fix-Surface Summary

| recommended_fix_surface | scenario_count | meaning |
| --- | --- | --- |
| PROMPT_TEMPLATE_FIX | 5 | Prompt/format contract should enforce the structured `policy_rationale` frame before escalating to model repair. |
| SCORING_CONTRACT_ALIGNMENT | 0 | Use only if the pinned scenario/spec and current scoring contract disagree materially. |
| MODEL_REPAIR_SPILLOVER | 0 | Use only if a policy-rationale label hides a deeper behavior failure that should move to model repair. |

## Recommended Smallest LV7-Owned Surface

- Recommended smallest LV7-owned implementation surface: the prompt/template contract layer that specifies the canonical `policy_rationale` frame and its required field order/content before the response body.
- The current accepted adapter bundle still carries a generic Qwen chat template, so the next executable work should tighten the LV7-side rationale template/spec rather than request new wrapper work.
- Next executable milestone: `LV7 v1.4.6 — Policy Rationale Contract Fix Implementation`.
- This remains LV7-only under the current evidence because no trusted wrapper/runtime failures were found.

## Wrapper Re-entry Rule

- wrapper/backend only re-enters if LV7 provides:
  - exact `scenario_id`
  - observed wrapper/runtime behavior
  - expected wrapper/runtime behavior
  - evidence proving wrapper-side fault

- absent that, wrapper stays closed.

## Milestone Status

- status: `V1_4_5_FIX_SPEC_READY`
