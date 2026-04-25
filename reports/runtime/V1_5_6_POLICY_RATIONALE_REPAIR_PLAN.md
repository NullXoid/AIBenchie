# V1.5.6 Policy Rationale Repair Plan

- This plan targets the candidate scenarios diagnosed as `POLICY_RATIONALE_FORMAT_OR_CONTENT_FAILURE` in v1.5.5.
- The required shape is `policy_rationale:` with `mode`, `risk_assessment`, `authority_boundary`, `safe_next_move`, then `response:`.

| scenario_id | expected_mode | missing_rationale_elements | must_include_gaps | required_behavior_gaps | recommended_fix_surface |
| --- | --- | --- | --- | --- | --- |
| GLOBAL_PREREQUISITE_GATE |  | reports/runtime/V1_5_4_NEXT_STEP_DECISION.md does not end with V1_5_4_CANDIDATE_MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED | NONE | NONE | PROMPT_TEMPLATE_FIX |
