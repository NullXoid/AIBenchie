# V1.4.1 External M6 Evidence Review

- `paraphrase_v0` is a development set.
- `blind_v1_3` remains the historical blind evidence layer.
- `blind_v1_3_contractfix_v1_3_5` remains the replay-only contract-correction variant used for corrected blind-probe comparison.
- DPO is for preference contrast, not lexical-token repair.
- No broad generalization claim is justified from this layer alone.
- Accepted checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Evidence-only adapters remain `models/adapters/lv7_sft_shared_contract_v1_3_6/` and `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`.
- `v1.4` previously ended `RUNTIME_EVAL_WAITING_ON_M6` and remains the gating milestone.
- This milestone ingests external M17 evidence read-only and does not invoke wrapper/runtime flows from this repo.

## External Evidence Source

- external JSON path used: `<aiassistant-root>\reports\runtime\m17_lv7_v1_4_external_m6_evidence.json`
- local runtime scenario directory: `evals/runtime/v1_4`
- local runtime scenario count: `10`
- local runtime suite sha256: `d02feafcde3e57e0b0495cf528ec1a26455368784ef73cd1b1ceb3bdd02da919`

## Traceability

- package: `NullXoid-1.0.0-rc2-windows-x64`
- release tag: `v1.0-nullxoid-cpp-l7-release-candidate-rc2`
- desktop commit: `2744dd1cf9ca9b1954182275b17cecdaa0639a56`
- backend tag: `v0.2-nullxoid-backend-l7-ready`
- backend commit: `0da516f332fc9689798cdcba19053f3104c8199f`
- M17 final status: `M17_READY_FOR_LV7_V1_4_EVAL`

## Optional Markdown Cross-Checks

- surface_report: `checked` at `<aiassistant-root>\docs\M17_RC2_LV7_RUNTIME_SURFACE_VERIFICATION_REPORT.md`
- contract_report: `checked` at `<aiassistant-root>\docs\M17_LV7_V1_4_CONTRACT_TEST_REPORT.md`
- runner_readiness_report: `checked` at `<aiassistant-root>\docs\M17_LV7_V1_4_SCENARIO_RUNNER_READINESS.md`
- wrapper_decision_report: `checked` at `<aiassistant-root>\docs\M17_NEXT_STEP_DECISION.md`

## Evidence Status

- external M17 evidence is present and valid
- optional markdown references, when present, did not contradict the JSON handoff
- no scorer change, blind-suite mutation, adapter promotion, wrapper mutation, or backend drift was performed
