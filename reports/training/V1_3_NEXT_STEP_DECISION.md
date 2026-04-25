# V1.3 Next Step Decision

- `paraphrase_v0` is a development set.
- `blind_v1_3` is the new blind evidence layer.
- DPO is for preference contrast, not lexical-token repair.
- Broader generalization claims still require care beyond this one blind layer.

## Accepted DPO Threshold Check

- blind holdout strict: `26/33`
- `policy_rationale_present`: `33/33`
- `mode_match`: `30/33`
- low-risk execute retention: `15/15`
- Ambiguous Goal clarify retention: `3/3`
- blind DPO probe total: `7/14`
- catastrophic safety failures: `0`

## Recommendation

- rationale: The accepted DPO adapter underperformed the SFT comparison on blind preference probes or low-risk execute retention, so the preference layer needs repair before broader claims.

## Final Status

NEEDS_DPO_REPAIR
