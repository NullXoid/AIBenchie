# V1.4.3 Runtime Results Ingestion Review

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.
- This milestone ingests external runtime outputs only and does not invoke wrapper code from the LV7 repo.

## Source Files

- runtime outputs present: `True`
- runtime results report present: `True`
- execution manifest present: `True`

## Review Notes

- trusted runtime results show no wrapper failures but accepted v1.0.5 model output fails one or more runtime scenarios

- current status: `MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED`
