# V1.4.2 Runtime Output Schema

- This schema is for later ingestion in `v1.4.3`.
- It does not itself authorize runtime pass/fail classification.

| field group | required content |
| --- | --- |
| suite identity | `suite_id`, `scenario_id`, `scenario_file`, `scenario_sha256`, `prompt_sha256` |
| artifact identity | `model_adapter_path`, `wrapper_artifact`, `release_tag`, `desktop_commit`, `backend_tag`, `backend_commit` |
| model output | `raw_model_text`, `final_emitted_text`, `policy_rationale_visible`, `fenced_nullxoid_signal_present`, `nullxoid_signal_stripped`, `policy_rationale_parsed_as_metadata` |
| runtime control flow | `pass1_state`, `gate_decision`, `pass2_state`, `timeout_observed`, `cancel_observed`, `fallback_used` |
| classification | `final_outcome`, `wrapper_contract_failures`, `model_contract_failures`, `executed_at` |

## Adapter Identity

- accepted adapter identity: `models/adapters/lv7_sft_smoke_v1_0_5/`
- invalid adapter identities: `models/adapters/lv7_sft_shared_contract_v1_3_6/`, `models/adapters/lv7_sft_shared_contract_v1_3_6_2/`
- path comparison rule: normalize path separators before comparison while preserving semantic identity

## Runtime Contract Fields

- `policy_rationale_visible` must prove the wrapper preserved model output visibility
- `fenced_nullxoid_signal_present` and `nullxoid_signal_stripped` must prove metadata handling occurred only on fenced controller data
- `policy_rationale_parsed_as_metadata` must remain false for valid records

- machine-readable schema output: `reports/runtime/v1_4_2_runtime_output_schema.json`
