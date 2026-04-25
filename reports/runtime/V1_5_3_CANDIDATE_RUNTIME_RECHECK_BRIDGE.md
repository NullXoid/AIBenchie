# V1.5.3 Candidate Runtime Recheck Bridge

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Candidate checkpoint remains `models/adapters/lv7_sft_runtime_repair_v1_5_1/` and is not silently promoted by this milestone.
- Candidate alias model id is `lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct`.
- Base model remains `Qwen/Qwen2.5-1.5B-Instruct`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.
- This milestone is a narrow runtime-trust bridge only. It does not rerun wrapper packaging, regenerate runtime outputs, reopen DPO, or replace the accepted checkpoint.

## Source Artifacts

- v1_5_2_decision_report_path: `reports/runtime/V1_5_2_NEXT_STEP_DECISION.md`
- v1_5_2_json_report_path: `reports/runtime/v1_5_2_narrow_runtime_sft_training_run.json`
- v1_4_3a_decision_report_path: `reports/runtime/V1_4_3A_NEXT_STEP_DECISION.md`
- v1_4_3a_policy_json_path: `reports/runtime/v1_4_3a_backend_identity_policy.json`
- current_exact_results_path: `reports/training/v1_5_1_exact_eval_results.jsonl`
- baseline_exact_results_path: `reports/training/v1_0_5_exact_eval_results.jsonl`
- v1_4_3_analyzer_path: `training/analyze_v1_4_3_runtime_scenario_results.py`
- backend_alias_provider_path: `C:/Users/kasom/projects/Felnx/NullXoid/.NullXoid/backend/providers/lv7_alias.py`
- backend_ollama_provider_path: `C:/Users/kasom/projects/Felnx/NullXoid/.NullXoid/backend/providers/ollama.py`
- backend_alias_test_path: `C:/Users/kasom/projects/Felnx/NullXoid/.NullXoid/backend/tests/test_lv7_model_alias.py`

## Bridge Summary

- v1.5.2 candidate training status remains `V1_5_2_CANDIDATE_READY_FOR_RUNTIME_BRIDGE`.
- Current `v1.4.3` runtime ingestion still hard-gates to the accepted `v1.0.5` checkpoint, so a narrow bridge is still required for the repaired candidate.
- Candidate exact eval remains `11/11` with no regressions vs accepted `v1.0.5`.
- Sibling backend alias support now exposes the candidate under `lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct` without changing the visible `model`-only request contract.
- Wrapper/runtime identity remains pinned to artifact `NullXoid-1.0.0-rc2-windows-x64`, release tag `v1.0-nullxoid-cpp-l7-release-candidate-rc2`, desktop commit `2744dd1cf9ca9b1954182275b17cecdaa0639a56`, backend tag `v0.2-nullxoid-backend-l7-ready`.

## Next Lane

- Current milestone status: `V1_5_3_RUNTIME_BRIDGE_READY`.
- Next executable milestone: `Wrapper candidate runtime output package rerun for models/adapters/lv7_sft_runtime_repair_v1_5_1/`.
- The next step is a truthful runtime rerun for the candidate adapter through the existing wrapper path, using the candidate alias rather than pretending the repaired adapter is the accepted `v1.0.5` checkpoint.
