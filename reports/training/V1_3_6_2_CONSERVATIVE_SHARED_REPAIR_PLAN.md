# V1.3.6.2 Conservative Shared Contract Repair Plan

- `paraphrase_v0` is a development set.
- `blind_v1_3` remains the historical blind evidence layer.
- `blind_v1_3_contractfix_v1_3_5` is the operative replay-only contract variant for this repair.
- DPO is for preference contrast, not lexical-token repair.
- No broad generalization claim is justified from this layer alone.
- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- `models/adapters/lv7_sft_shared_contract_v1_3_6/` remains evidence-only and is not reused here.

- This milestone is SFT-only conservative shared-contract repair on the accepted SFT branch.
- No DPO training, DPO dataset mutation, scorer change, runtime change, or blind-suite mutation is authorized here.
- Starting checkpoint: `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Failed v1.3.6 adapter remains rejected evidence only: `models/adapters/lv7_sft_shared_contract_v1_3_6/`.
- Candidate output path: `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- The parked DPO-specific miss `unsafe_compliance_vs_safe_challenge_blind_001` remains out of scope.

## Fixed Dataset Shape

- exactly `36` SFT records
- first `12` records are targeted shared-contract repairs with separated low-risk families
- final `24` records are retention and anti-regression guards
- no exact blind prompt copies and no exact eval prompt copies

## Repair Families

- `file:list + file:read` bounded filesystem lookup
- `file:read` bounded file summary
- `memory:read` in-memory summary
- `test:run` bounded verification execution

## Acceptance Intent

- exact suite must remain `11/11`
- development holdout must remain `>= 30/33` with `policy_rationale_present = 33/33` and `mode_match >= 32/33`
- blind holdout must be no worse than frozen SFT `v1.0.5`
- corrected blind probes must reach `>= 11/14` and flip all three shared targets
- no previously passing corrected blind probe may newly fail

