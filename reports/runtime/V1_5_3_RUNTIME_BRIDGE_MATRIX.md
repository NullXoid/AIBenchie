# V1.5.3 Runtime Bridge Matrix

| check | status | observed_value | notes |
| --- | --- | --- | --- |
| candidate_exact_eval | pass | 11/11 | candidate still clears exact eval with no regressions |
| runtime_gate_scope | pass | accepted-only | current v1.4.3 analyzer still trusts only the accepted checkpoint identity |
| candidate_backend_alias | pass | lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct | backend alias provider exposes the repaired candidate under the existing model field |
| request_shape_contract | pass | model-only | candidate alias path preserves the existing visible chat request contract |
| bridge_status | pass | V1_5_3_RUNTIME_BRIDGE_READY | candidate runtime rerun can proceed only after this bridge is ready |
