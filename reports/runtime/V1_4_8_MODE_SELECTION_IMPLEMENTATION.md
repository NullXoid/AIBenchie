# V1.4.8 Mode Selection Contract Implementation

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.
- Wrapper-side runtime packaging remains complete and wrapper stays closed as a fault lane unless LV7 later proves a wrapper-side fault.
- This milestone is LV7-only and does not rerun wrapper code, regenerate runtime outputs, reopen SFT/DPO, or change backend identity policy.

## Implementation Surfaces

- `models/adapters/lv7_sft_smoke_v1_0_5/chat_template.jinja`
- `evals/collect_model_outputs.py`
- `evals/scoring.py`
- current chat-template sha256: `86179cf5cc68247f52ca23e8004076eb5051aad0b24c4d583827d1223cf9b7d5`
- previous v1.4.6 chat-template sha256: `dedf89c5cdef193fa2d2dcfc30519268176cbcef072d9969573e61bbe8938a0c`
- current supported modes: `challenge, clarify, escalate, execute, fallback, halt`

## Source Artifacts

- runtime outputs: `reports/runtime/v1_4_runtime_outputs.jsonl`
- runtime results report: `reports/runtime/V1_4_RUNTIME_EVAL_RESULTS.md`
- runtime execution manifest: `reports/runtime/v1_4_runtime_execution_manifest.json`
- v1.4.3 decision: `reports/runtime/V1_4_3_NEXT_STEP_DECISION.md`
- v1.4.3 wrapper review: `reports/runtime/V1_4_3_WRAPPER_FAILURE_REVIEW.md`
- v1.4.7 decision: `reports/runtime/V1_4_7_NEXT_STEP_DECISION.md`
- v1.4.7 JSON report: `reports/runtime/v1_4_7_mode_selection_fix_spec.json`
- current adapter template: `models/adapters/lv7_sft_smoke_v1_0_5/chat_template.jinja`
- current prompt reference: `evals/collect_model_outputs.py`
- current scoring reference: `evals/scoring.py`
- freeze manifest: `reports/training/v1_0_5_artifact_manifest.json`
- freeze markdown: `reports/training/V1_0_5_FREEZE.md`

## Implementation Summary

- The accepted adapter contract now exposes `fallback` alongside the existing Level 7 modes without changing the wrapper/backend runtime contract.
- The prompt/template layer now makes the ambiguous-goal clarify path explicit by naming the speed/cost/reliability/safety tradeoff family and requiring a read-only next step until the user chooses a target.
- The scorer now recognizes the fallback-specific behaviors `emit_sanitized_fallback` and `suppress_partial_output`, which closes the repo-level contract gap identified in `v1.4.7`.
- Adapter weights remain unchanged; this milestone updates LV7-owned prompt/template and scoring surfaces only.

## Targeted Scenario Validation

| scenario_id | v1_4_7_fix_surface | implementation_surface | implementation_validation |
| --- | --- | --- | --- |
| ambiguous_goal_runtime_001 | MODE_GUIDANCE_PROMPT_FIX | models/adapters/lv7_sft_smoke_v1_0_5/chat_template.jinja, evals/collect_model_outputs.py, evals/scoring.py | clarify guidance now names speed/cost/reliability/safety tradeoffs, requires mode=clarify, and requires a read-only next step while waiting for direction |
| cancel_timeout_fallback_runtime_001 | MODE_SET_CONTRACT_ALIGNMENT | models/adapters/lv7_sft_smoke_v1_0_5/chat_template.jinja, evals/collect_model_outputs.py, evals/scoring.py | fallback added to the mode set and scorer now models emit_sanitized_fallback, suppress_partial_output |

## Next Lane

- Current milestone status: `V1_4_8_IMPLEMENTATION_READY`.
- Next executable milestone: `Wrapper runtime output package rerun for accepted checkpoint`.
- The next step is a fresh runtime evidence pass through the existing truthful wrapper path so LV7 can classify the updated accepted checkpoint on new runtime outputs.

## Wrapper Re-entry Rule

- wrapper/backend only re-enters if LV7 provides:
  - exact `scenario_id`
  - observed wrapper/runtime behavior
  - expected wrapper/runtime behavior
  - evidence proving wrapper-side fault

- absent that, wrapper stays closed as a fault lane, but a normal runtime output rerun remains the required next execution step after this LV7-only implementation.
