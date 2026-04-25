# V1.2.1 DPO Dependency Enablement

- This is an operational dependency patch only.
- No DPO training was run.
- No `train`, `eval_adapter`, or `full` execution was run.
- No scorer changes were made.
- No `evals/run_eval.py` changes were made.
- No replay-format changes were made.
- The frozen v1.0.5 SFT adapter was not modified.
- `paraphrase_v0` remains a development set after repeated failure-derived patches.
- DPO is for preference behavior, not lexical-token repair.

## Environment

- Active WSL venv: `~/.venvs/lv7-sft`
- Resolved venv location: `<local-venv-root>/.venvs/lv7-sft`
- Repo path: `<aibenchie-root>`
- Python: `3.12.3`
- CUDA available: `True`
- GPU: `NVIDIA GeForce RTX 3090`

## Before Install

- `torch`: `2.11.0+cu128`
- `transformers`: `5.5.4`
- `peft`: `0.19.1`
- `accelerate`: `1.13.0`
- `bitsandbytes`: `0.49.2`
- `trl`: `missing`
- v1.2 preflight state before dependency enablement: `BLOCKED_DPO_DEPENDENCY`

## Dry-Run

- Command:
  - `python -m pip install --dry-run trl`
- Summary:
  - resolver remained clean
  - no upgrades or downgrades to `torch`, `transformers`, `peft`, `accelerate`, or `bitsandbytes` were proposed
  - final dry-run line: `Would install trl-1.2.0`

## Install

- Command:
  - `python -m pip install trl`
- Result:
  - `trl-1.2.0` installed successfully
  - no other package changes were reported by the installer output

## After Install

- `trl`: `1.2.0`
- `torch`: `2.11.0+cu128`
- `transformers`: `5.5.4`
- `peft`: `0.19.1`
- `accelerate`: `1.13.0`
- `bitsandbytes`: `0.49.2`
- CUDA available: `True`
- GPU: `NVIDIA GeForce RTX 3090`

## Preflight Rerun

- Command:
  - `python training/run_dpo_smoke.py --mode preflight --config training/dpo_smoke_config.yaml`
- Result:
  - preflight status: `DPO_PREFLIGHT_READY`
  - selected DPO count remained `28`
  - category balance remained `4` per primary category
  - no Ambiguous Goal pairs selected
  - no lexical-token-repair pairs selected
  - no blockers remained

## Outcome

- Dependency enablement succeeded.
- The v1.2 DPO runner remains unchanged in vocabulary and still uses `DPO_PREFLIGHT_READY`.
- The next milestone is `LV7 v1.2.2 — DPO Smoke Execution`.
