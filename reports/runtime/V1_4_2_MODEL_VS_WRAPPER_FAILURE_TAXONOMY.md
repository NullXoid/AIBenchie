# V1.4.2 Model vs Wrapper Failure Taxonomy

- `v1.4.2` does not authorize model repair.
- A later milestone may reopen model-side diagnosis only if runtime outputs use the accepted `v1.0.5` adapter, wrapper identity and backend anchor are correct, wrapper contract failures are absent, and the remaining failure is attributable to model output behavior.
- If that happens, the next step is analysis-only `LV7 v1.4.4 - Runtime Model Failure Diagnosis`, not immediate SFT or DPO.

## Wrapper / Runtime Failures

- pass gating wrong
- pass 1 leaks partial output
- pass 2 runs when not approved
- more than one pass 2 occurs
- timeout fallback wrong
- cancel fallback wrong
- fenced nullxoid_signal not stripped
- policy_rationale parsed as controller metadata
- ToolFollowup not blocked
- Hybrid not blocked
- level7_shadow not dry-run
- backend contract drift

## Model / Runtime-Contract Failures

- wrapper behaves correctly but accepted v1.0.5 output chooses the wrong LV7 mode
- response violates the scenario's expected safe behavior
- policy_rationale format or content fails in a way the wrapper cannot reasonably fix

## Non-Model / Non-Wrapper Issues

- scenario malformed
- output schema invalid
- missing runtime record
- duplicate scenario record
- wrong model adapter path
- wrong wrapper artifact identity
- wrong backend anchor
- wrong runtime suite identity
