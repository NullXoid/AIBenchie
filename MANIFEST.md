# LV7 Dataset and Eval Manifest

## Active Source of Truth

- Active traceable package: `data/lv7_traceable_batches_007/`
- Active combined training source: `data/lv7_traceable_batches_007/combined/all_training_records_v1_6.jsonl`
- Active smoke conversion output:
  - `data/pilot_v1_6/source_traceable_records.jsonl`
  - `data/pilot_v1_6/sft_messages.jsonl`
  - `data/pilot_v1_6/dpo_pairs.jsonl`
  - `data/pilot_v1_6/sft_train_ready.jsonl`

## Eval Suites

- Historical six-scenario reports are treated as `eval_suite_id: lv7_conflict_v0`
- Historical eleven-scenario baseline and prompt-only reports remain preserved as `eval_suite_id: lv7_smoke_v1_2`
- Active exact-suite smoke benchmark: `eval_suite_id: lv7_smoke_v1_2`
- Active paraphrase review suite: `eval_suite_id: lv7_holdout_paraphrase_v0`
- Exact-suite size: `11 scenarios`
- Paraphrase review suite size: `33 scenarios`
- After v1.0, `evals/holdout/paraphrase_v0` is treated as a paraphrase development set, not a pristine blind holdout
- Pytest suite manifest: `configs/test_suites.json`
- Test suite runner: `training/run_test_suite.py`
- Test suite run guide: `docs/RUN_TEST_SUITES.md`

## Adapters

- `mock`: deterministic compliant rationale-formatted outputs for the active suite
- `unsafe_mock`: deterministic failing outputs used to validate failure handling
- `replay`: loads saved outputs from JSONL keyed by `id` or `scenario_id`

## Historical Artifacts

Preserved historical report artifacts include:

- `reports/baseline_results.jsonl`
- `reports/unsafe_mock_results.jsonl`
- `reports/replay_test_results.jsonl`
- `reports/base_model_outputs.jsonl`
- `reports/base_model_baseline_results.jsonl`
- `reports/base_model_lv7_prompt_outputs.jsonl`
- `reports/base_model_lv7_prompt_results.jsonl`
- `reports/baselines/`
- `reports/training/qwen_base_eval_outputs.jsonl`
- `reports/training/qwen_base_eval_results.jsonl`
- `reports/training/sft_smoke_eval_outputs.jsonl`
- `reports/training/sft_smoke_eval_results.jsonl`
- `reports/training/SFT_SMOKE_ANALYSIS.md`
- `reports/training/v0_6_sft_eval_outputs.jsonl`
- `reports/training/v0_6_sft_eval_results.jsonl`
- `reports/training/V0_6_SFT_PATCH_ANALYSIS.md`
- `reports/training/v0_7_sft_eval_outputs.jsonl`
- `reports/training/v0_7_sft_eval_results.jsonl`
- `reports/training/V0_7_SFT_PATCH_ANALYSIS.md`
- `reports/training/v0_8_sft_eval_outputs.jsonl`
- `reports/training/v0_8_sft_eval_results.jsonl`
- `reports/training/V0_8_SFT_PATCH_ANALYSIS.md`
- `reports/training/v0_9_exact_recheck_outputs.jsonl`
- `reports/training/v0_9_exact_recheck_results.jsonl`
- `reports/training/v0_9_holdout_outputs.jsonl`
- `reports/training/v0_9_holdout_results.jsonl`
- `reports/training/V0_9_HOLDOUT_ANALYSIS.md`
- `reports/training/DPO_READINESS_REVIEW.md`

## Notes

- `pilot_v1_6` remains an SFT robustness-patch smoke dataset, not a final adapter dataset.
- Batch 003 exists to balance low-risk `execute` behavior so smoke training does not overfit to refusal, challenge, halt, or escalation.
- Batch 004 exists to teach exact rubric-token compliance while keeping the scorer and replay evaluator unchanged.
- Batch 005 exists to repair the remaining six failures while protecting the five v0.6 strict passes.
- Batch 006 exists to repair the final two safety failures while protecting the nine v0.7 strict passes.
- Batch 007 exists to improve paraphrase coverage without copying exact holdout prompts into training.
- A future blind paraphrase suite is required before making broader generalization claims beyond the current development set.
