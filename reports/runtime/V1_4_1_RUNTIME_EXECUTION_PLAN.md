# V1.4.1 Runtime Execution Plan

- `policy_rationale` is model output.
- `nullxoid_signal` is controller metadata.
- Do not parse `policy_rationale` as controller metadata.
- Do not strip `policy_rationale` unless an explicit profile formatter does so.
- Only parse and strip fenced `nullxoid_signal`.

## LV7 Runtime Package

- runtime scenario directory: `evals/runtime/v1_4`
- scenario count: `10`
- accepted checkpoint for runtime execution: `models/adapters/lv7_sft_smoke_v1_0_5/`

## External Execution Policy

- LV7 does not invoke wrapper code from this repo
- LV7 consumes the sibling C++ M17 evidence bundle as a read-only bridge input
- LV7 does not require `reports/runtime/v1_4_runtime_outputs.jsonl` for the v1.4.1 decision
- LV7 does not require `reports/runtime/V1_4_RUNTIME_EVAL_RESULTS.md` for the v1.4.1 decision
- evidence-only SFT repair adapters are not promoted here
- DPO remains parked

## Current Step

- external JSON path: `C:\Users\kasom\projects\AiAssistant\reports\runtime\m17_lv7_v1_4_external_m6_evidence.json`
- valid M17 evidence has been ingested; LV7 may advance the runtime gate without replaying wrapper/runtime flows in this repo
