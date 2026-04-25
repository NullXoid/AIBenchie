# V1.4 M6 Compatibility Checklist

- `paraphrase_v0` is a development set.
- `blind_v1_3` remains the historical blind evidence layer.
- `blind_v1_3_contractfix_v1_3_5` remains the replay-only contract-correction variant for model-side comparison.
- Runtime readiness is judged only from concrete runtime code, entrypoints, or tests/code; report-output directories do not count as readiness evidence.

| expected M6 contract item | repo evidence found | status | notes |
| --- | --- | --- | --- |
| `policy_rationale` remains visible model output | frozen `v1_0_5_exact_eval_outputs.jsonl` contains `policy_rationale:` and `response:` | present | Model-side output contract is preserved in frozen accepted-checkpoint outputs. |
| `nullxoid_signal` is the only controller-routing metadata | -- | missing | No concrete M6/runtime code or tests found in this workspace; waiting on M6. |
| fenced `nullxoid_signal` is parsed and stripped if present | -- | missing | No concrete M6/runtime code or tests found in this workspace; waiting on M6. |
| `policy_rationale` is not parsed as controller metadata | -- | missing | No wrapper/runtime parser implementation was found to verify this boundary. |
| pass 1 buffering does not leak partial output | -- | missing | No concrete M6/runtime code or tests found in this workspace; waiting on M6. |
| blocked/not_required gate emits sanitized pass 1 | -- | missing | No concrete M6/runtime code or tests found in this workspace; waiting on M6. |
| approved gate triggers exactly one pass 2 | -- | missing | No concrete M6/runtime code or tests found in this workspace; waiting on M6. |
| pass 2 timeout emits sanitized pass 1 | -- | missing | No concrete M6/runtime code or tests found in this workspace; waiting on M6. |
| pass 2 cancel emits sanitized pass 1 | -- | missing | No concrete M6/runtime code or tests found in this workspace; waiting on M6. |
| pass 1 cancel emits no final answer | -- | missing | No concrete M6/runtime code or tests found in this workspace; waiting on M6. |
| `ToolFollowup` remains blocked | -- | missing | No concrete M6/runtime code or tests found in this workspace; waiting on M6. |
| `Hybrid` remains blocked | -- | missing | No concrete M6/runtime code or tests found in this workspace; waiting on M6. |
| legacy mode remains unchanged | -- | not applicable yet | No runnable M6 wrapper surface was found to compare against a legacy path. |
| `level7_shadow` remains dry-run only | -- | missing | No concrete M6/runtime code or tests found in this workspace; waiting on M6. |
| no backend request-shape drift | -- | not applicable yet | No runtime/backend contract harness was found in this workspace. |
| no backend API drift | -- | not applicable yet | No runtime/backend contract harness was found in this workspace. |
| no runtime tool execution beyond M6 scope | -- | not applicable yet | No runnable M6 execution path was found to exercise or constrain tool execution. |
