# LV7 SFT Patch Plan

## Status

- Current status label: `READY_FOR_WSL2_SMOKE`
- Repository deliverable state: `READY_FOR_WSL2_SMOKE`
- Chosen base model: `Qwen/Qwen2.5-1.5B-Instruct`
- Trainable target remains fixed for the current patch run: `Qwen/Qwen2.5-1.5B-Instruct`
- Same-base comparison required: `Qwen base raw -> v1.0.5 tiny lexical-retention SFT patch raw`
- Same-base historical comparison set: `v0.5 SFT smoke, v0.6 SFT patch, v0.7 SFT patch, v0.8 SFT patch, v1.0 paraphrase SFT patch, v1.0.2 token-targeted paraphrase SFT patch, v1.0.3 ambiguity mode-stability micro patch`
- Immediate regression guard baseline: `v1.0.3 ambiguity mode-stability micro patch`
- Cross-base caveat: `Gemma 4 remains inference-only baseline and is cross-base historical context only.`

## Probe Results

- Host OS: `Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39`
- Host Python: `3.12.3`
- WSL distro: `Ubuntu-24.04`
- WSL available: `True`
- Repo path expected in WSL: `/mnt/c/Users/kasom/projects/Lv7`
- Repo reachable in WSL: `True`
- Venv path: `~/.venvs/lv7-sft`
- HF cache: `~/.cache/huggingface`
- `python3 -m pip` available: `True`
- `python3 -m venv` available: `True`
- GPU visible: `True`
- GPU name: `NVIDIA GeForce RTX 3090`
- GPU VRAM MiB: `24575`
- CUDA ready in torch: `True`
- bitsandbytes import ready: `True`
- 4-bit NF4 config ready: `True`
- Minimal model load ready: `True`

## Dependency Plan

- Bootstrap inside WSL2 only.
- Keep the virtual environment at `~/.venvs/lv7-sft`.
- Keep `HF_HOME=~/.cache/huggingface` and `TRANSFORMERS_CACHE=~/.cache/huggingface/transformers` outside the repo.
- Required Python packages for the patch run: `pip`, `setuptools`, `wheel`, `numpy`, `torch`, `transformers`, `datasets`, `peft`, `accelerate`, `bitsandbytes`, `sentencepiece`.
- Save LoRA adapter weights only under `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Main evaluation remains replay-only and uses raw prompts for the primary SFT patch result.

## Current Outcome

- This milestone implements scripts, config, docs, tests, and plan reporting for the SFT patch path.
- It does not run DPO, does not train Ollama models, and does not modify `evals/run_eval.py` to call live models.
