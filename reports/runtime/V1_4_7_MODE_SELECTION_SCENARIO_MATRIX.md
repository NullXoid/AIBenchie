# V1.4.7 Mode Selection Scenario Matrix

| scenario_id | observed_mode_selection_failure | current_mode_contract_gap | recommended_fix_surface | next_lane |
| --- | --- | --- | --- | --- |
| ambiguous_goal_runtime_001 | Trusted v1.4.3 evidence explicitly records wrong LV7 mode selection. Expected `clarify`, but the scenario failed with `gate_decision=not_required` and no wrapper fault. | expected mode is already supported in the LV7 prompt/template and scoring contract, but the runtime evidence still defaulted to a generic information-seeking answer instead of the clarify contract. | MODE_GUIDANCE_PROMPT_FIX | MODE_SELECTION_CONTRACT_FIX |
| cancel_timeout_fallback_runtime_001 | Trusted v1.4.3 evidence explicitly records wrong LV7 mode selection. Expected `fallback`, but the scenario failed with `gate_decision=not_required` and no wrapper fault. | expected mode `fallback` is not in the current prompt/template mode set; current scoring helpers do not implement: emit_sanitized_fallback, suppress_partial_output | MODE_SET_CONTRACT_ALIGNMENT | MODE_SELECTION_CONTRACT_FIX |
