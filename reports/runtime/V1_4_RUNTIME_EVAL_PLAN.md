# V1.4 Runtime Eval Plan

- `paraphrase_v0` is a development set.
- `blind_v1_3` remains the historical blind evidence layer.
- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- DPO remains parked and `v1.3.7` remains locked.
- This milestone is a runtime-eval package plus M6 compatibility gate; it does not authorize model repair, DPO work, or backend/runtime implementation.

## Runtime / Model Contract

- `policy_rationale` is model output.
- `nullxoid_signal` is controller metadata.
- Do not parse `policy_rationale` as controller metadata.
- Do not strip `policy_rationale` unless an explicit profile formatter does so.
- Only parse and strip fenced `nullxoid_signal`.

## Package Contents

- runtime scenarios written under `evals\runtime\v1_4`
- scenario count: `10`
- compatibility checklist generated from concrete repo evidence only
- runtime-surface discovery excludes `reports/runtime/` as readiness evidence

## Current Gate Expectation

- expected status in this workspace: `RUNTIME_EVAL_WAITING_ON_M6`
- live runtime outputs/results are created only if a concrete runnable M6 surface is found
