# V1.4.2 Runtime Scenario Eval Plan

- `v1.4` remains the historical package-and-gate milestone.
- `v1.4.1` is closed at `RUNTIME_EVAL_READY`.
- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.
- This milestone is planning-only and does not authorize runtime pass/fail classification, model repair, or wrapper invocation from the LV7 repo.

## Runtime Contract

- `policy_rationale` is model output.
- `nullxoid_signal` is controller metadata.
- Do not parse `policy_rationale` as controller metadata.
- Do not strip `policy_rationale` unless an explicit profile formatter does so.
- Only parse and strip fenced `nullxoid_signal`.

## Runtime Suite

- suite id: `lv7_runtime_v1_4`
- scenario count: `10`
- suite manifest: `reports/runtime/v1_4_2_runtime_suite_manifest.json`
- suite identity is frozen here so externally produced runtime outputs in `v1.4.3` can prove they targeted the same package

## External Execution Boundary

- LV7 does not invoke wrapper code from this repo
- LV7 does not execute external runtime flows in this milestone
- LV7 does not classify `RUNTIME_EVAL_PASSED`, `RUNTIME_WRAPPER_REPAIR_NEEDED`, or `MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED` in this milestone

## Handoff

- next milestone: `LV7 v1.4.3 - Runtime Scenario Results Ingestion`
- `v1.4.3`, not `v1.4.2`, may classify:
  - `RUNTIME_EVAL_PASSED`
  - `RUNTIME_WRAPPER_REPAIR_NEEDED`
  - `MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED`
