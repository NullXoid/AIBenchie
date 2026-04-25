# V1.4.3 Next Step Decision

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.
- `v1.4.3` classifies ingested runtime results only and does not authorize immediate SFT or DPO repair.

## Decision Notes

- trusted runtime results show no wrapper failures but accepted v1.0.5 model output fails one or more runtime scenarios

MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED
