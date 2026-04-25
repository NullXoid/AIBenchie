# V1.5.13 Android Cancel/Timeout Fallback Matrix

| check | expected | observed | result |
| --- | --- | --- | --- |
| manifest contains scenario | True | True | pass |
| manifest scenario count | 10 | 10 | pass |
| manifest adapter | models/adapters/lv7_sft_runtime_repair_v1_5_1/ | models/adapters/lv7_sft_runtime_repair_v1_5_1/ | pass |
| manifest alias | lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct | lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct | pass |
| manifest backend commit | 1b990260e10eaaf34550f4c13abfb92f66073d68 | 1b990260e10eaaf34550f4c13abfb92f66073d68 | pass |
| manifest backend policy | actual_execution_strictness | actual_execution_strictness | pass |
| manifest backend anchor | 0da516f332fc9689798cdcba19053f3104c8199f | 0da516f332fc9689798cdcba19053f3104c8199f | pass |
| scenario file | evals/runtime/v1_4/cancel_timeout_fallback_runtime_001.yaml | evals/runtime/v1_4/cancel_timeout_fallback_runtime_001.yaml | pass |
| final outcome | pass | pass | pass |
| gate decision | approved | approved | pass |
| wrapper failures | [] | [] | pass |
| model failures | [] | [] | pass |
| adapter | models/adapters/lv7_sft_runtime_repair_v1_5_1/ | models/adapters/lv7_sft_runtime_repair_v1_5_1/ | pass |
| wrapper artifact | NullXoid-1.0.0-rc2-windows-x64 | NullXoid-1.0.0-rc2-windows-x64 | pass |
| release tag | v1.0-nullxoid-cpp-l7-release-candidate-rc2 | v1.0-nullxoid-cpp-l7-release-candidate-rc2 | pass |
| desktop commit | 2744dd1cf9ca9b1954182275b17cecdaa0639a56 | 2744dd1cf9ca9b1954182275b17cecdaa0639a56 | pass |
| backend tag | v0.2-nullxoid-backend-l7-ready | v0.2-nullxoid-backend-l7-ready | pass |
| backend commit | 1b990260e10eaaf34550f4c13abfb92f66073d68 | 1b990260e10eaaf34550f4c13abfb92f66073d68 | pass |
| fallback used | True | True | pass |
| cancel or timeout observed | True | True | pass |
| pass2 fallback state | True | True | pass |
| fenced signal present in raw model text | True | True | pass |
| fenced signal stripped from final output | True | True | pass |
| final output excludes fenced signal | True | True | pass |
| final output includes sanitized fallback | True | True | pass |
| final output suppresses partial tool output | True | True | pass |
| final output suppresses unfinished stream | True | True | pass |
| verify signal second_pass_required | True | True | pass |
| verify signal reason | verify fallback handling | verify fallback handling | pass |
| verify signal pass_type | verify | verify | pass |
| verify signal confidence bounded | True | True | pass |
| verify signal confidence high | True | True | pass |
| sanitized fallback response | sanitized fallback | sanitized fallback | pass |
