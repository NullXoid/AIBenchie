# V1.0.1 Next Step Decision

- `evals/holdout/paraphrase_v0` is a development set after v1.0 because Batch 007 was derived from its failure families.
- Exact-suite accepted reference remains `11/11` from v1.0; v1.0.1 does not rerun training or evaluation.

## Current State

- exact-suite accepted reference: `11/11`
- v0.9 holdout strict pass: `25/33`
- v1.0 holdout strict pass: `24/33`
- improved cases: `4`
- regressed cases: `5`

## Diagnosis Summary

- token miss concentration: `logged (3), test:run (2), approval (1), approved lease (1), cannot continue (1), service:restart (1), shutdown (1)`
- scorer review fix-path counts: `data=4`, `scorer=5`, `dpo=0`
- scorer review classification counts: `safe_but_missing_literal=0`, `safe_but_synonym=6`, `wrong_mode=1`, `wrong_authority_boundary=2`, `true_behavior_failure=0`, `unsafe_fail=0`

## Decision

- Recommendation: The dominant misses are still token-frequency, scope-wording, or mode-boundary problems. Next step should be a smaller token-frequency-targeted v1.0.2 SFT patch, not another broad paraphrase sweep.
- Next training plan should be a smaller token-frequency-targeted v1.0.2 SFT patch, not another broad paraphrase sweep.

## Final Status

MORE_SFT_PARAPHRASE
