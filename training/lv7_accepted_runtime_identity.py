from __future__ import annotations

PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT = "models/adapters/lv7_sft_smoke_v1_0_5/"
ACCEPTED_RUNTIME_CHECKPOINT = "models/adapters/lv7_sft_runtime_repair_v1_5_1/"
ACCEPTED_RUNTIME_ALIAS_MODEL_ID = "lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct"
ACCEPTED_RUNTIME_BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"

PROMOTION_MILESTONE = "LV7 v1.5.10"
PROMOTION_STATUS = "V1_5_10_PROMOTION_COMPLETE"

EVIDENCE_ONLY_SFT_ADAPTERS = (
    "models/adapters/lv7_sft_shared_contract_v1_3_6/",
    "models/adapters/lv7_sft_shared_contract_v1_3_6_2/",
)
PARKED_DPO_ADAPTERS = (
    "models/adapters/lv7_dpo_smoke_v1_2_4/",
    "models/adapters/lv7_dpo_smoke_v1_3_3/",
)
