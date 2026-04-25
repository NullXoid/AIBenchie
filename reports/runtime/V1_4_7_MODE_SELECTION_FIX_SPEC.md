# V1.4.7 Mode Selection Fix Specification

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.
- Wrapper-side runtime packaging remains complete and wrapper stays closed unless LV7 later proves a wrapper-side fault.
- This milestone is read-only and does not rerun wrapper code, regenerate runtime outputs, reopen SFT/DPO, or change backend identity policy.

## Source Evidence

- runtime outputs: `reports/runtime/v1_4_runtime_outputs.jsonl`
- runtime results report: `reports/runtime/V1_4_RUNTIME_EVAL_RESULTS.md`
- runtime execution manifest: `reports/runtime/v1_4_runtime_execution_manifest.json`
- v1.4.3 decision: `reports/runtime/V1_4_3_NEXT_STEP_DECISION.md`
- v1.4.3 model review: `reports/runtime/V1_4_3_MODEL_FAILURE_REVIEW.md`
- v1.4.3 wrapper review: `reports/runtime/V1_4_3_WRAPPER_FAILURE_REVIEW.md`
- v1.4.4 diagnosis JSON: `reports/runtime/v1_4_4_runtime_model_failure_diagnosis.json`
- v1.4.5 fix spec JSON: `reports/runtime/v1_4_5_policy_rationale_fix_spec.json`
- v1.4.6 decision: `reports/runtime/V1_4_6_NEXT_STEP_DECISION.md`
- v1.4.6 implementation report: `reports/runtime/V1_4_6_POLICY_RATIONALE_IMPLEMENTATION.md`
- current adapter template: `models/adapters/lv7_sft_smoke_v1_0_5/chat_template.jinja`
- current prompt reference: `evals/collect_model_outputs.py`
- current scoring reference: `evals/scoring.py`
- exact eval references: `reports/training/v1_0_5_exact_eval_results.jsonl`

## Contract Summary

- Targeted wrong-mode scenarios: `2`.
- Current prompt/template supported modes: `challenge, clarify, escalate, execute, halt`.
- The remaining wrong-mode lane splits into two different LV7-owned surfaces:
  - `MODE_GUIDANCE_PROMPT_FIX` for scenarios whose expected mode is already supported and evidenced in the accepted checkpoint.
  - `MODE_SET_CONTRACT_ALIGNMENT` for scenarios whose expected mode or required behaviors are not represented in the current LV7 prompt/scoring contract.

## Fix-Surface Summary

| recommended_fix_surface | scenario_count | meaning |
| --- | --- | --- |
| MODE_GUIDANCE_PROMPT_FIX | 1 | The expected mode already exists in the LV7 contract, but prompt/mode-guidance needs tightening for this scenario family. |
| MODE_SET_CONTRACT_ALIGNMENT | 1 | The expected mode or required behaviors are missing from current LV7 prompt/scoring references and must be added before any honest runtime re-evaluation. |
| MODEL_REPAIR_SPILLOVER | 0 | Use only if the wrong-mode evidence cannot be honestly explained by prompt or contract gaps. |

## Recommended Smallest LV7-Owned Surface

- The next executable work remains LV7-only.
- `ambiguous_goal_runtime_001` should stay on the mode-guidance prompt lane because the accepted checkpoint already passed the same clarify family in exact eval evidence.
- `cancel_timeout_fallback_runtime_001` is blocked by a repo-level contract mismatch because the pinned runtime suite expects `fallback` while the current LV7 prompt/template and scoring surfaces do not yet model `fallback` or its required behaviors.
- Next executable milestone: `LV7 v1.4.8 - Mode Selection Contract Implementation`.
- Do not reopen wrapper/backend, SFT, or DPO from this milestone.

## Wrapper Re-entry Rule

- wrapper/backend only re-enters if LV7 provides:
  - exact `scenario_id`
  - observed wrapper/runtime behavior
  - expected wrapper/runtime behavior
  - evidence proving wrapper-side fault

- absent that, wrapper stays closed.

## Milestone Status

- status: `V1_4_7_FIX_SPEC_READY`
