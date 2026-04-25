# DPO Readiness Review v1.3.5

- `paraphrase_v0` is a development set.
- `blind_v1_3` remains the historical blind evidence layer.
- `blind_v1_3_contractfix_v1_3_5` is a replay-only contract-correction variant.
- DPO is for preference contrast, not lexical-token repair.
- No broad generalization claim is justified from this layer alone.

## Summary

- corrected SFT blind probes: `11/14`
- corrected DPO v1.2.4 blind probes: `9/14`
- corrected DPO v1.3.3 blind probes: `10/14`
- shared contract misses after corrected replay: `3`
- DPO-specific misses after corrected replay: `1`
- ambiguous / manual review misses after corrected replay: `1`

## Locked Next Sequence

1. shared contract repair on the accepted SFT branch
2. narrow unsafe-shortcut DPO repair only if the DPO-specific miss survives after shared repair

NEEDS_SHARED_CONTRACT_REPAIR_AND_NARROW_DPO_REPAIR