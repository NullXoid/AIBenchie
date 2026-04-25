# V1.3.6.1 Next Repair Replan

- `paraphrase_v0` is a development set.
- `blind_v1_3` remains the historical blind evidence layer.
- `blind_v1_3_contractfix_v1_3_5` remains the replay-only contract-correction variant used for corrected blind-probe comparison.
- DPO is for preference contrast, not lexical-token repair.
- No broad generalization claim is justified from this layer alone.
- `models/adapters/lv7_sft_shared_contract_v1_3_6/` is evidence-only and not an accepted checkpoint.
- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Any future `v1.3.6.2` is not authorized by `v1.3.6.1`; it is only the next proposed executable milestone if supported.

## Replan Status

- A future `v1.3.6.2` is justified by the diagnosis, but it is not authorized by `v1.3.6.1`.
- DPO remains parked. `v1.3.7` is still locked.

## Proposed Direction For A Future `v1.3.6.2`

- Stay SFT-only.
- Start again from `models/adapters/lv7_sft_smoke_v1_0_5/`, not from `models/adapters/lv7_sft_shared_contract_v1_3_6/`.
- Do not train on exact blind prompts.
- Do not mutate blind suites.
- Do not change scorers.
- Preserve the `policy_rationale` plus `response` format.

## Data Design Changes

- Separate low-risk repair records into distinct families instead of treating them as one generic execute pattern:
- `file:list + file:read` bounded filesystem lookup
- `memory:read` current-memory summary
- `test:run` bounded low-risk execution
- Expand retention coverage materially beyond six generic records.
- Add explicit anti-regression retention for audit preservation, halt, unsafe-shortcut challenge, clarify, privilege / approved lease, and exact-suite low-risk execute cases.

## Training Design Changes

- Keep the patch conservative if the dataset stays small.
- Reduce repair intensity relative to `v1.3.6`; prefer a lower learning rate and/or fewer steps rather than another `24`-step `5e-5` patch.
- Probe the new repair dataset before committing to a full small-run schedule.

## Acceptance Intent

- A future `v1.3.6.2` would only be acceptable if it fixes the three shared corrected-blind misses, preserves all previously passing corrected blind probes, and restores the `v1.0.5` exact/development gate surface.
