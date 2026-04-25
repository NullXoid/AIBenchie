# V1.5.11 Post-Promotion Identity Sync

- Status: `V1_5_11_IDENTITY_SYNC_COMPLETE`
- Current accepted runtime checkpoint: `models/adapters/lv7_sft_runtime_repair_v1_5_1/`.
- Current accepted runtime alias: `lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct`.
- Previous accepted checkpoint retained as historical evidence: `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Previous backend-visible alias retained for historical compatibility: `lv7_sft_smoke_v1_0_5:qwen2.5-1.5b-instruct`.
- Base model: `Qwen/Qwen2.5-1.5B-Instruct`.
- Wrapper artifact identity remains `NullXoid-1.0.0-rc2-windows-x64`.
- Release tag remains `v1.0-nullxoid-cpp-l7-release-candidate-rc2`.
- Desktop commit remains `2744dd1cf9ca9b1954182275b17cecdaa0639a56`.
- Backend tag remains `v0.2-nullxoid-backend-l7-ready`.
- Executing backend commit remains `1b990260e10eaaf34550f4c13abfb92f66073d68` under `actual_execution_strictness`.
- Frozen backend anchor remains `0da516f332fc9689798cdcba19053f3104c8199f`.

## Scope

- This milestone synchronizes forward-looking identity references only.
- It does not reopen SFT, DPO, adapter promotion, scorers, blind suites, or scenario definitions.
- It does not rewrite historical v1.4 or v1.5 evidence that correctly referenced the old accepted checkpoint at the time.

## Audit

| check | expected | observed | result |
| --- | --- | --- | --- |
| v1.5.10 decision | V1_5_10_PROMOTION_COMPLETE | V1_5_10_PROMOTION_COMPLETE | pass |
| v1.5.10 JSON status | V1_5_10_PROMOTION_COMPLETE | V1_5_10_PROMOTION_COMPLETE | pass |
| promotion complete | True | True | pass |
| promoted checkpoint | models/adapters/lv7_sft_runtime_repair_v1_5_1/ | models/adapters/lv7_sft_runtime_repair_v1_5_1/ | pass |
| promoted alias | lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct | lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct | pass |
| promoted base model | Qwen/Qwen2.5-1.5B-Instruct | Qwen/Qwen2.5-1.5B-Instruct | pass |
| previous accepted checkpoint preserved | models/adapters/lv7_sft_smoke_v1_0_5/ | models/adapters/lv7_sft_smoke_v1_0_5/ | pass |
| backend accepted alias constant | ACCEPTED_ALIAS_MODEL_ID = "lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct" | present | pass |
| backend previous alias constant | PREVIOUS_ACCEPTED_ALIAS_MODEL_ID = "lv7_sft_smoke_v1_0_5:qwen2.5-1.5b-instruct" | present | pass |
| backend accepted adapter constant | ACCEPTED_ADAPTER_PATH = "models/adapters/lv7_sft_runtime_repair_v1_5_1/" | present | pass |
| backend previous adapter constant | PREVIOUS_ACCEPTED_ADAPTER_PATH = "models/adapters/lv7_sft_smoke_v1_0_5/" | present | pass |
| backend default alias points to accepted | ALIAS_MODEL_ID = ACCEPTED_ALIAS_MODEL_ID | present | pass |
| model registry contains promoted alias | True | True | pass |
| model registry retains previous alias | True | True | pass |
| handoff active accepted checkpoint | accepted runtime checkpoint: `models/adapters/lv7_sft_runtime_repair_v1_5_1/` | present | pass |
| handoff previous checkpoint historical | previous accepted checkpoint retained as historical evidence: `models/adapters/lv7_sft_smoke_v1_0_5/` | present | pass |
| handoff promoted alias | alias model id: `lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct` | present | pass |
| handoff v1.5.10 status | v1.5.10 promotion is complete | present | pass |

## Notes

- forward-looking accepted runtime identity now points to the promoted repair adapter
- previous v1.0.5 identity remains available only as historical compatibility evidence
