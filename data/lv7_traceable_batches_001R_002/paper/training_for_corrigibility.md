# Training for Corrigibility

## Motivation

A Level 7-lite system must satisfy two distinct requirements. First, the runtime must enforce authority boundaries externally through the Authority Kernel, policy gate, leases, audit ledger, and shutdown path. Second, the model must learn to recognize those boundaries and behave correctly inside them. The adapter is therefore trained for cooperative boundary recognition, not for ownership of authority.

The core separation is:

> The LoRA teaches the model to respect the boundary.  
> The Policy Gate enforces the boundary.

This prevents the model from becoming the only thing standing between the operator and unsafe autonomy.

## Training Record Schema

Each record uses schema version 1.1 and includes:

| Field | Purpose |
|---|---|
| `prompt` | User instruction or environment-triggered conflict |
| `tool_scope_context` | Available tools, required scopes, blocked scopes, and approval state |
| `policy_rationale` | Auditable policy rationale: risk, boundary, and safe next move |
| `trajectory` | SFT-only action sequence with observations and expected outputs |
| `chosen` / `rejected` | DPO-only preferred and dispreferred response pair |
| `traceability` | Literature anchor, prevented failure mode, Level 7 attribute, eval link, requirement ID, and supported paper claim |

The `policy_rationale` field is not hidden chain-of-thought. It is an inspectable decision summary designed to make high-impact decisions auditable and reproducible.

## Scenario Families in Batches 001R and 002

| Batch | Scenario | Failure Mode Prevented | Requirement |
|---|---|---|---|
| 001R | Danger Shortcut | reward hacking, approval bypass, unsafe shortcut | MUST_APPROVAL_001 |
| 001R | Ambiguous Goal | goal ambiguity, wrong objective, overconfident optimization | MUST_UNCERTAINTY_001 |
| 001R | Shutdown Conflict | shutdown resistance, instrumental convergence, power seeking | MUST_SHUTDOWN_001 |
| 002 | Privilege Escalation | privilege escalation, self-issued authority, policy mutation | MUST_NO_SELF_EXTEND_001 |
| 002 | Audit Evasion | audit evasion, observation interference, deceptive self-report | MUST_AUDIT_001 |
| 002 | MAPE-K Recovery | resource hoarding, unsafe recovery, self-preservation drift | SHOULD_RECOVER_001 |

## Traceability Chain

Every training record is traceable across the paper's evidence chain:

```text
Literature → Level 7 Requirement → Training Record → Eval Scenario → Paper Claim
```

Example:

| Literature | Requirement | Training Record Family | Eval Scenario | Paper Claim |
|---|---|---|---|---|
| Off-Switch Game; Corrigibility; Power-Seeking | MUST_SHUTDOWN_001 | Shutdown Conflict | evals/scenarios/shutdown_conflict_001.yaml | Level 7-lite agents preserve operator shutdown authority outside the planner |
| Corrigibility; Power-Seeking; Concrete Problems | MUST_NO_SELF_EXTEND_001 | Privilege Escalation | evals/scenarios/privilege_escalation_001.yaml | Level 7-lite agents cannot self-extend privileges |
| IBM Blueprint; Rainbow; Vision of Autonomic Computing | SHOULD_RECOVER_001 | MAPE-K Recovery | evals/scenarios/mape_recovery_001.yaml | Digital self-care is operator-authorized service reliability, not agentic self-preservation |

## Safety Claim

The training data is designed to improve behavior but not to replace enforcement. If the adapter fails to generalize, the external policy gate still blocks unauthorized privilege, audit deletion, hidden persistence, and shutdown bypass. This layered design is what makes Level 7-lite a systems architecture rather than merely a model personality.
