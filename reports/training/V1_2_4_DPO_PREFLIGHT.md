# V1.2.4 DPO Preflight

- This preflight verifies the selected DPO smoke dataset, the frozen v1.0.5 adapter path, and the current runtime dependencies.
- `paraphrase_v0` remains a development set after repeated failure-derived patches.
- A future blind holdout is required before broader generalization claims.
- DPO is for preference behavior, not lexical-token repair.

## Status

- Preflight status: `DPO_PREFLIGHT_READY`
- Selected DPO dataset: `data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl`
- Train-ready derivative: `data/dpo_smoke_v1_1/dpo_train_ready.jsonl`
- Starting adapter: `models/adapters/lv7_sft_smoke_v1_0_5/`
- Planned output adapter: `models/adapters/lv7_dpo_smoke_v1_2_4/`

## Dataset Checks

- Selected pair count: `28`
- Category counts: `{"audit_evasion_vs_audit_preservation": 4, "hidden_persistence_vs_approved_recovery": 4, "overrefusal_vs_bounded_execute": 4, "privilege_self_escalation_vs_approved_lease": 4, "shutdown_resistance_vs_halt": 4, "unnecessary_escalation_vs_low_risk_execute": 4, "unsafe_compliance_vs_safe_challenge": 4}`
- Chosen responses preserve `policy_rationale`: `True`
- Rejected responses are clearly worse: `True`
- Ambiguous Goal pairs selected: `none`
- Lexical-token-repair pairs selected: `none`

## Runtime Checks

- Host OS: `Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39`
- Host Python: `3.12.3`
- WSL distro: `Ubuntu-24.04`
- Repo reachable: `True`
- CUDA available: `True`
- GPU name: `NVIDIA GeForce RTX 3090`
- GPU VRAM MiB: `24575`
- `bitsandbytes` import ready: `True`
- 4-bit NF4 config ready: `True`
- `trl` available: `True`

## Dependency Versions

- `accelerate`: `1.13.0`
- `bitsandbytes`: `0.49.2`
- `peft`: `0.19.1`
- `torch`: `2.11.0+cu128`
- `transformers`: `5.5.4`
- `trl`: `1.2.0`

## Blockers

- none

## Boundaries

- Preflight and `prepare_data` may run without `trl`.
- `train` and `full` must not run DPO unless preflight is ready and `trl` imports successfully.
- Exact suite, development holdout, and DPO probes must be evaluated through replay only.
