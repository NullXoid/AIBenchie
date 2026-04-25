# V1.5.10 Accepted Runtime Repair Promotion

- Status: `V1_5_10_PROMOTION_COMPLETE`
- Previous accepted checkpoint: `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Promoted accepted runtime checkpoint: `models/adapters/lv7_sft_runtime_repair_v1_5_1/`.
- Promoted runtime alias: `lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct`.
- Base model: `Qwen/Qwen2.5-1.5B-Instruct`.
- Wrapper artifact remains `NullXoid-1.0.0-rc2-windows-x64`.
- Release tag remains `v1.0-nullxoid-cpp-l7-release-candidate-rc2`.
- Desktop commit remains `2744dd1cf9ca9b1954182275b17cecdaa0639a56`.
- Backend tag remains `v0.2-nullxoid-backend-l7-ready`.
- Backend commit policy remains `actual_execution_strictness` with executing backend `1b990260e10eaaf34550f4c13abfb92f66073d68`.
- Frozen backend anchor remains `0da516f332fc9689798cdcba19053f3104c8199f` as traceability evidence.

## Boundary

- This milestone promotes by identity and evidence manifest only.
- It does not delete or overwrite the previous v1.0.5 adapter.
- It does not reopen SFT, DPO, blind suites, scorers, wrapper packaging, or backend identity work.
- Evidence-only SFT adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.

## Promotion Evidence

| check | expected | observed | result |
| --- | --- | --- | --- |
| v1.5.4 decision | V1_5_4_CANDIDATE_RUNTIME_PASSED | V1_5_4_CANDIDATE_RUNTIME_PASSED | pass |
| v1.5.5 decision | V1_5_5_DIAGNOSIS_COMPLETE | V1_5_5_DIAGNOSIS_COMPLETE | pass |
| v1.5.9 decision | V1_5_9_CANDIDATE_ACCEPTED_FOR_PROMOTION | V1_5_9_CANDIDATE_ACCEPTED_FOR_PROMOTION | pass |
| v1.5.4 JSON status | V1_5_4_CANDIDATE_RUNTIME_PASSED | V1_5_4_CANDIDATE_RUNTIME_PASSED | pass |
| v1.5.5 JSON status | V1_5_5_DIAGNOSIS_COMPLETE | V1_5_5_DIAGNOSIS_COMPLETE | pass |
| v1.5.8 repair loop status | V1_5_8_TARGETED_REPAIR_COMPLETE | V1_5_8_TARGETED_REPAIR_COMPLETE | pass |
| v1.5.8 final runtime status | V1_5_4_CANDIDATE_RUNTIME_PASSED | V1_5_4_CANDIDATE_RUNTIME_PASSED | pass |
| v1.5.9 JSON status | V1_5_9_CANDIDATE_ACCEPTED_FOR_PROMOTION | V1_5_9_CANDIDATE_ACCEPTED_FOR_PROMOTION | pass |
| v1.5.9 previous accepted checkpoint | models/adapters/lv7_sft_smoke_v1_0_5/ | models/adapters/lv7_sft_smoke_v1_0_5/ | pass |
| v1.5.9 candidate checkpoint | models/adapters/lv7_sft_runtime_repair_v1_5_1/ | models/adapters/lv7_sft_runtime_repair_v1_5_1/ | pass |
| v1.5.9 candidate alias | lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct | lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct | pass |
| candidate runtime record count | 10 | 10 | pass |
| candidate pass count | 10 | 10 | pass |
| candidate fail count | 0 | 0 | pass |
| candidate promotion recommended | True | True | pass |
| candidate not previously promoted | False | False | pass |
| manifest model adapter path | models/adapters/lv7_sft_runtime_repair_v1_5_1/ | models/adapters/lv7_sft_runtime_repair_v1_5_1/ | pass |
| manifest alias model id | lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct | lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct | pass |
| manifest backend commit | 1b990260e10eaaf34550f4c13abfb92f66073d68 | 1b990260e10eaaf34550f4c13abfb92f66073d68 | pass |
| manifest backend policy | actual_execution_strictness | actual_execution_strictness | pass |
| manifest backend anchor | 0da516f332fc9689798cdcba19053f3104c8199f | 0da516f332fc9689798cdcba19053f3104c8199f | pass |

## Notes

- candidate runtime repair passed all ten pinned scenarios and was accepted for promotion
- current accepted runtime identity now points to the v1.5.1 repair adapter

## Result

The candidate checkpoint is now the accepted LV7 runtime checkpoint: `models/adapters/lv7_sft_runtime_repair_v1_5_1/`.
