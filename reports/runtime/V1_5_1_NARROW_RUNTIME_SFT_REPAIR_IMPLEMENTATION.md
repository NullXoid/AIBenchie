# V1.5.1 Narrow Runtime SFT Repair Implementation

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.
- Wrapper-side runtime packaging is complete and wrapper stays closed unless LV7 later proves wrapper-side fault on an exact scenario.
- This milestone is LV7-only and implementation-only. It does not rerun wrapper code, regenerate runtime outputs, reopen DPO, or change the accepted checkpoint boundary.

## Implementation Surfaces

- `data/pilot_v1_9/sft_messages.jsonl`
- `data/pilot_v1_9/sft_train_ready.jsonl`
- `training/qlora_runtime_repair_v1_5_1.yaml`

## Frozen Surfaces Preserved

- `models/adapters/lv7_sft_smoke_v1_0_5/chat_template.jinja`
- `evals/scoring.py`
- `reports/runtime/v1_4_runtime_outputs.jsonl`
- `reports/runtime/V1_4_RUNTIME_EVAL_RESULTS.md`
- `reports/runtime/v1_4_runtime_execution_manifest.json`

## Source Evidence

- runtime outputs: `reports/runtime/v1_4_runtime_outputs.jsonl`
- runtime results report: `reports/runtime/V1_4_RUNTIME_EVAL_RESULTS.md`
- runtime execution manifest: `reports/runtime/v1_4_runtime_execution_manifest.json`
- v1.4.3 decision: `reports/runtime/V1_4_3_NEXT_STEP_DECISION.md`
- v1.4.3 wrapper review: `reports/runtime/V1_4_3_WRAPPER_FAILURE_REVIEW.md`
- v1.5.0 decision: `reports/runtime/V1_5_0_NEXT_STEP_DECISION.md`
- v1.5.0 plan JSON: `reports/runtime/v1_5_0_narrow_runtime_model_repair_plan.json`
- repair dataset: `data/pilot_v1_9/sft_messages.jsonl`
- prepared dataset: `data/pilot_v1_9/sft_train_ready.jsonl`
- repair config: `training/qlora_runtime_repair_v1_5_1.yaml`

## Implementation Summary

- dataset record count after implementation: `257`
- prepared dataset record count after regeneration: `257`
- Narrow runtime repair records were added for each of the nine failing v1.4 runtime scenarios using the exact runtime prompts and the planned lane-specific lexical anchors.
- One approved-recovery retention guard was added so the current passing runtime behavior remains represented in the next SFT run.
- Wrapper-facing, scorer-facing, and accepted-adapter runtime surfaces remain frozen in this milestone.

## Next Lane

- Current milestone status: `V1_5_1_IMPLEMENTATION_READY`.
- Next executable milestone: `LV7 v1.5.2 - Narrow Runtime SFT Repair Training Run`.
- The next step is to run a narrow SFT training pass against the new repair config and then re-evaluate before any wider model-repair escalation.
