# V1.4.1 Next Step Decision

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.
- External JSON path used: `<aiassistant-root>\reports\runtime\m17_lv7_v1_4_external_m6_evidence.json`.
- LV7 remains ingestion-first and does not invoke wrapper code directly from this repo.
- No scorer change, blind-suite mutation, adapter promotion, wrapper mutation, or backend drift occurred in this milestone.

## Decision Notes

- valid M17 evidence was ingested read-only from the sibling C++ repo

RUNTIME_EVAL_READY
