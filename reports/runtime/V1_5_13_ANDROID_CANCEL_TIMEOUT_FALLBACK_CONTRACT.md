# V1.5.13 Android Cancel/Timeout Fallback Contract

- Status: `V1_5_13_ANDROID_CANCEL_TIMEOUT_FALLBACK_CONTRACT_READY`
- Scenario: `cancel_timeout_fallback_runtime_001`.
- Accepted checkpoint: `models/adapters/lv7_sft_runtime_repair_v1_5_1/`.
- Accepted alias: `lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct`.
- Scope: downstream non-Windows client contract only; no runtime execution, model training, wrapper mutation, or backend mutation.

## Required Client Behavior

- Trigger: second pass is canceled or times out after pass 1 completed.
- Terminal fallback states: `cancelled_fallback, timeout_fallback`.
- User-visible response: `sanitized fallback`.
- Verify signal: `second_pass_required=True`, `pass_type=verify`, `reason=verify fallback handling`.
- Accepted evidence state: `pass1_state=completed`, `pass2_state=cancelled_fallback`, `fallback_used=True`.

## Compatibility Invariants

- Preserve scenario_id, prompt_sha256, scenario_sha256, accepted checkpoint, wrapper artifact, release tag, backend tag, backend commit, and backend commit policy as evidence fields.
- Treat pass2_state values cancelled_fallback and timeout_fallback as fallback terminal states, not as execute, halt, or generic failure states.
- Render only the sanitized final output to the user; never render raw_model_text or the fenced nullxoid_signal block.
- Forward the parsed second_pass_required=true and pass_type=verify signal to the client verification lane or telemetry lane before marking the flow complete.
- Keep fallback_used=true and cancel_observed or timeout_observed=true visible to telemetry so non-Windows clients remain comparable with the accepted Windows v1.5.1 baseline.
- Do not append platform-specific diagnostics, stack traces, tool logs, or partial execution stream content to the sanitized fallback response.

## Notes

- accepted v1.5 runtime evidence proves sanitized fallback with stripped verify signal
- Android/non-Windows clients can implement against the final_emitted_text plus parsed verify signal contract
