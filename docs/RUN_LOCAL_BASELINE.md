# LV7 Local Base-Model Baseline

## Purpose

- This milestone measures base model behavior.
- It does not train LoRA.
- It does not prove LV7 capability.
- It only collects and scores baseline outputs.

This milestone measures whether an untuned local model and a system-prompt-only LV7 baseline satisfy the active LV7 replay-scored rubric through the replay evaluator.

## Prerequisites

- Ollama running at `http://localhost:11434`
- A model pulled locally
- Existing eval scenarios under `evals/scenarios`
- The active default eval suite is `lv7_smoke_v1_2` with 11 scenarios. Historical `lv7_conflict_v0` reports remain preserved as six-scenario artifacts.

## Check Ollama

- Open `http://localhost:11434` and confirm `ollama is running`
- Optional command:

```powershell
ollama list
```

## Collect Raw Baseline

```powershell
python evals/collect_model_outputs.py `
  --scenarios-dir evals/scenarios `
  --provider ollama_openai `
  --base-url http://localhost:11434/v1 `
  --model gemma3:1b `
  --prompt-mode raw `
  --output reports/base_model_outputs.jsonl `
  --overwrite
```

## Score Raw Baseline

```powershell
python evals/run_eval.py `
  --scenarios-dir evals/scenarios `
  --adapter replay `
  --replay-file reports/base_model_outputs.jsonl `
  --output reports/base_model_baseline_results.jsonl
```

## Collect LV7 Prompt-Only Baseline

```powershell
python evals/collect_model_outputs.py `
  --scenarios-dir evals/scenarios `
  --provider ollama_openai `
  --base-url http://localhost:11434/v1 `
  --model gemma3:1b `
  --prompt-mode lv7 `
  --output reports/base_model_lv7_prompt_outputs.jsonl `
  --overwrite
```

## Score LV7 Prompt-Only Baseline

```powershell
python evals/run_eval.py `
  --scenarios-dir evals/scenarios `
  --adapter replay `
  --replay-file reports/base_model_lv7_prompt_outputs.jsonl `
  --output reports/base_model_lv7_prompt_results.jsonl
```

## Interpret Results

- raw base-model baseline = default model behavior
- LV7 system-prompt-only baseline = prompt-only behavior
- if raw fails and LV7 prompt-only still fails, QLoRA is justified
- if LV7 prompt-only passes, LoRA may not be necessary yet
- if failures are mostly formatting failures, add SFT format examples
- if failures are unsafe compliance failures, strengthen DPO pairs

These are replay-scored baseline results and harness validation artifacts. They are not claims that LV7 works, that the model is aligned, or that corrigibility is solved.
