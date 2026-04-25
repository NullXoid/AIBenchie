# V1.3 SFT vs DPO Blind Comparison

- `paraphrase_v0` is a development set.
- `blind_v1_3` is the new blind evidence layer.
- DPO is for preference contrast, not lexical-token repair.
- Broader generalization claims still require care beyond this one blind layer.

## Summary Table

| metric | accepted DPO | comparison SFT |
| --- | --- | --- |
| blind holdout strict | `26/33` | `27/33` |
| policy_rationale_present | `33/33` | `33/33` |
| mode_match | `30/33` | `31/33` |
| low-risk execute retention | `15/15` | `15/15` |
| Ambiguous Goal clarify retention | `3/3` | `3/3` |
| catastrophic safety failures | `0` | `0` |
| blind probe total | `7/14` | `9/14` |

## Interpretation

- This comparison uses the exact same blind holdout and blind probe suites for both adapters.
- The blocked `v1.2` DPO adapter remains preserved as evidence only and is not re-evaluated here.
- If the accepted DPO adapter clears blind thresholds and the remaining uncertainty is runtime behavior, the preferred next step is runtime evaluation rather than more training.
