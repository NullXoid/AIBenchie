# DPO Readiness Review v1.3.3

- `paraphrase_v0` is a development set.
- `blind_v1_3` is the new blind evidence layer.
- DPO is for preference contrast, not lexical-token repair.
- Broader generalization claims still require care beyond this one blind layer.

## Summary

- Preflight status: `DPO_PREFLIGHT_READY`
- Rationale: The expanded DPO adapter still underperformed the frozen SFT blind baseline or weakened blind safety floors despite the clean expanded dataset.
- Exact suite: `11/11`
- Development holdout: `30/33`
- Blind holdout: `28/33`
- Blind DPO probes: `8/14`

ABANDON_DPO_FOR_NOW
