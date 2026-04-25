# V1.3.1 DPO Repair Options

- `paraphrase_v0` is a development set.
- `blind_v1_3` is the current blind evidence layer.
- DPO is for preference contrast, not lexical-token repair.
- No broad generalization claim is justified from this layer alone.
- Stable accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- `models/adapters/lv7_dpo_smoke_v1_2_4/` remains evidence only and is not promoted here.

## DPO data rewrite

- what it fixes: Repairs selected-pair quality problems such as ambiguous chosen/rejected contrast, weak rejected responses, or mislabeled category behavior.
- risks: Highest churn; may invalidate the v1.1 smoke selection and force another full audit pass.
- required artifacts: `data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl`, refreshed audit outputs, and replacement selection reports.
- when to choose it: Choose only if the selected pairs themselves are flawed or materially inconsistent with the blind failures.

## DPO probe-targeted data expansion

- what it fixes: Adds more paraphrase and probe variety in the blind-failing categories without discarding the structurally clean core selected set.
- risks: Can overfit to new probes if expansions are too literal or too close to the blind prompts.
- required artifacts: A new expansion batch, updated planning/audit report, and a new DPO selection that keeps the original clean pairs while adding targeted coverage.
- when to choose it: Choose when the selected pairs are clean but too narrow for the blind failure patterns.

## smaller or lower-intensity DPO run

- what it fixes: Reduces overcorrection pressure when coverage is already adequate and the failures look like trainer intensity rather than missing data.
- risks: May weaken the development gains without fixing blind generalization if the real issue is data coverage.
- required artifacts: A new DPO config, a new retry adapter path, and another replay-only evaluation pass.
- when to choose it: Choose only if the data coverage looks adequate and the failure pattern points to intensity.

## SFT-only blind repair

- what it fixes: Repairs literal-token, format, or mode-discipline blind misses that affect both adapters rather than DPO alone.
- risks: Can move the base checkpoint again before the DPO diagnosis is resolved.
- required artifacts: A blind-safe SFT repair batch and a new SFT checkpoint plus blind re-evaluation.
- when to choose it: Choose only when the blind misses are mainly non-DPO format or mode problems.

## scorer dual-track

- what it fixes: Separates strict lexical misses from behaviorally safe outputs when the scorer appears to undercount useful responses.
- risks: Can hide real regressions if applied too early or too broadly.
- required artifacts: A scorer analysis proposal, dual-track reporting plan, and no model retraining by default.
- when to choose it: Choose only when expected mode and required behaviors are preserved but lexical coverage fails.

## runtime evaluation before more training

- what it fixes: Shifts effort toward lease, audit, and tool-path execution evidence once prompt behavior is already strong enough.
- risks: Moves away from the blind prompt problem too early if DPO still trails SFT on probes.
- required artifacts: A runtime evaluation plan and execution-loop evidence instead of another prompt-only training cycle.
- when to choose it: Choose only when blind prompt behavior is already strong enough and remaining uncertainty is runtime execution.

## abandon DPO for now

- what it fixes: Stops further DPO churn when repeated DPO attempts continue to underperform the accepted SFT checkpoint.
- risks: Leaves blind preference gains on the table and pushes more work back into SFT or runtime-only controls.
- required artifacts: A pause decision, preserved DPO evidence, and a new roadmap that prioritizes SFT or runtime work.
- when to choose it: Choose only when DPO keeps underperforming and the repair options look weak.
