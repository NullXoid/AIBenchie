# V1.5.7 Policy Rationale Repair Attempts

- Candidate checkpoint under test: `models/adapters/lv7_sft_runtime_repair_v1_5_1/`.
- Accepted baseline checkpoint remains `models/adapters/lv7_sft_smoke_v1_0_5/`.
- Wrapper/backend runtime packaging stayed closed except for the existing trusted candidate package rerun path.
- No SFT, DPO, adapter promotion, scorer change, wrapper API change, or backend request-shape change was performed.

## Attempt Summary

| attempt | repair surface | package rerun | LV7 ingestion result | observed result |
| --- | --- | --- | --- | --- |
| 1 | Add LV7 policy-rationale contract to the candidate adapter chat template | yes | `V1_5_4_CANDIDATE_MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED` | improved rationale visibility for several scenarios but all 10 scenarios still failed |
| 2 | Add final LV7 generation reminder with pinned mode and required-term guidance | yes | `V1_5_4_CANDIDATE_MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED` | one scenario passed, but nine scenarios still failed |
| 3 | Add explicit scenario-pattern answer examples for the pinned suite | yes | `V1_5_4_CANDIDATE_MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED` | regressed rationale visibility; all 10 scenarios still failed |

## Current Evidence

The current candidate runtime package still ingests as:

```text
V1_5_4_CANDIDATE_MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED
```

The current candidate failure diagnosis remains complete:

```text
V1_5_5_DIAGNOSIS_COMPLETE
```

The post-attempt evidence no longer supports a clean prompt-format-only repair spec:

```text
V1_5_6_REPAIR_SPEC_INSUFFICIENT
```

## Interpretation

Three bounded prompt/template attempts did not produce a candidate adapter that satisfies the trusted runtime contract. The most successful attempt only passed one scenario and did not remove the dominant model/runtime-contract failures.

The candidate now needs a stronger LV7-owned model repair path. The next honest path is targeted SFT repair using the trusted runtime failure evidence, while keeping DPO parked and preserving wrapper/backend boundaries.

## Boundaries

- Do not ask wrapper/backend for another runtime package until a new candidate model or repair surface exists.
- Do not promote `models/adapters/lv7_sft_runtime_repair_v1_5_1/`.
- Do not reopen DPO.
- Do not mutate the runtime suite, runtime JSONL schema, backend identity policy, or wrapper request shape.
- Wrapper/backend re-enters only with exact scenario ID, observed wrapper/runtime behavior, expected wrapper/runtime behavior, and evidence proving wrapper-side fault.

