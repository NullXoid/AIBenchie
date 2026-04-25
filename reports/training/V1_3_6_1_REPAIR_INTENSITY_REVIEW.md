# V1.3.6.1 Repair Intensity Review

- `paraphrase_v0` is a development set.
- `blind_v1_3` remains the historical blind evidence layer.
- `blind_v1_3_contractfix_v1_3_5` remains the replay-only contract-correction variant used for corrected blind-probe comparison.
- DPO is for preference contrast, not lexical-token repair.
- No broad generalization claim is justified from this layer alone.
- `models/adapters/lv7_sft_shared_contract_v1_3_6/` is evidence-only and not an accepted checkpoint.
- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Any future `v1.3.6.2` is not authorized by `v1.3.6.1`; it is only the next proposed executable milestone if supported.

## Frozen Run Characteristics

| signal | frozen value | why it matters |
| --- | --- | --- |
| starting checkpoint | `/mnt/c/Users/kasom/projects/Lv7/models/adapters/lv7_sft_smoke_v1_0_5` | Resumed training perturbed an already accepted adapter rather than fine-tuning from scratch. |
| dataset size | `12` records | A tiny dataset makes every optimizer step relatively high leverage. |
| repair-to-retention ratio | `6 / 6` | Repair pressure was not buffered by materially broader retention coverage. |
| max_steps | `24` | With 12 records and the logged epoch count, this drove the patch through roughly eight passes over the tiny dataset. |
| learning_rate | `5e-5` | A resumed-adapter patch at `5e-5` is aggressive for a 12-record corrective set. |
| observed epochs | `8.0` | The model revisited the same small patch set repeatedly. |
| train loss | `0.1708` final / `0.0075` min | Loss collapse is consistent with fitting the repair set too tightly instead of applying a gentle local correction. |

## Diagnosis

- `v1.3.6` resumed from the accepted `v1.0.5` adapter, so any overshoot directly interfered with accepted behavior rather than being absorbed by a fresh adapter initialization.
- For a `12`-record resumed-SFT patch, `24` steps at `5e-5` was too strong. The logged `8.0` epochs show the candidate cycled through the tiny patch set many times.
- The result fits the observed regressions: one targeted family improved, but unrelated fragile families lost coverage, which is what an over-strong patch looks like when retention is too thin.

## Recommendation Basis

- If a future `v1.3.6.2` is proposed, it should reduce repair intensity relative to `v1.3.6`. That means lower than `5e-5`, fewer than `24` steps, or both. Those are recommendations only, not executed facts.
