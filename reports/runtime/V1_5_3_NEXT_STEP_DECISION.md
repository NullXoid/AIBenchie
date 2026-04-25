# V1.5.3 Next Step Decision

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Candidate checkpoint remains `models/adapters/lv7_sft_runtime_repair_v1_5_1/` and runtime recheck still requires an explicit bridge rather than a silent promotion.
- The repaired candidate still clears exact eval with no regressions vs accepted `v1.0.5`.
- The sibling backend now exposes `lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct` under the unchanged `model` field.
- The next executable milestone is `Wrapper candidate runtime output package rerun for models/adapters/lv7_sft_runtime_repair_v1_5_1/`.

V1_5_3_RUNTIME_BRIDGE_READY
