# V1.5.11 Identity Reference Audit

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
