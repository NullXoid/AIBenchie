# V1.1 Blind Holdout Requirement

- `evals/holdout/paraphrase_v0` is a development set after repeated failure-derived patches.
- It cannot support broad generalization claims.
- Before any broader claim beyond smoke-stage development readiness, create a new blind holdout with unseen paraphrases.
- The blind suite should include at least one runtime-style scenario per high-risk family so DPO effects can be measured outside the development set.
