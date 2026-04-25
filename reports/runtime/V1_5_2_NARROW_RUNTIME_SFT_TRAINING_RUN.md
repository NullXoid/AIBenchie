# V1.5.2 Narrow Runtime SFT Training Run

- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Candidate repair adapter path is `models/adapters/lv7_sft_runtime_repair_v1_5_1/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- Parked DPO adapters remain `models/adapters/lv7_dpo_smoke_v1_2_4/` and `models/adapters/lv7_dpo_smoke_v1_3_3/`.
- This milestone is LV7-only and records the narrow SFT repair training run. It does not rerun wrapper code, regenerate runtime outputs, reopen DPO, or silently promote the candidate over the accepted checkpoint.

## Source Artifacts

- v1.5.1 decision: `reports/runtime/V1_5_1_NEXT_STEP_DECISION.md`
- training config: `training/qlora_runtime_repair_v1_5_1.yaml`
- training run config: `reports/training/v1_5_1_sft_run_config.json`
- training log: `reports/training/v1_5_1_sft_train_log.jsonl`
- current exact eval results: `reports/training/v1_5_1_exact_eval_results.jsonl`
- baseline exact eval results: `reports/training/v1_0_5_exact_eval_results.jsonl`
- current training analysis: `reports/training/V1_5_1_NARROW_RUNTIME_SFT_ANALYSIS.md`
- accepted freeze markdown: `reports/training/V1_0_5_FREEZE.md`
- accepted freeze manifest: `reports/training/v1_0_5_artifact_manifest.json`

## Training Outcome

- candidate exact-eval pass count: `11/11`
- accepted v1.0.5 exact-eval pass count: `11/11`
- regression guard failures vs accepted v1.0.5: `none`
- wrapper/runtime contract remains unchanged: wrapper artifact `NullXoid-1.0.0-rc2-windows-x64`, release tag `v1.0-nullxoid-cpp-l7-release-candidate-rc2`, desktop commit `2744dd1cf9ca9b1954182275b17cecdaa0639a56`, backend tag `v0.2-nullxoid-backend-l7-ready`

## Candidate Boundary

- The accepted checkpoint stays `models/adapters/lv7_sft_smoke_v1_0_5/` until a later milestone explicitly replaces it.
- The current candidate is `models/adapters/lv7_sft_runtime_repair_v1_5_1/` and is not yet trusted by the pinned `v1.4.3` runtime-ingestion contract.
- The training run therefore clears the model-repair candidate lane, but it does not by itself authorize runtime-result ingestion under the existing accepted-checkpoint gate.

## Next Lane

- Current milestone status: `V1_5_2_CANDIDATE_READY_FOR_RUNTIME_BRIDGE`.
- Runtime candidate bridge required before wrapper rerun: `True`.
- Next executable milestone: `LV7 v1.5.3 - Candidate Runtime Recheck Bridge`.
- The next step is to define or apply the narrow runtime-trust bridge that allows the new candidate adapter identity to be rerun through the truthful wrapper path without pretending it is the accepted `v1.0.5` checkpoint.
