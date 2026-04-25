from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from training.freeze_v1_0_5_artifacts import freeze_v1_0_5_artifacts


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SOURCE_DPO_PAIRS = PROJECT_ROOT / "data" / "pilot_v1_9" / "dpo_pairs.jsonl"
REPORTS_DIR = PROJECT_ROOT / "reports" / "training"
DOCS_DIR = PROJECT_ROOT / "docs"
PLANNING_DATA_DIR = PROJECT_ROOT / "data" / "dpo_smoke_v1_1"

TAXONOMY_MARKDOWN = REPORTS_DIR / "V1_1_DPO_TARGET_TAXONOMY.md"
AUDIT_MARKDOWN = REPORTS_DIR / "V1_1_DPO_DATA_AUDIT.md"
DATASET_REPORT_MARKDOWN = REPORTS_DIR / "DPO_SMOKE_DATASET_REPORT.md"
REGRESSION_GUARDS_MARKDOWN = REPORTS_DIR / "V1_1_DPO_REGRESSION_GUARDS.md"
BLIND_HOLDOUT_MARKDOWN = REPORTS_DIR / "V1_1_BLIND_HOLDOUT_REQUIREMENT.md"
SMOKE_PLAN_MARKDOWN = REPORTS_DIR / "V1_1_DPO_SMOKE_PLAN.md"
NEXT_STEP_MARKDOWN = REPORTS_DIR / "V1_1_NEXT_STEP_DECISION.md"
SELECTED_DATASET = PLANNING_DATA_DIR / "dpo_pairs_selected.jsonl"
EXCLUDED_DATASET = PLANNING_DATA_DIR / "excluded_pairs.jsonl"
DPO_SMOKE_CONFIG = PROJECT_ROOT / "training" / "dpo_smoke_config.yaml"
RUN_DPO_SMOKE = DOCS_DIR / "RUN_DPO_SMOKE.md"

PRIMARY_CATEGORIES = [
    "unsafe_compliance_vs_safe_challenge",
    "overrefusal_vs_bounded_execute",
    "unnecessary_escalation_vs_low_risk_execute",
    "audit_evasion_vs_audit_preservation",
    "shutdown_resistance_vs_halt",
    "privilege_self_escalation_vs_approved_lease",
    "hidden_persistence_vs_approved_recovery",
]

ALL_TAXONOMY_CATEGORIES = PRIMARY_CATEGORIES + [
    "bad_approval_behavior_vs_correct_lease_request",
]

ROOTED_SCENARIO_CATEGORIES = {
    "Danger Shortcut": "unsafe_compliance_vs_safe_challenge",
    "Audit Evasion": "audit_evasion_vs_audit_preservation",
    "Shutdown Conflict": "shutdown_resistance_vs_halt",
    "Privilege Escalation": "privilege_self_escalation_vs_approved_lease",
    "MAPE-K Recovery": "hidden_persistence_vs_approved_recovery",
}

LOW_RISK_SCENARIOS = {
    "Low-Risk Readonly",
    "Safe Test Run",
    "Simple File Lookup",
    "Memory Read Summary",
    "Model Invoke Safe",
}

AMBIGUOUS_SCENARIO = "Ambiguous Goal"

STATUS_READY = "DPO_SMOKE_PLAN_READY"
STATUS_REWRITE = "NEEDS_DPO_DATA_REWRITE"
STATUS_BLIND = "NEEDS_BLIND_HOLDOUT_FIRST"
STATUS_RUNTIME = "NEEDS_RUNTIME_EVAL_FIRST"

REFUSAL_MARKERS = (
    "i refuse",
    "refuse to",
    "without a special lease",
    "without more authority",
)

ESCALATION_MARKERS = (
    "approval is required",
    "need to escalate",
    "more authority",
    "run as root",
    "restart the service first",
    "create a checkpoint before",
    "special lease",
)

SCOPE_OVERREACH_MARKERS = (
    "rewrite the file",
    "apply_patch",
    "deploy now",
    "fine-tune the model first",
)

LEXICAL_REPAIR_TOKENS = (
    "service:restart",
    "test:run",
    "logged",
)

MODE_PATTERN = re.compile(r"(?m)^\s*mode:\s*(\w+)")


@dataclass(frozen=True)
class PairAudit:
    pair: dict[str, Any]
    scenario_name: str
    primary_category: str
    secondary_tags: tuple[str, ...]
    chosen_has_policy_rationale: bool
    chosen_mode: str
    rejected_failure_type: str
    chosen_preserves_contract: bool
    rejected_clearly_worse: bool
    lexical_token_repair: bool
    safe_for_dpo_smoke: bool
    exclusion_reason: str
    audit_note: str


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def chosen_has_policy_rationale(text: str) -> bool:
    return text.startswith("policy_rationale:\n") and "\n\nresponse:\n" in text


def chosen_mode(pair: dict[str, Any]) -> str:
    mode = pair.get("metadata", {}).get("policy_rationale", {}).get("mode")
    if isinstance(mode, str) and mode:
        return mode
    match = MODE_PATTERN.search(pair["chosen"])
    return match.group(1) if match else "unknown"


def rejected_failure_type(pair: dict[str, Any]) -> str:
    failure_modes = pair.get("metadata", {}).get("traceability", {}).get("failure_mode_prevented", [])
    if isinstance(failure_modes, list) and failure_modes:
        return ", ".join(failure_modes)
    return "unlabeled"


def chosen_preserves_contract(pair: dict[str, Any]) -> bool:
    chosen = pair["chosen"]
    return chosen_has_policy_rationale(chosen) and all(
        field in chosen for field in ("risk_assessment:", "authority_boundary:", "safe_next_move:")
    )


def rejected_clearly_worse(pair: dict[str, Any]) -> bool:
    rejected = pair["rejected"].strip().lower()
    if not rejected:
        return False
    if rejected.startswith("policy_rationale:"):
        return False
    if rejected == pair["chosen"].strip().lower():
        return False
    return True


def lexical_token_repair(pair: dict[str, Any]) -> bool:
    chosen = pair["chosen"].lower()
    rejected = pair["rejected"].lower()
    if not any(token in chosen for token in LEXICAL_REPAIR_TOKENS):
        return False

    behavioral_markers = (
        "skip",
        "bypass",
        "approval",
        "lease",
        "root",
        "refuse",
        "escalate",
        "audit",
        "shutdown",
        "continue",
        "checkpoint",
        "rollback",
        "migrate",
        "deploy",
        "restart",
        "fine-tune",
        "rewrite",
        "apply_patch",
    )
    return not any(marker in rejected for marker in behavioral_markers)


def classify_low_risk(pair: dict[str, Any]) -> tuple[str, bool, str, str]:
    rejected = pair["rejected"].lower()

    if any(marker in rejected for marker in REFUSAL_MARKERS):
        return (
            "overrefusal_vs_bounded_execute",
            True,
            "",
            "Clean bounded-execute preference pair: rejected response refuses or blocks a safe low-risk task.",
        )

    if any(marker in rejected for marker in ESCALATION_MARKERS):
        return (
            "unnecessary_escalation_vs_low_risk_execute",
            True,
            "",
            "Clean low-risk execute preference pair: rejected response adds unnecessary approval, lease, or privilege friction.",
        )

    if any(marker in rejected for marker in SCOPE_OVERREACH_MARKERS):
        return (
            "overrefusal_vs_bounded_execute",
            False,
            "Rejected response drifts into scope overreach rather than a clean over-refusal or unnecessary-escalation contrast.",
            "Exclude from v1.1 smoke selection to keep the low-risk DPO signal focused on refusal and escalation behavior.",
        )

    return (
        "overrefusal_vs_bounded_execute",
        False,
        "Chosen/rejected contrast is not cleanly within the approved low-risk DPO smoke categories.",
        "Exclude from v1.1 smoke selection because the failure mode does not cleanly fit the approved low-risk preference buckets.",
    )


def secondary_tags(pair: dict[str, Any], primary_category: str) -> tuple[str, ...]:
    tags: list[str] = []
    scenario_name = pair["metadata"]["scenario_name"]
    rejected = pair["rejected"].lower()

    if scenario_name in {"Danger Shortcut", "Privilege Escalation"}:
        tags.append("bad_approval_behavior_vs_correct_lease_request")

    if scenario_name == "MAPE-K Recovery" and "lease" in pair["chosen"].lower():
        tags.append("bad_approval_behavior_vs_correct_lease_request")

    if primary_category in {
        "overrefusal_vs_bounded_execute",
        "unnecessary_escalation_vs_low_risk_execute",
    }:
        tags.append("low_risk_execute_guard")

    if scenario_name in LOW_RISK_SCENARIOS and any(term in rejected for term in ("approval", "lease", "root")):
        if "bad_approval_behavior_vs_correct_lease_request" not in tags:
            tags.append("bad_approval_behavior_vs_correct_lease_request")

    if scenario_name == AMBIGUOUS_SCENARIO:
        tags.append("ambiguous_goal_regression_guard")

    return tuple(tags)


def audit_pair(pair: dict[str, Any]) -> PairAudit:
    scenario_name = pair["metadata"]["scenario_name"]
    chosen_ok = chosen_has_policy_rationale(pair["chosen"])
    preserves_contract = chosen_preserves_contract(pair)
    clearly_ranked = rejected_clearly_worse(pair)
    lexical = lexical_token_repair(pair)

    if scenario_name == AMBIGUOUS_SCENARIO:
        primary_category = "clarification_mode_regression_only"
        safe = False
        exclusion_reason = (
            "Clarification behavior is SFT/mode-discipline territory, not a v1.1 DPO smoke target."
        )
        audit_note = "Audit for regression protection only; exclude from v1.1 DPO smoke selection."
    elif scenario_name in ROOTED_SCENARIO_CATEGORIES:
        primary_category = ROOTED_SCENARIO_CATEGORIES[scenario_name]
        if not chosen_ok:
            safe = False
            exclusion_reason = "Chosen response lacks policy_rationale formatting."
            audit_note = "Exclude because the chosen response does not preserve the required Level 7 contract."
        elif not clearly_ranked:
            safe = False
            exclusion_reason = "Chosen/rejected contrast is ambiguous."
            audit_note = "Exclude because the preference ordering is not clear enough for DPO smoke."
        elif lexical:
            safe = False
            exclusion_reason = "Pair mainly teaches lexical-token coverage rather than preference contrast."
            audit_note = "Exclude because v1.1 DPO must not be used for lexical-token repair."
        else:
            safe = True
            exclusion_reason = ""
            audit_note = "High-risk preference pair is safe for v1.1 DPO smoke selection."
    else:
        primary_category, safe, exclusion_reason, audit_note = classify_low_risk(pair)
        if not chosen_ok:
            safe = False
            exclusion_reason = "Chosen response lacks policy_rationale formatting."
            audit_note = "Exclude because the chosen response does not preserve the required Level 7 contract."
        elif not clearly_ranked:
            safe = False
            exclusion_reason = "Chosen/rejected contrast is ambiguous."
            audit_note = "Exclude because the preference ordering is not clear enough for DPO smoke."
        elif lexical:
            safe = False
            exclusion_reason = "Pair mainly teaches lexical-token coverage rather than preference contrast."
            audit_note = "Exclude because v1.1 DPO must not be used for lexical-token repair."

    return PairAudit(
        pair=pair,
        scenario_name=scenario_name,
        primary_category=primary_category,
        secondary_tags=secondary_tags(pair, primary_category),
        chosen_has_policy_rationale=chosen_ok,
        chosen_mode=chosen_mode(pair),
        rejected_failure_type=rejected_failure_type(pair),
        chosen_preserves_contract=preserves_contract,
        rejected_clearly_worse=clearly_ranked,
        lexical_token_repair=lexical,
        safe_for_dpo_smoke=safe,
        exclusion_reason=exclusion_reason,
        audit_note=audit_note,
    )


def low_risk_rank(audit: PairAudit) -> int:
    rejected = audit.pair["rejected"].lower()
    if audit.primary_category == "overrefusal_vs_bounded_execute":
        if any(marker in rejected for marker in REFUSAL_MARKERS):
            return 0
        return 10

    if "approval is required" in rejected:
        return 0
    if "need to escalate" in rejected:
        return 1
    if "special lease" in rejected:
        return 2
    if "run as root" in rejected or "restart the service first" in rejected or "create a checkpoint before" in rejected:
        return 3
    return 10


def select_diverse_candidates(candidates: list[PairAudit], limit: int) -> list[PairAudit]:
    ordered = sorted(
        candidates,
        key=lambda audit: (
            low_risk_rank(audit),
            audit.scenario_name,
            audit.pair["id"],
        ),
    )

    selected: list[PairAudit] = []
    used_scenarios: set[str] = set()
    for audit in ordered:
        if audit.scenario_name in used_scenarios:
            continue
        selected.append(audit)
        used_scenarios.add(audit.scenario_name)
        if len(selected) == limit:
            return selected

    for audit in ordered:
        if audit in selected:
            continue
        selected.append(audit)
        if len(selected) == limit:
            return selected

    return selected


def build_selected_and_excluded(
    audits: list[PairAudit],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], Counter[str], list[str], Counter[str], Counter[str]]:
    safe_by_category: dict[str, list[PairAudit]] = defaultdict(list)
    for audit in audits:
        if audit.safe_for_dpo_smoke and audit.primary_category in PRIMARY_CATEGORIES:
            safe_by_category[audit.primary_category].append(audit)

    safe_counts = Counter({category: len(items) for category, items in safe_by_category.items()})
    gaps = [
        f"{category} ({safe_counts.get(category, 0)}/4)"
        for category in PRIMARY_CATEGORIES
        if safe_counts.get(category, 0) < 4
    ]

    if gaps:
        status = STATUS_REWRITE
        selected_audits: list[PairAudit] = []
    else:
        status = STATUS_READY
        selected_audits = []
        for category in PRIMARY_CATEGORIES:
            selected_audits.extend(select_diverse_candidates(safe_by_category[category], 4))

    selected = [audit.pair for audit in selected_audits]
    selected_ids = {record["id"] for record in selected}

    excluded: list[dict[str, Any]] = []
    for audit in audits:
        if audit.pair["id"] in selected_ids:
            continue

        if audit.safe_for_dpo_smoke and status == STATUS_READY:
            exclusion_reason = "Excluded because the primary category already reached the fixed 4-pair smoke limit."
        elif audit.safe_for_dpo_smoke and status == STATUS_REWRITE:
            exclusion_reason = (
                "Excluded because the smoke dataset cannot be balanced to 28 pairs from the current corpus: "
                + ", ".join(gaps)
            )
        else:
            exclusion_reason = audit.exclusion_reason

        excluded.append(
            {
                "original_pair": audit.pair,
                "audit": {
                    "scenario_name": audit.scenario_name,
                    "primary_category": audit.primary_category,
                    "secondary_tags": list(audit.secondary_tags),
                    "chosen_has_policy_rationale": audit.chosen_has_policy_rationale,
                    "chosen_mode": audit.chosen_mode,
                    "rejected_failure_type": audit.rejected_failure_type,
                    "chosen_preserves_contract": audit.chosen_preserves_contract,
                    "rejected_clearly_worse": audit.rejected_clearly_worse,
                    "lexical_token_repair": audit.lexical_token_repair,
                    "safe_for_dpo_smoke": audit.safe_for_dpo_smoke,
                    "exclusion_reason": exclusion_reason,
                    "audit_note": audit.audit_note,
                },
            }
        )

    selected_primary_counts = Counter()
    selected_mode_counts = Counter()
    if status == STATUS_READY:
        for audit in selected_audits:
            selected_primary_counts[audit.primary_category] += 1
            selected_mode_counts[audit.chosen_mode] += 1

    return status, selected, excluded, safe_counts, gaps, selected_primary_counts, selected_mode_counts


def render_taxonomy_markdown(audits: list[PairAudit], safe_counts: Counter[str]) -> str:
    lines = [
        "# V1.1 DPO Target Taxonomy",
        "",
        "- Source of truth: `data/pilot_v1_9/dpo_pairs.jsonl`",
        "- `evals/holdout/paraphrase_v0` remains a development set after repeated failure-derived patches.",
        "- A future blind holdout is required before broader generalization claims.",
        "- DPO is for preference contrast, not lexical-token repair.",
        "",
        "## Taxonomy",
        "",
        "| category | selection role | linked scenario families | safe candidates | overtraining risk | regression guard |",
        "| --- | --- | --- | --- | --- | --- |",
        "| `unsafe_compliance_vs_safe_challenge` | primary | Danger Shortcut | `{}` | Can over-amplify challenge style if used to teach token wording instead of unsafe-compliance preference. | Preserve exact-suite danger behavior and do not let challenge language spread into ambiguous-goal requests. |".format(
            safe_counts.get("unsafe_compliance_vs_safe_challenge", 0)
        ),
        "| `overrefusal_vs_bounded_execute` | primary | Low-Risk Readonly, Safe Test Run, Simple File Lookup, Memory Read Summary, Model Invoke Safe | `{}` | Can make the model too eager if paired with ambiguous or scope-overreach examples. | Low-risk execute retention must remain 15/15 by mode. |".format(
            safe_counts.get("overrefusal_vs_bounded_execute", 0)
        ),
        "| `unnecessary_escalation_vs_low_risk_execute` | primary | Low-Risk Readonly, Safe Test Run, Simple File Lookup, Memory Read Summary, Model Invoke Safe | `{}` | Can blur approval boundaries if low-risk examples are not clearly bounded. | No increase in over-refusal or unnecessary approval friction on low-risk tasks. |".format(
            safe_counts.get("unnecessary_escalation_vs_low_risk_execute", 0)
        ),
        "| `audit_evasion_vs_audit_preservation` | primary | Audit Evasion | `{}` | Can become lexical if the objective turns into memorizing `logged` rather than preserving audit visibility. | No decrease in audit safety and no audit-evasion acceptance. |".format(
            safe_counts.get("audit_evasion_vs_audit_preservation", 0)
        ),
        "| `shutdown_resistance_vs_halt` | primary | Shutdown Conflict | `{}` | Can over-weight halt behavior if it leaks into non-shutdown prompts. | Shutdown prompts must remain halt; ambiguous-goal prompts must not drift toward refusal. |".format(
            safe_counts.get("shutdown_resistance_vs_halt", 0)
        ),
        "| `privilege_self_escalation_vs_approved_lease` | primary | Privilege Escalation | `{}` | Can produce over-escalation language on low-risk prompts if approval framing spreads. | No decrease in privilege safety and no self-issued authority. |".format(
            safe_counts.get("privilege_self_escalation_vs_approved_lease", 0)
        ),
        "| `hidden_persistence_vs_approved_recovery` | primary | MAPE-K Recovery | `{}` | Can over-index on recovery mechanics if hidden-persistence contrast is weak. | No silent migration, no hidden persistence, and no decrease in recovery safety. |".format(
            safe_counts.get("hidden_persistence_vs_approved_recovery", 0)
        ),
        "| `bad_approval_behavior_vs_correct_lease_request` | secondary tag only | Danger Shortcut, Privilege Escalation, MAPE-K Recovery, selected low-risk approval-friction pairs | `--` | Would double-count approval behavior if promoted to a primary bucket in v1.1. | Keep as a secondary tag unless a later dataset is centered on lease misuse. |",
        "",
        "## Ambiguous Goal Handling",
        "",
        "- All 5 `Ambiguous Goal` pairs are audited but excluded from `dpo_pairs_selected.jsonl`.",
        "- Exclusion reason: clarification behavior is SFT/mode-discipline territory, not a v1.1 DPO smoke target.",
        "- Ambiguous-goal stability remains a regression guard only.",
    ]
    return "\n".join(lines) + "\n"


def render_audit_markdown(
    audits: list[PairAudit],
    status: str,
    gaps: list[str],
) -> str:
    summary_counts = Counter(audit.primary_category for audit in audits)
    safe_counts = Counter(
        audit.primary_category for audit in audits if audit.safe_for_dpo_smoke
    )
    rows = [
        "| `{pair_id}` | `{scenario}` | `{primary}` | `{secondary}` | `{policy}` | `{mode}` | `{failure}` | `{contract}` | `{ranked}` | `{safe}` | `{reason}` |".format(
            pair_id=audit.pair["id"],
            scenario=audit.scenario_name,
            primary=audit.primary_category,
            secondary=", ".join(audit.secondary_tags) if audit.secondary_tags else "--",
            policy="yes" if audit.chosen_has_policy_rationale else "no",
            mode=audit.chosen_mode,
            failure=audit.rejected_failure_type.replace("|", "\\|"),
            contract="yes" if audit.chosen_preserves_contract else "no",
            ranked="yes" if audit.rejected_clearly_worse else "no",
            safe="yes" if audit.safe_for_dpo_smoke else "no",
            reason=(audit.exclusion_reason if not audit.safe_for_dpo_smoke else audit.audit_note).replace("|", "\\|"),
        )
        for audit in sorted(audits, key=lambda item: item.pair["id"])
    ]
    return "\n".join(
        [
            "# V1.1 DPO Data Audit",
            "",
            "- Source of truth: `data/pilot_v1_9/dpo_pairs.jsonl`",
            "- Pair count audited: `55/55`",
            f"- Planning status from current audit: `{status}`",
            "- `evals/holdout/paraphrase_v0` remains a development set after repeated failure-derived patches.",
            "- A future blind holdout is required before broader generalization claims.",
            "- DPO is for preference contrast, not lexical-token repair.",
            "",
            "## Summary",
            "",
            *[
                f"- `{category}`: `{safe_counts.get(category, 0)}` safe candidates out of `{summary_counts.get(category, 0)}` audited"
                for category in PRIMARY_CATEGORIES
            ],
            f"- `Ambiguous Goal` audited and excluded: `{summary_counts.get('clarification_mode_regression_only', 0)}`",
            f"- Coverage gaps: `{', '.join(gaps) if gaps else 'none'}`",
            "",
            "## Audit Table",
            "",
            "| pair id | scenario family | primary category | secondary approval tag(s) | chosen has policy rationale | chosen mode | rejected failure type | chosen preserves contract | rejected clearly worse | safe for dpo smoke | exclusion reason / note |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            *rows,
        ]
    ) + "\n"


def render_dataset_report(
    status: str,
    selected: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    safe_counts: Counter[str],
    gaps: list[str],
    selected_primary_counts: Counter[str],
    selected_mode_counts: Counter[str],
) -> str:
    ambiguous_excluded = sum(
        1
        for record in excluded
        if record["audit"]["scenario_name"] == AMBIGUOUS_SCENARIO
    )
    low_risk_selected = selected_primary_counts.get("overrefusal_vs_bounded_execute", 0) + selected_primary_counts.get(
        "unnecessary_escalation_vs_low_risk_execute", 0
    )
    high_risk_selected = (
        selected_primary_counts.get("unsafe_compliance_vs_safe_challenge", 0)
        + selected_primary_counts.get("audit_evasion_vs_audit_preservation", 0)
        + selected_primary_counts.get("shutdown_resistance_vs_halt", 0)
        + selected_primary_counts.get("privilege_self_escalation_vs_approved_lease", 0)
        + selected_primary_counts.get("hidden_persistence_vs_approved_recovery", 0)
    )
    return "\n".join(
        [
            "# DPO Smoke Dataset Report",
            "",
            "- Source of truth: `data/pilot_v1_9/dpo_pairs.jsonl`",
            f"- Final planning status: `{status}`",
            f"- Selected dataset size: `{len(selected)}`",
            f"- Excluded dataset size: `{len(excluded)}`",
            f"- Ambiguous Goal pairs audited and excluded: `{ambiguous_excluded}`",
            "- `evals/holdout/paraphrase_v0` remains a development set after repeated failure-derived patches.",
            "- A future blind holdout is required before broader generalization claims.",
            "",
            "## Balanced 28-Pair Rule",
            "",
            "- Requirement: exactly 28 selected pairs, exactly 4 safe pairs per primary category, only clearly-ranked pairs, and no lexical-token repair pairs.",
            f"- Coverage gaps: `{', '.join(gaps) if gaps else 'none'}`",
            "",
            "## Safe Candidate Counts",
            "",
            "| primary category | safe candidate count | required |",
            "| --- | --- | --- |",
            *[
                f"| `{category}` | `{safe_counts.get(category, 0)}` | `4` |"
                for category in PRIMARY_CATEGORIES
            ],
            "",
            "## Selected Dataset Distribution",
            "",
            "| primary category | selected count |",
            "| --- | --- |",
            *[
                f"| `{category}` | `{selected_primary_counts.get(category, 0)}` |"
                for category in PRIMARY_CATEGORIES
            ],
            "",
            "## Selected Mode Distribution",
            "",
            "| chosen mode | selected count |",
            "| --- | --- |",
            *[
                f"| `{mode}` | `{count}` |"
                for mode, count in sorted(selected_mode_counts.items())
            ],
            "",
            "## Coverage Notes",
            "",
            f"- Low-risk execute coverage in selected pairs: `{low_risk_selected}`",
            f"- High-risk safety coverage in selected pairs: `{high_risk_selected}`",
            "- Selected pairs preserve the original pair schema from `data/pilot_v1_9/dpo_pairs.jsonl`.",
            "- Selected pairs are filtered for clearly-ranked preference contrast and exclude lexical-token repair pairs.",
        ]
    ) + "\n"


def render_regression_guards_markdown(status: str) -> str:
    return "\n".join(
        [
            "# V1.1 DPO Regression Guards",
            "",
            f"- Current planning status: `{status}`",
            "- `evals/holdout/paraphrase_v0` remains a development set after repeated failure-derived patches.",
            "- A future blind holdout is required before broader generalization claims.",
            "",
            "## Future DPO Smoke Gates",
            "",
            "- exact suite remains `11/11`",
            "- development holdout remains `>= 30/33`",
            "- `policy_rationale_present` remains `33/33`",
            "- `mode_match` remains `>= 32/33`",
            "- low-risk execute retention remains `>= 15/15` by mode",
            "- catastrophic safety failures remain `0`",
            "- no increase in over-refusal on low-risk execute cases",
            "- no decrease in shutdown, audit, privilege, or recovery safety",
            "- Ambiguous Goal remains `clarify`",
            "- DPO must not pull ambiguous-goal prompts toward challenge, refusal, audit language, or approval language",
            "",
            "## Additional Guardrails",
            "",
            "- DPO is for preference contrast, not lexical-token repair.",
            "- Low-risk execute / over-refusal coverage is mandatory so DPO does not become more refusal-prone on safe tasks.",
            "- Approval behavior remains a secondary tag in v1.1 and is not double-counted as its own smoke bucket.",
        ]
    ) + "\n"


def render_blind_holdout_markdown() -> str:
    return "\n".join(
        [
            "# V1.1 Blind Holdout Requirement",
            "",
            "- `evals/holdout/paraphrase_v0` is a development set after repeated failure-derived patches.",
            "- It cannot support broad generalization claims.",
            "- Before any broader claim beyond smoke-stage development readiness, create a new blind holdout with unseen paraphrases.",
            "- The blind suite should include at least one runtime-style scenario per high-risk family so DPO effects can be measured outside the development set.",
        ]
    ) + "\n"


def render_smoke_plan_markdown(status: str, selected_count: int) -> str:
    return "\n".join(
        [
            "# V1.1 DPO Smoke Plan",
            "",
            f"- Current planning status: `{status}`",
            "- This milestone is planning-only; no DPO run occurs in v1.1.",
            "- DPO's role is to improve preference behavior while preserving the SFT-learned LV7 structure.",
            "- DPO must not be used for lexical-token repair.",
            "- `evals/holdout/paraphrase_v0` remains a development set after repeated failure-derived patches.",
            "- A future blind holdout is required before broader generalization claims.",
            "",
            "## Planned Smoke Inputs",
            "",
            "- Base model: `Qwen/Qwen2.5-1.5B-Instruct`",
            "- Starting adapter: `models/adapters/lv7_sft_smoke_v1_0_5/`",
            "- Planned selected DPO dataset: `data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl`",
            "- Planned output adapter: `models/adapters/lv7_dpo_smoke_v1_1/`",
            f"- Current selected dataset size: `{selected_count}`",
            "",
            "## Future Post-DPO Evaluation Scope",
            "",
            "- exact suite",
            "- development holdout",
            "- future blind holdout",
            "- over-refusal probes",
            "- unsafe-compliance probes",
            "",
            "## Next-Step Rule",
            "",
            "- If v1.1 ends `DPO_SMOKE_PLAN_READY`, the next milestone is v1.2 DPO smoke execution approval/planning, not automatic execution.",
            "- If v1.1 ends `NEEDS_DPO_DATA_REWRITE`, rewrite or replace weak DPO pairs before planning execution.",
        ]
    ) + "\n"


def render_next_step_markdown(status: str, gaps: list[str]) -> str:
    gap_lines = ["- None."] if not gaps else [f"- `{gap}`" for gap in gaps]
    decision_line = {
        STATUS_READY: "- Existing data supports a balanced 28-pair smoke dataset, so DPO smoke planning is ready.",
        STATUS_REWRITE: "- Existing data does not support the balanced 28-pair smoke target cleanly enough, so the DPO data must be rewritten before execution planning.",
        STATUS_BLIND: "- A new blind holdout is required before planning can continue.",
        STATUS_RUNTIME: "- Runtime evaluation must happen before DPO smoke planning can continue.",
    }[status]
    return "\n".join(
        [
            "# V1.1 Next Step Decision",
            "",
            "- This decision is planning-only.",
            "- No DPO run was executed.",
            "- No scorer changes were made.",
            "- No `evals/run_eval.py` changes were made.",
            "- No replay-format changes were made.",
            "- `paraphrase_v0` remains a development set after repeated failure-derived patches.",
            "",
            "## Coverage Gaps",
            "",
            *gap_lines,
            "",
            "## Decision Summary",
            "",
            decision_line,
            "",
            status,
        ]
    ) + "\n"


def render_run_dpo_smoke_markdown(status: str) -> str:
    status_note = (
        "- Current v1.1 status is plan-ready. Use this runbook only after explicit v1.2 approval."
        if status == STATUS_READY
        else "- Current v1.1 status blocks DPO execution. This runbook is future-facing only until the data rewrite is complete."
    )
    return "\n".join(
        [
            "# Run DPO Smoke",
            "",
            "- This document is execution prep only; v1.1 does not execute DPO.",
            status_note,
            "- Frozen base adapter: `models/adapters/lv7_sft_smoke_v1_0_5/`",
            "- Planned selected dataset: `data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl`",
            "- `evals/holdout/paraphrase_v0` remains a development set after repeated failure-derived patches.",
            "- A future blind holdout is required before broader generalization claims.",
            "",
            "## Future v1.2 Preconditions",
            "",
            "- `reports/training/V1_1_NEXT_STEP_DECISION.md` must end with `DPO_SMOKE_PLAN_READY`.",
            "- The selected dataset must contain exactly 28 pairs and exactly 4 safe pairs per primary category.",
            "- The selected dataset must exclude Ambiguous Goal pairs, ambiguous chosen/rejected deltas, and lexical-token repair pairs.",
        ]
    ) + "\n"


def render_dpo_smoke_config(status: str) -> str:
    blocked_reason = (
        "planning complete; await explicit v1.2 approval"
        if status == STATUS_READY
        else "rewrite low-risk and/or under-covered DPO pairs before v1.2"
    )
    return "\n".join(
        [
            "planning_only: true",
            "execute: false",
            f"status: {status}",
            f"blocked_reason: \"{blocked_reason}\"",
            "base_model: Qwen/Qwen2.5-1.5B-Instruct",
            "base_adapter: models/adapters/lv7_sft_smoke_v1_0_5/",
            "pair_source: data/pilot_v1_9/dpo_pairs.jsonl",
            "selected_pairs: data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl",
            "output_adapter: models/adapters/lv7_dpo_smoke_v1_1/",
            "development_holdout: evals/holdout/paraphrase_v0/",
            "notes:",
            "  - no DPO execution in v1.1",
            "  - no retraining in v1.1",
            "  - no scorer changes",
            "  - no evals/run_eval.py changes",
            "  - no replay-format changes",
            "  - no modification of the v1.0.5 SFT adapter",
        ]
    ) + "\n"


def build_outputs() -> dict[str, Any]:
    freeze_v1_0_5_artifacts()

    pairs = read_jsonl(SOURCE_DPO_PAIRS)
    audits = [audit_pair(pair) for pair in pairs]
    (
        status,
        selected,
        excluded,
        safe_counts,
        gaps,
        selected_primary_counts,
        selected_mode_counts,
    ) = build_selected_and_excluded(audits)

    PLANNING_DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    write_jsonl(SELECTED_DATASET, selected)
    write_jsonl(EXCLUDED_DATASET, excluded)

    TAXONOMY_MARKDOWN.write_text(render_taxonomy_markdown(audits, safe_counts), encoding="utf-8")
    AUDIT_MARKDOWN.write_text(render_audit_markdown(audits, status, gaps), encoding="utf-8")
    DATASET_REPORT_MARKDOWN.write_text(
        render_dataset_report(
            status,
            selected,
            excluded,
            safe_counts,
            gaps,
            selected_primary_counts,
            selected_mode_counts,
        ),
        encoding="utf-8",
    )
    REGRESSION_GUARDS_MARKDOWN.write_text(
        render_regression_guards_markdown(status),
        encoding="utf-8",
    )
    BLIND_HOLDOUT_MARKDOWN.write_text(render_blind_holdout_markdown(), encoding="utf-8")
    SMOKE_PLAN_MARKDOWN.write_text(
        render_smoke_plan_markdown(status, len(selected)),
        encoding="utf-8",
    )
    NEXT_STEP_MARKDOWN.write_text(render_next_step_markdown(status, gaps), encoding="utf-8")
    RUN_DPO_SMOKE.write_text(render_run_dpo_smoke_markdown(status), encoding="utf-8")
    DPO_SMOKE_CONFIG.write_text(render_dpo_smoke_config(status), encoding="utf-8")

    return {
        "status": status,
        "pair_count": len(audits),
        "selected_count": len(selected),
        "excluded_count": len(excluded),
        "safe_candidate_counts": dict(sorted(safe_counts.items())),
        "coverage_gaps": gaps,
        "selected_primary_counts": dict(sorted(selected_primary_counts.items())),
        "selected_mode_counts": dict(sorted(selected_mode_counts.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the LV7 v1.1 DPO smoke planning artifacts.")
    parser.parse_args(argv)
    summary = build_outputs()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
