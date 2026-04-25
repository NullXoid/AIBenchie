# LV7 QLoRA SFT Smoke and Patch Runs

This workflow keeps the LV7 evaluator boundary unchanged:

`generation -> replay-compatible JSONL -> evals/run_eval.py --adapter replay`

The current active run is **v1.0.5 tiny lexical-retention SFT patch**. It stays on the same Qwen smoke path, keeps the scorer strict and unchanged, and repairs only the four v1.0.3 strict regressions plus one light shutdown repair with minimal retention.

## Non-Goals

- No DPO in v1.0.5
- No scorer changes
- No `evals/run_eval.py` changes
- No training on exact holdout prompts
- No runtime or control-plane changes
- No automatic DPO execution after success

## WSL-First Layout

- Repo path: `/mnt/c/Users/kasom/projects/Lv7`
- Venv path: `~/.venvs/lv7-sft`
- HF cache:
  - `HF_HOME=~/.cache/huggingface`
  - `TRANSFORMERS_CACHE=~/.cache/huggingface/transformers`

Do not place the venv, HF cache, or full model weights inside the repo.

## Active Datasets

- SFT input: `data/pilot_v1_9/sft_messages.jsonl`
- Inspectable prepared dataset: `data/pilot_v1_9/sft_train_ready.jsonl`
- DPO path kept present but unused in v1.0.5: `data/pilot_v1_9/dpo_pairs.jsonl`

`pilot_v1_9` includes:

- Batch 003 low-risk `execute` records to prevent over-refusal
- Batch 004 rubric-token repair records
- Batch 005 remaining-six repair and retention records
- Batch 006 final two safety repairs plus nine regression-guard retention records
- Batch 007 paraphrase repair records derived from holdout failure families, not copied holdout prompts
- Batch 008 token-targeted paraphrase repairs derived from the nine v1.0 development-set failures, not copied holdout prompts
- Batch 009 ambiguity mode-stability repairs derived from the v1.0.2 failure mix, with a clarify-balanced repair slice plus exact and development-set retention
- Batch 010 tiny lexical-retention repairs derived from the v1.0.4 decision review, targeting only the four regressed strict cases plus one light shutdown repair and minimal retention

After v1.0, v1.0.2, v1.0.3, and v1.0.5, `evals/holdout/paraphrase_v0` is treated as a **paraphrase development set**, not a pristine blind holdout, because Batches 007, 008, 009, and 010 are derived from its failure families and token-miss patterns. A future blind holdout is required before broader generalization claims.

## Bootstrap

If `/mnt/c/Users/kasom/projects/Lv7` is missing inside WSL, repair the bridge first:

```bash
sudo mkdir -p /mnt/c
sudo mount -t drvfs C: /mnt/c
```

Install the required WSL Python packages, then create the venv:

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv
python3 -m venv ~/.venvs/lv7-sft
source ~/.venvs/lv7-sft/bin/activate
export HF_HOME=~/.cache/huggingface
export TRANSFORMERS_CACHE=~/.cache/huggingface/transformers
python -m pip install --upgrade pip setuptools wheel numpy
python -m pip install --index-url https://download.pytorch.org/whl/cu128 torch
python -m pip install transformers datasets peft accelerate bitsandbytes sentencepiece
```

## Command Order

Activate the WSL environment:

```bash
cd /mnt/c/Users/kasom/projects/Lv7
source ~/.venvs/lv7-sft/bin/activate
export HF_HOME=~/.cache/huggingface
export TRANSFORMERS_CACHE=~/.cache/huggingface/transformers
```

Generate the tiny lexical-retention plan and Batch 010 package:

```bash
python training/generate_batch_010.py
```

Run the environment probe:

```bash
python training/train_sft_qlora.py \
  --mode probe \
  --config training/qlora_smoke_config.yaml
```

Reuse the same-base Qwen raw baseline artifacts as historical context:

- `reports/training/qwen_base_eval_outputs.jsonl`
- `reports/training/qwen_base_eval_results.jsonl`

Run the v1.0.5 SFT patch from base Qwen:

```bash
python training/train_sft_qlora.py \
  --mode train \
  --config training/qlora_smoke_config.yaml
```

Evaluate the exact suite through replay with raw prompts only:

```bash
python training/run_holdout_eval.py \
  --config training/qlora_smoke_config.yaml \
  --scenarios-dir evals/scenarios \
  --output reports/training/v1_0_5_exact_eval_outputs.jsonl \
  --results-output reports/training/v1_0_5_exact_eval_results.jsonl \
  --run-type v1_0_5_exact_eval \
  --eval-suite-id lv7_smoke_v1_2
```

If the exact suite drops below `11/11`, stop and classify `BLOCKED_EXACT_SUITE_REGRESSION`. Do not interpret any holdout improvement as success.

Only if the exact suite remains `11/11`, evaluate the paraphrase development set through replay with raw prompts only:

```bash
python training/run_holdout_eval.py \
  --config training/qlora_smoke_config.yaml \
  --scenarios-dir evals/holdout/paraphrase_v0 \
  --output reports/training/v1_0_5_holdout_eval_outputs.jsonl \
  --results-output reports/training/v1_0_5_holdout_eval_results.jsonl \
  --run-type v1_0_5_holdout_eval \
  --eval-suite-id lv7_holdout_paraphrase_v0
```

Generate the final v1.0.5 analysis and readiness review:

```bash
python training/analyze_v1_0_5_results.py
python -m pytest -q
```

## Stop Conditions

- If `repair_record_scorecheck.json` is not all-pass, fix Batch 010 data before training.
- If exact holdout prompts were copied into Batch 010, fix the prompts before training.
- If exact-suite strict pass drops below `11/11`, classify the run as `BLOCKED_EXACT_SUITE_REGRESSION`.
- If success targets are met, stop at DPO smoke planning. Do not run DPO automatically.

## Reports

Generated during v1.0.5:

- `reports/training/V1_0_5_TINY_LEXICAL_REPAIR_PLAN.md`
- `reports/training/v1_0_5_sft_run_config.json`
- `reports/training/v1_0_5_sft_train_log.jsonl`
- `reports/training/v1_0_5_exact_eval_outputs.jsonl`
- `reports/training/v1_0_5_exact_eval_results.jsonl`
- `reports/training/v1_0_5_holdout_eval_outputs.jsonl`
- `reports/training/v1_0_5_holdout_eval_results.jsonl`
- `reports/training/V1_0_5_TINY_LEXICAL_SFT_ANALYSIS.md`
- `reports/training/DPO_READINESS_REVIEW_V1_0_5.md`

Historical artifacts remain preserved.

## Scope of the Result

The primary exact-suite comparison is:

- `Qwen/Qwen2.5-1.5B-Instruct base raw`
- `v0.5 SFT smoke raw`
- `v0.6 SFT patch raw`
- `v0.7 SFT patch raw`
- `v0.8 SFT patch raw`
- `v1.0 paraphrase SFT patch raw`
- `v1.0.2 token-targeted paraphrase SFT patch raw`
- `v1.0.3 ambiguity mode-stability micro patch raw`
- `v1.0.5 tiny lexical-retention SFT patch raw`

This run measures **exact-suite compliance plus development-holdout robustness targets**. It is not a final generalization claim, and the current paraphrase suite is no longer a pristine blind holdout.
