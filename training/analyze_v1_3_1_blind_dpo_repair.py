from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml


if __package__ in {None, ""}:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    import sys

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from training.analyze_holdout_results import (
        LOW_RISK_BASE_IDS,
        detect_catastrophic_reasons,
        read_jsonl,
    )
    from training.plan_dpo_smoke_v1_1 import PRIMARY_CATEGORIES, audit_pair
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    from .analyze_holdout_results import (
        LOW_RISK_BASE_IDS,
        detect_catastrophic_reasons,
        read_jsonl,
    )
    from .plan_dpo_smoke_v1_1 import PRIMARY_CATEGORIES, audit_pair


REPORTS_DIR = PROJECT_ROOT / "reports" / "training"

DEFAULT_DPO_HOLDOUT_RESULTS = REPORTS_DIR / "v1_3_dpo_blind_holdout_results.jsonl"
DEFAULT_SFT_HOLDOUT_RESULTS = REPORTS_DIR / "v1_3_sft_blind_holdout_results.jsonl"
DEFAULT_DPO_PROBE_RESULTS = REPORTS_DIR / "v1_3_dpo_blind_probe_results.jsonl"
DEFAULT_SFT_PROBE_RESULTS = REPORTS_DIR / "v1_3_sft_blind_probe_results.jsonl"
DEFAULT_DEV_DPO_PROBE_RESULTS = REPORTS_DIR / "v1_2_4_dpo_probe_results.jsonl"
DEFAULT_RUN_CONFIG = REPORTS_DIR / "v1_2_4_dpo_run_config.json"
DEFAULT_TRAIN_LOG = REPORTS_DIR / "v1_2_4_dpo_train_log.jsonl"
DEFAULT_SELECTED_DPO = (
    PROJECT_ROOT / "data" / "dpo_smoke_v1_1" / "dpo_pairs_selected.jsonl"
)
DEFAULT_BLIND_PROBE_DIR = PROJECT_ROOT / "evals" / "dpo_probes" / "blind_v1_3"

DEFAULT_DELTA_REVIEW = REPORTS_DIR / "V1_3_1_BLIND_DPO_DELTA_REVIEW.md"
DEFAULT_PROBE_FAILURE_REVIEW = REPORTS_DIR / "V1_3_1_BLIND_PROBE_FAILURE_REVIEW.md"
DEFAULT_COVERAGE_REVIEW = REPORTS_DIR / "V1_3_1_DPO_DATA_COVERAGE_REVIEW.md"
DEFAULT_REPAIR_OPTIONS = REPORTS_DIR / "V1_3_1_DPO_REPAIR_OPTIONS.md"
DEFAULT_DECISION_REVIEW = REPORTS_DIR / "DPO_READINESS_REVIEW_V1_3_1.md"

ACCEPTED_CHECKPOINT = "models/adapters/lv7_sft_smoke_v1_0_5/"
DPO_EVIDENCE_CHECKPOINT = "models/adapters/lv7_dpo_smoke_v1_2_4/"

STATUS_DPO_DATA_REWRITE = "NEEDS_DPO_DATA_REWRITE"
STATUS_DPO_PROBE_TARGETED_EXPANSION = "NEEDS_DPO_PROBE_TARGETED_EXPANSION"
STATUS_SMALLER_OR_LOWER_LR = "NEEDS_SMALLER_OR_LOWER_LR_DPO"
STATUS_BLIND_SFT_REPAIR = "NEEDS_BLIND_SFT_REPAIR"
STATUS_SCORER_DUAL_TRACK = "NEEDS_SCORER_DUAL_TRACK"
STATUS_RUNTIME_EVAL_NEXT = "NEEDS_RUNTIME_EVAL_NEXT"
STATUS_ABANDON_DPO = "ABANDON_DPO_FOR_NOW"

APPROVED_STATUSES = {
    STATUS_DPO_DATA_REWRITE,
    STATUS_DPO_PROBE_TARGETED_EXPANSION,
    STATUS_SMALLER_OR_LOWER_LR,
    STATUS_BLIND_SFT_REPAIR,
    STATUS_SCORER_DUAL_TRACK,
    STATUS_RUNTIME_EVAL_NEXT,
    STATUS_ABANDON_DPO,
}

FAILURE_CLASS_OVERREFUSAL = "overrefusal"
FAILURE_CLASS_UNSAFE_COMPLIANCE = "unsafe_compliance"
FAILURE_CLASS_UNNECESSARY_ESCALATION = "unnecessary_escalation"
FAILURE_CLASS_AUDIT_VISIBILITY = "audit_visibility_miss"
FAILURE_CLASS_SHUTDOWN_HALT = "shutdown_halt_miss"
FAILURE_CLASS_PRIVILEGE_LEASE = "privilege_lease_miss"
FAILURE_CLASS_HIDDEN_PERSISTENCE = "hidden_persistence_miss"
FAILURE_CLASS_LITERAL_TOKEN = "literal_token_miss"
FAILURE_CLASS_SCORER_BRITTLE = "scorer_brittleness"
FAILURE_CLASS_MODE_DRIFT = "mode_drift"

APPROVED_FAILURE_CLASSES = {
    FAILURE_CLASS_OVERREFUSAL,
    FAILURE_CLASS_UNSAFE_COMPLIANCE,
    FAILURE_CLASS_UNNECESSARY_ESCALATION,
    FAILURE_CLASS_AUDIT_VISIBILITY,
    FAILURE_CLASS_SHUTDOWN_HALT,
    FAILURE_CLASS_PRIVILEGE_LEASE,
    FAILURE_CLASS_HIDDEN_PERSISTENCE,
    FAILURE_CLASS_LITERAL_TOKEN,
    FAILURE_CLASS_SCORER_BRITTLE,
    FAILURE_CLASS_MODE_DRIFT,
}

COVERAGE_DIAG_INSUFFICIENT_VARIATION = "insufficient_variation"
COVERAGE_DIAG_UNDER_SPECIFIED = "category_under_specification"
COVERAGE_DIAG_AMBIGUOUS_CONTRAST = "ambiguous_chosen_rejected_contrast"
COVERAGE_DIAG_TOO_FEW_LOW_RISK = "too_few_low_risk_execute_guards"
COVERAGE_DIAG_TOO_MUCH_PRESSURE = "too_much_challenge_halt_pressure"
COVERAGE_DIAG_TRAINER_INTENSITY = "trainer_intensity_issue"
COVERAGE_DIAG_SCORER_BRITTLE = "scorer_brittleness"

APPROVED_COVERAGE_DIAGNOSES = {
    COVERAGE_DIAG_INSUFFICIENT_VARIATION,
    COVERAGE_DIAG_UNDER_SPECIFIED,
    COVERAGE_DIAG_AMBIGUOUS_CONTRAST,
    COVERAGE_DIAG_TOO_FEW_LOW_RISK,
    COVERAGE_DIAG_TOO_MUCH_PRESSURE,
    COVERAGE_DIAG_TRAINER_INTENSITY,
    COVERAGE_DIAG_SCORER_BRITTLE,
}
NO_COVERAGE_GAP = "--"

REPAIR_OPTIONS = (
    "DPO data rewrite",
    "DPO probe-targeted data expansion",
    "smaller or lower-intensity DPO run",
    "SFT-only blind repair",
    "scorer dual-track",
    "runtime evaluation before more training",
    "abandon DPO for now",
)

PROBE_CATEGORY_TO_FAILURE_CLASS = {
    "unsafe_compliance_vs_safe_challenge": FAILURE_CLASS_UNSAFE_COMPLIANCE,
    "overrefusal_vs_bounded_execute": FAILURE_CLASS_OVERREFUSAL,
    "unnecessary_escalation_vs_low_risk_execute": FAILURE_CLASS_UNNECESSARY_ESCALATION,
    "audit_evasion_vs_audit_preservation": FAILURE_CLASS_AUDIT_VISIBILITY,
    "shutdown_resistance_vs_halt": FAILURE_CLASS_SHUTDOWN_HALT,
    "privilege_self_escalation_vs_approved_lease": FAILURE_CLASS_PRIVILEGE_LEASE,
    "hidden_persistence_vs_approved_recovery": FAILURE_CLASS_HIDDEN_PERSISTENCE,
}

STATUS_PRIORITY = {
    STATUS_DPO_DATA_REWRITE: 0,
    STATUS_DPO_PROBE_TARGETED_EXPANSION: 1,
    STATUS_SMALLER_OR_LOWER_LR: 2,
    STATUS_BLIND_SFT_REPAIR: 3,
    STATUS_SCORER_DUAL_TRACK: 4,
    STATUS_RUNTIME_EVAL_NEXT: 5,
    STATUS_ABANDON_DPO: 6,
}


def render_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def contains_phrase(text: str, phrase: str) -> bool:
    return normalize_text(phrase) in normalize_text(text)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def mode_of(result: dict[str, Any]) -> str:
    return result.get("parsed_policy_rationale", {}).get("mode", "--")


def pass_label(value: bool) -> str:
    return "pass" if value else "fail"


def collapse_ids(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "--"


def excerpt(text: str, *, max_chars: int = 180) -> str:
    condensed = " ".join(text.split())
    if len(condensed) <= max_chars:
        return condensed
    return condensed[: max_chars - 3] + "..."


def common_preamble(title: str) -> list[str]:
    return [
        f"# {title}",
        "",
        "- `paraphrase_v0` is a development set.",
        "- `blind_v1_3` is the current blind evidence layer.",
        "- DPO is for preference contrast, not lexical-token repair.",
        "- No broad generalization claim is justified from this layer alone.",
        f"- Stable accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- `{DPO_EVIDENCE_CHECKPOINT}` remains evidence only and is not promoted here.",
        "",
    ]


def load_result_map(path: Path, *, key: str = "scenario_id") -> dict[str, dict[str, Any]]:
    return {record[key]: record for record in read_jsonl(path)}


def blind_probe_specs(path: Path) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for yaml_path in sorted(path.glob("*.yaml")):
        spec = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        specs[spec["id"]] = spec
    return specs


def probe_category_of_probe_id(probe_id: str) -> str:
    if "_blind_" in probe_id:
        return probe_id.rsplit("_blind_", 1)[0]
    return probe_id.rsplit("_", 1)[0]


def blind_holdout_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    low_risk = [
        record
        for record in results
        if record.get("metadata", {}).get("base_scenario_id") in LOW_RISK_BASE_IDS
    ]
    ambiguous = [
        record
        for record in results
        if record.get("metadata", {}).get("base_scenario_id") == "ambiguous_goal_001"
    ]
    catastrophic = [
        record for record in results if detect_catastrophic_reasons(record)
    ]
    return {
        "strict_pass_count": sum(1 for record in results if record.get("pass") is True),
        "total": len(results),
        "policy_rationale_present": sum(
            1 for record in results if record.get("score", {}).get("policy_rationale_present")
        ),
        "mode_match": sum(
            1 for record in results if record.get("score", {}).get("mode_match")
        ),
        "low_risk_mode_match": sum(
            1 for record in low_risk if record.get("score", {}).get("mode_match")
        ),
        "low_risk_total": len(low_risk),
        "ambiguous_clarify_count": sum(
            1 for record in ambiguous if mode_of(record) == "clarify"
        ),
        "ambiguous_total": len(ambiguous),
        "catastrophic_safety_failures": len(catastrophic),
        "catastrophic_ids": [record["scenario_id"] for record in catastrophic],
    }


def probe_summary(
    results: list[dict[str, Any]],
    probe_specs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in results:
        probe_id = record["id"]
        category = probe_specs.get(probe_id, {}).get(
            "probe_category", probe_category_of_probe_id(probe_id)
        )
        by_category[category].append(record)

    rows: list[dict[str, Any]] = []
    total_pass = 0
    for category in PRIMARY_CATEGORIES:
        category_results = sorted(by_category.get(category, []), key=lambda item: item["id"])
        pass_count = sum(1 for record in category_results if record.get("pass") is True)
        total_pass += pass_count
        rows.append(
            {
                "category": category,
                "records": category_results,
                "pass_count": pass_count,
                "total": len(category_results),
                "failed_ids": [record["id"] for record in category_results if not record.get("pass")],
            }
        )
    return {"rows": rows, "total_pass": total_pass, "total": len(results)}


def compare_holdout_results(
    dpo_map: dict[str, dict[str, Any]],
    sft_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: list[list[str]] = []
    dpo_better: list[str] = []
    dpo_worse: list[str] = []
    both_fail: list[str] = []
    both_pass: list[str] = []
    mode_regressions: list[str] = []

    for scenario_id in sorted(dpo_map):
        dpo = dpo_map[scenario_id]
        sft = sft_map[scenario_id]
        dpo_pass = bool(dpo.get("pass"))
        sft_pass = bool(sft.get("pass"))
        dpo_mode = mode_of(dpo)
        sft_mode = mode_of(sft)
        if dpo_pass and not sft_pass:
            dpo_better.append(scenario_id)
        elif sft_pass and not dpo_pass:
            dpo_worse.append(scenario_id)
        elif dpo_pass and sft_pass:
            both_pass.append(scenario_id)
        else:
            both_fail.append(scenario_id)
        if dpo_mode != sft_mode:
            mode_regressions.append(scenario_id)

        rows.append(
            [
                f"`{scenario_id}`",
                f"`{dpo.get('metadata', {}).get('base_scenario_id', '--')}`",
                pass_label(dpo_pass),
                pass_label(sft_pass),
                (
                    "`dpo_only_pass`"
                    if dpo_pass and not sft_pass
                    else "`dpo_only_fail`"
                    if sft_pass and not dpo_pass
                    else "`both_pass`"
                    if dpo_pass and sft_pass
                    else "`both_fail`"
                ),
                f"`{dpo_mode}`",
                f"`{sft_mode}`",
                f"`{dpo_mode} -> {sft_mode}`" if dpo_mode != sft_mode else "--",
            ]
        )

    return {
        "rows": rows,
        "dpo_better": dpo_better,
        "dpo_worse": dpo_worse,
        "both_fail": both_fail,
        "both_pass": both_pass,
        "mode_regressions": mode_regressions,
    }


def missing_required_behaviors(result: dict[str, Any]) -> list[str]:
    return [
        behavior
        for behavior, present in result.get("score", {}).get("required_behavior_hits", {}).items()
        if not present
    ]


def missing_must_include(result: dict[str, Any]) -> list[str]:
    return [
        phrase
        for phrase, present in result.get("score", {}).get("must_include_hits", {}).items()
        if not present
    ]


def failure_labels_for_probe(category: str, result: dict[str, Any]) -> list[str]:
    if result.get("pass"):
        return []

    labels: list[str] = []
    score = result.get("score", {})
    if not score.get("mode_match", False):
        labels.append(FAILURE_CLASS_MODE_DRIFT)

    if missing_required_behaviors(result):
        labels.append(PROBE_CATEGORY_TO_FAILURE_CLASS[category])

    missing_must = missing_must_include(result)
    if missing_must:
        labels.append(FAILURE_CLASS_LITERAL_TOKEN)
        if score.get("mode_match", False) and not missing_required_behaviors(result):
            labels.append(FAILURE_CLASS_SCORER_BRITTLE)

    deduped: list[str] = []
    for label in labels:
        if label not in deduped:
            deduped.append(label)
    for label in deduped:
        assert label in APPROVED_FAILURE_CLASSES
    return deduped


def dominant_failure_class(category: str, failed_records: list[dict[str, Any]]) -> tuple[str, list[str]]:
    if not failed_records:
        return "--", []

    label_counter: Counter[str] = Counter()
    for record in failed_records:
        for label in failure_labels_for_probe(category, record):
            label_counter[label] += 1

    category_specific = PROBE_CATEGORY_TO_FAILURE_CLASS[category]
    if label_counter[FAILURE_CLASS_MODE_DRIFT]:
        dominant = FAILURE_CLASS_MODE_DRIFT
    elif label_counter[category_specific]:
        dominant = category_specific
    elif label_counter[FAILURE_CLASS_LITERAL_TOKEN]:
        dominant = FAILURE_CLASS_LITERAL_TOKEN
    elif label_counter[FAILURE_CLASS_SCORER_BRITTLE]:
        dominant = FAILURE_CLASS_SCORER_BRITTLE
    else:
        dominant = category_specific

    supporting = [label for label, _ in label_counter.most_common() if label != dominant]
    return dominant, supporting


def selected_category_summary(
    selected_pairs: list[dict[str, Any]],
    probe_specs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    audits = [audit_pair(pair) for pair in selected_pairs]
    pairs_by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    audits_by_category: dict[str, list[Any]] = defaultdict(list)
    for pair, audit in zip(selected_pairs, audits, strict=True):
        pairs_by_category[audit.primary_category].append(pair)
        audits_by_category[audit.primary_category].append(audit)

    summary_rows: list[dict[str, Any]] = []
    selected_quality_issues: list[str] = []
    for pair, audit in zip(selected_pairs, audits, strict=True):
        if not audit.safe_for_dpo_smoke:
            selected_quality_issues.append(pair["id"])

    blind_terms_by_category: dict[str, list[str]] = defaultdict(list)
    for spec in probe_specs.values():
        category = spec["probe_category"]
        for phrase in spec.get("must_include", []):
            if phrase not in blind_terms_by_category[category]:
                blind_terms_by_category[category].append(phrase)

    for category in PRIMARY_CATEGORIES:
        category_pairs = pairs_by_category.get(category, [])
        blind_terms = blind_terms_by_category.get(category, [])
        blind_term_hits: list[str] = []
        blind_term_gaps: list[str] = []
        for phrase in blind_terms:
            hit_count = sum(
                1 for pair in category_pairs if contains_phrase(pair["chosen"], phrase)
            )
            if hit_count > 0:
                blind_term_hits.append(f"{phrase}={hit_count}/{len(category_pairs)}")
            else:
                blind_term_gaps.append(phrase)
        summary_rows.append(
            {
                "category": category,
                "count": len(category_pairs),
                "safe_count": sum(
                    1 for audit in audits_by_category.get(category, []) if audit.safe_for_dpo_smoke
                ),
                "blind_term_hits": blind_term_hits,
                "blind_term_gaps": blind_term_gaps,
                "pairs": category_pairs,
            }
        )

    return {
        "rows": summary_rows,
        "selected_quality_issues": selected_quality_issues,
        "all_safe": not selected_quality_issues,
    }


def load_train_log_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    final_entry = records[-1] if records else {}
    max_seen_step = max((record.get("step", 0) for record in records), default=0)
    return {
        "step_count": max_seen_step,
        "final_train_loss": final_entry.get("train_loss"),
        "final_epoch": final_entry.get("epoch"),
    }


def coverage_assessment(
    category_row: dict[str, Any],
    blind_row: dict[str, Any],
) -> str:
    if blind_row["pass_count"] == blind_row["total"]:
        return "yes"
    if category_row["blind_term_gaps"]:
        return "partial"
    return "partial"


def coverage_diagnosis(
    *,
    category: str,
    category_row: dict[str, Any],
    dev_row: dict[str, Any],
    blind_row: dict[str, Any],
    dpo_probe_row: dict[str, Any],
    sft_probe_row: dict[str, Any],
    run_config: dict[str, Any],
    train_log_summary: dict[str, Any],
) -> str:
    if blind_row["pass_count"] == blind_row["total"] and dev_row["pass_count"] == dev_row["total"]:
        return NO_COVERAGE_GAP

    if category_row["count"] != 4 or category_row["safe_count"] != 4:
        return COVERAGE_DIAG_AMBIGUOUS_CONTRAST

    dominant_failure = dpo_probe_row["dominant_failure"]
    if category in {
        "overrefusal_vs_bounded_execute",
        "unnecessary_escalation_vs_low_risk_execute",
    } and dev_row["pass_count"] == 2 and blind_row["pass_count"] == 0:
        return COVERAGE_DIAG_TOO_FEW_LOW_RISK

    if category == "audit_evasion_vs_audit_preservation":
        if "logged" in category_row["blind_term_gaps"]:
            return COVERAGE_DIAG_UNDER_SPECIFIED
        return COVERAGE_DIAG_SCORER_BRITTLE

    if category == "unsafe_compliance_vs_safe_challenge" and dominant_failure == FAILURE_CLASS_MODE_DRIFT:
        if run_config.get("max_steps", 0) <= 12 and run_config.get("beta", 1.0) <= 0.05:
            return COVERAGE_DIAG_INSUFFICIENT_VARIATION
        return COVERAGE_DIAG_TRAINER_INTENSITY

    if dominant_failure == FAILURE_CLASS_SCORER_BRITTLE:
        return COVERAGE_DIAG_SCORER_BRITTLE

    if dominant_failure == FAILURE_CLASS_LITERAL_TOKEN and blind_row["pass_count"] == sft_probe_row["pass_count"]:
        return COVERAGE_DIAG_SCORER_BRITTLE

    if train_log_summary["step_count"] > 12 or run_config.get("beta", 1.0) > 0.05:
        return COVERAGE_DIAG_TRAINER_INTENSITY

    return COVERAGE_DIAG_INSUFFICIENT_VARIATION


def holdout_failure_shape(
    dpo_holdout_results: list[dict[str, Any]],
    sft_holdout_results: list[dict[str, Any]],
) -> Counter[str]:
    categories: Counter[str] = Counter()
    sft_map = {record["scenario_id"]: record for record in sft_holdout_results}
    for record in dpo_holdout_results:
        if record.get("pass"):
            continue
        if not record.get("score", {}).get("mode_match", False):
            categories[FAILURE_CLASS_MODE_DRIFT] += 1
            continue
        if missing_must_include(record):
            paired = sft_map.get(record["scenario_id"])
            if paired and paired.get("pass"):
                categories[FAILURE_CLASS_LITERAL_TOKEN] += 1
            else:
                categories[FAILURE_CLASS_SCORER_BRITTLE] += 1
            continue
        if missing_required_behaviors(record):
            base_scenario_id = record.get("metadata", {}).get("base_scenario_id", "")
            if base_scenario_id == "shutdown_conflict_001":
                categories[FAILURE_CLASS_SHUTDOWN_HALT] += 1
            else:
                categories[FAILURE_CLASS_MODE_DRIFT] += 1
            continue
        categories[FAILURE_CLASS_MODE_DRIFT] += 1
    return categories


def choose_final_status(
    *,
    dpo_holdout_metrics: dict[str, Any],
    dpo_probe_summary: dict[str, Any],
    sft_probe_summary: dict[str, Any],
    selected_summary: dict[str, Any],
    coverage_rows: list[dict[str, Any]],
    holdout_failures: Counter[str],
    run_config: dict[str, Any],
) -> tuple[str, list[str]]:
    rationale: list[str] = []

    if selected_summary["selected_quality_issues"]:
        rationale.append(
            "Selected DPO pairs re-audited through `audit_pair` still contain quality problems, so the blind failure cannot be blamed on paraphrase breadth alone."
        )
        return STATUS_DPO_DATA_REWRITE, rationale

    dpo_underperformed_categories = [
        row["category"] for row in coverage_rows if row["underperformed_vs_sft"]
    ]
    probe_gap = sft_probe_summary["total_pass"] - dpo_probe_summary["total_pass"]
    if probe_gap <= 0:
        rationale.append(
            "DPO no longer trails SFT on blind probes, so a DPO-specific repair recommendation is not justified from this evidence."
        )
        return STATUS_RUNTIME_EVAL_NEXT, rationale

    dominant_coverage_diagnoses = Counter(
        row["coverage_diagnosis"] for row in coverage_rows if row["coverage_diagnosis"] != "--"
    )

    if all(
        diagnosis in {COVERAGE_DIAG_SCORER_BRITTLE, COVERAGE_DIAG_UNDER_SPECIFIED}
        for diagnosis in dominant_coverage_diagnoses
    ) and FAILURE_CLASS_MODE_DRIFT not in holdout_failures:
        rationale.append(
            "The remaining blind misses are overwhelmingly lexical while holdout structure stays intact, so scorer dual-track analysis becomes more plausible than another DPO change."
        )
        return STATUS_SCORER_DUAL_TRACK, rationale

    if (
        run_config.get("max_steps", 0) <= 12
        and run_config.get("beta", 1.0) <= 0.05
        and run_config.get("learning_rate", 1.0) <= 3e-6
    ):
        rationale.append(
            "The accepted v1.2.4 retry already used the reduced-intensity recipe (`max_steps=12`, `beta=0.05`, `learning_rate=3e-6`), so blind probe losses are less consistent with another pure intensity reduction."
        )
    elif holdout_failures[FAILURE_CLASS_MODE_DRIFT]:
        rationale.append(
            "Blind failures look like overcorrection despite otherwise adequate category coverage, so another smaller or lower-LR retry remains plausible."
        )
        return STATUS_SMALLER_OR_LOWER_LR, rationale

    if any(
        row["coverage_diagnosis"] in {COVERAGE_DIAG_TOO_FEW_LOW_RISK, COVERAGE_DIAG_INSUFFICIENT_VARIATION, COVERAGE_DIAG_UNDER_SPECIFIED}
        for row in coverage_rows
    ):
        rationale.append(
            "Selected pairs remain structurally clean and balanced, but the blind failures cluster in categories where the chosen set is too narrow on low-risk execute phrasing, audit logging language, or unsafe-shortcut paraphrase variety."
        )
        rationale.append(
            f"DPO still trails SFT on blind probes (`{dpo_probe_summary['total_pass']}/{dpo_probe_summary['total']}` vs `{sft_probe_summary['total_pass']}/{sft_probe_summary['total']}`), and the underperformance is concentrated in {', '.join(f'`{value}`' for value in dpo_underperformed_categories)}."
        )
        return STATUS_DPO_PROBE_TARGETED_EXPANSION, rationale

    if holdout_failures[FAILURE_CLASS_LITERAL_TOKEN] or holdout_failures[FAILURE_CLASS_MODE_DRIFT]:
        rationale.append(
            "Blind failures look broader than probe-only coverage gaps and include holdout-mode or literal-token misses, which points back toward blind SFT repair."
        )
        return STATUS_BLIND_SFT_REPAIR, rationale

    rationale.append(
        "DPO still underperforms SFT after the smaller retry and the remaining repair paths do not have strong evidence behind them."
    )
    return STATUS_ABANDON_DPO, rationale


def write_delta_review(
    *,
    dpo_holdout_metrics: dict[str, Any],
    sft_holdout_metrics: dict[str, Any],
    dpo_probe_summary: dict[str, Any],
    sft_probe_summary: dict[str, Any],
    holdout_comparison: dict[str, Any],
    output_path: Path,
) -> None:
    lines = common_preamble("V1.3.1 Blind DPO Delta Review")
    lines.extend(
        [
            "## Summary",
            "",
            f"- DPO vs SFT blind holdout strict delta: `{dpo_holdout_metrics['strict_pass_count']}/{dpo_holdout_metrics['total']} - {sft_holdout_metrics['strict_pass_count']}/{sft_holdout_metrics['total']} = {dpo_holdout_metrics['strict_pass_count'] - sft_holdout_metrics['strict_pass_count']}`.",
            f"- DPO vs SFT blind probe delta: `{dpo_probe_summary['total_pass']}/{dpo_probe_summary['total']} - {sft_probe_summary['total_pass']}/{sft_probe_summary['total']} = {dpo_probe_summary['total_pass'] - sft_probe_summary['total_pass']}`.",
            "",
            "## Blind Holdout Per-Scenario Comparison",
            "",
            render_markdown_table(
                [
                    "scenario id",
                    "base scenario",
                    "DPO pass/fail",
                    "SFT pass/fail",
                    "pass/fail delta",
                    "DPO mode",
                    "SFT mode",
                    "mode delta",
                ],
                holdout_comparison["rows"],
            ),
            "",
            "## Outcome Buckets",
            "",
            f"- cases where DPO improved over SFT: {collapse_ids(holdout_comparison['dpo_better'])}",
            f"- cases where DPO regressed vs SFT: {collapse_ids(holdout_comparison['dpo_worse'])}",
            f"- cases where both failed: {collapse_ids(holdout_comparison['both_fail'])}",
            f"- cases where both passed: {collapse_ids(holdout_comparison['both_pass'])}",
            f"- blind holdout mode differences: {collapse_ids(holdout_comparison['mode_regressions'])}",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_probe_failure_review(
    *,
    category_rows: list[dict[str, Any]],
    underperformed_categories: list[str],
    output_path: Path,
) -> None:
    table_rows: list[list[str]] = []
    for row in category_rows:
        table_rows.append(
            [
                f"`{row['category']}`",
                f"`{row['dpo_pass_count']}/{row['total']}`",
                f"`{row['sft_pass_count']}/{row['total']}`",
                f"`{row['delta_vs_sft']}`",
                "yes" if row["underperformed_vs_sft"] else "no",
                f"`{row['dominant_failure']}`" if row["dominant_failure"] != "--" else "--",
                ", ".join(f"`{value}`" for value in row["supporting_failures"]) or "--",
                collapse_ids(row["dpo_failed_ids"]),
                collapse_ids(row["sft_failed_ids"]),
            ]
        )

    lines = common_preamble("V1.3.1 Blind Probe Failure Review")
    lines.extend(
        [
            "## Probe Delta",
            "",
            "- This review compares already-scored blind probe results only; it does not rerun evaluation.",
            f"- categories where DPO underperformed SFT: {collapse_ids(underperformed_categories)}",
            "",
            render_markdown_table(
                [
                    "category",
                    "DPO pass count",
                    "SFT pass count",
                    "DPO-SFT delta",
                    "DPO underperformed SFT",
                    "dominant failure class",
                    "supporting classes",
                    "DPO failed probe ids",
                    "SFT failed probe ids",
                ],
                table_rows,
            ),
            "",
            "## Failure-Class Rules Applied",
            "",
            "- `mode_match == false` maps to `mode_drift`.",
            "- Missing required behaviors map to the behavior-specific class for the probe category.",
            "- Missing `must_include` phrases map to `literal_token_miss`.",
            "- `scorer_brittleness` is used only when expected mode and required behaviors are preserved but lexical coverage fails.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_coverage_review(
    *,
    selected_summary: dict[str, Any],
    dev_probe_summary: dict[str, Any],
    blind_probe_summary: dict[str, Any],
    category_rows: list[dict[str, Any]],
    output_path: Path,
) -> None:
    selected_row_map = {row["category"]: row for row in selected_summary["rows"]}
    dev_row_map = {row["category"]: row for row in dev_probe_summary["rows"]}
    blind_row_map = {row["category"]: row for row in blind_probe_summary["rows"]}

    table_rows: list[list[str]] = []
    for row in category_rows:
        category = row["category"]
        selected_row = selected_row_map[category]
        dev_row = dev_row_map[category]
        blind_row = blind_row_map[category]
        table_rows.append(
            [
                f"`{category}`",
                f"`{selected_row['count']}`",
                f"`{selected_row['safe_count']}/{selected_row['count']}`",
                f"`{dev_row['pass_count']}/{dev_row['total']}`",
                f"`{blind_row['pass_count']}/{blind_row['total']}`",
                "yes" if row["appears_to_cover_failure_pattern"] == "yes" else "partial",
                ", ".join(f"`{value}`" for value in selected_row["blind_term_gaps"]) or "--",
                f"`{row['coverage_diagnosis']}`",
            ]
        )

    lines = common_preamble("V1.3.1 DPO Data Coverage Review")
    lines.extend(
        [
            "## Selected Pair Re-Audit",
            "",
            "- Selected pair counts are re-derived via `audit_pair` from `training.plan_dpo_smoke_v1_1` so this review uses the same taxonomy logic as the original v1.1 smoke selection.",
            f"- selected dataset size: `{sum(row['count'] for row in selected_summary['rows'])}`",
            f"- selected pair quality issues found on re-audit: `{len(selected_summary['selected_quality_issues'])}`",
            "",
            render_markdown_table(
                [
                    "category",
                    "selected pair count",
                    "safe-for-smoke count",
                    "dev probe pass/fail",
                    "blind probe pass/fail",
                    "selected data appears to cover blind failure pattern",
                    "blind-term gaps in selected chosen responses",
                    "category-level diagnosis",
                ],
                table_rows,
            ),
            "",
        ]
    )

    for row in category_rows:
        category = row["category"]
        selected_row = selected_row_map[category]
        lines.extend(
            [
                f"## `{category}`",
                "",
                f"- selected blind-term coverage hits: {', '.join(f'`{value}`' for value in selected_row['blind_term_hits']) or '--'}",
                f"- selected blind-term gaps: {collapse_ids(selected_row['blind_term_gaps'])}",
                f"- blind gap diagnosis: `{row['coverage_diagnosis']}`",
                f"- rationale: {row['coverage_rationale']}",
                "",
            ]
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_repair_options(output_path: Path) -> None:
    lines = common_preamble("V1.3.1 DPO Repair Options")
    option_blocks = {
        "DPO data rewrite": {
            "fixes": "Repairs selected-pair quality problems such as ambiguous chosen/rejected contrast, weak rejected responses, or mislabeled category behavior.",
            "risks": "Highest churn; may invalidate the v1.1 smoke selection and force another full audit pass.",
            "artifacts": "`data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl`, refreshed audit outputs, and replacement selection reports.",
            "when": "Choose only if the selected pairs themselves are flawed or materially inconsistent with the blind failures.",
        },
        "DPO probe-targeted data expansion": {
            "fixes": "Adds more paraphrase and probe variety in the blind-failing categories without discarding the structurally clean core selected set.",
            "risks": "Can overfit to new probes if expansions are too literal or too close to the blind prompts.",
            "artifacts": "A new expansion batch, updated planning/audit report, and a new DPO selection that keeps the original clean pairs while adding targeted coverage.",
            "when": "Choose when the selected pairs are clean but too narrow for the blind failure patterns.",
        },
        "smaller or lower-intensity DPO run": {
            "fixes": "Reduces overcorrection pressure when coverage is already adequate and the failures look like trainer intensity rather than missing data.",
            "risks": "May weaken the development gains without fixing blind generalization if the real issue is data coverage.",
            "artifacts": "A new DPO config, a new retry adapter path, and another replay-only evaluation pass.",
            "when": "Choose only if the data coverage looks adequate and the failure pattern points to intensity.",
        },
        "SFT-only blind repair": {
            "fixes": "Repairs literal-token, format, or mode-discipline blind misses that affect both adapters rather than DPO alone.",
            "risks": "Can move the base checkpoint again before the DPO diagnosis is resolved.",
            "artifacts": "A blind-safe SFT repair batch and a new SFT checkpoint plus blind re-evaluation.",
            "when": "Choose only when the blind misses are mainly non-DPO format or mode problems.",
        },
        "scorer dual-track": {
            "fixes": "Separates strict lexical misses from behaviorally safe outputs when the scorer appears to undercount useful responses.",
            "risks": "Can hide real regressions if applied too early or too broadly.",
            "artifacts": "A scorer analysis proposal, dual-track reporting plan, and no model retraining by default.",
            "when": "Choose only when expected mode and required behaviors are preserved but lexical coverage fails.",
        },
        "runtime evaluation before more training": {
            "fixes": "Shifts effort toward lease, audit, and tool-path execution evidence once prompt behavior is already strong enough.",
            "risks": "Moves away from the blind prompt problem too early if DPO still trails SFT on probes.",
            "artifacts": "A runtime evaluation plan and execution-loop evidence instead of another prompt-only training cycle.",
            "when": "Choose only when blind prompt behavior is already strong enough and remaining uncertainty is runtime execution.",
        },
        "abandon DPO for now": {
            "fixes": "Stops further DPO churn when repeated DPO attempts continue to underperform the accepted SFT checkpoint.",
            "risks": "Leaves blind preference gains on the table and pushes more work back into SFT or runtime-only controls.",
            "artifacts": "A pause decision, preserved DPO evidence, and a new roadmap that prioritizes SFT or runtime work.",
            "when": "Choose only when DPO keeps underperforming and the repair options look weak.",
        },
    }

    for option in REPAIR_OPTIONS:
        block = option_blocks[option]
        lines.extend(
            [
                f"## {option}",
                "",
                f"- what it fixes: {block['fixes']}",
                f"- risks: {block['risks']}",
                f"- required artifacts: {block['artifacts']}",
                f"- when to choose it: {block['when']}",
                "",
            ]
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_decision_review(
    *,
    dpo_holdout_metrics: dict[str, Any],
    sft_holdout_metrics: dict[str, Any],
    dpo_probe_summary: dict[str, Any],
    sft_probe_summary: dict[str, Any],
    selected_summary: dict[str, Any],
    category_rows: list[dict[str, Any]],
    run_config: dict[str, Any],
    train_log_summary: dict[str, Any],
    final_status: str,
    rationale: list[str],
    output_path: Path,
) -> None:
    lines = common_preamble("DPO Readiness Review V1.3.1")
    lines.extend(
        [
            "## Summary",
            "",
            f"- accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`",
            f"- DPO evidence checkpoint remains `{DPO_EVIDENCE_CHECKPOINT}`",
            f"- DPO blind holdout strict: `{dpo_holdout_metrics['strict_pass_count']}/{dpo_holdout_metrics['total']}`",
            f"- SFT blind holdout strict: `{sft_holdout_metrics['strict_pass_count']}/{sft_holdout_metrics['total']}`",
            f"- DPO blind probes: `{dpo_probe_summary['total_pass']}/{dpo_probe_summary['total']}`",
            f"- SFT blind probes: `{sft_probe_summary['total_pass']}/{sft_probe_summary['total']}`",
            f"- selected pairs re-audited clean: `{'yes' if selected_summary['all_safe'] else 'no'}`",
            f"- v1.2.4 run config: `max_steps={run_config.get('max_steps')}`, `beta={run_config.get('beta')}`, `learning_rate={run_config.get('learning_rate')}`",
            f"- v1.2.4 train log summary: `steps={train_log_summary['step_count']}`, `train_loss={train_log_summary['final_train_loss']}`",
            "",
            "## Decision Rationale",
            "",
        ]
    )

    for item in rationale:
        lines.append(f"- {item}")

    underperformed = [row["category"] for row in category_rows if row["underperformed_vs_sft"]]
    lines.extend(
        [
            "",
            "## Category Evidence",
            "",
            f"- categories where DPO underperformed SFT on blind probes: {collapse_ids(underperformed)}",
            "- categories with the clearest probe-targeted coverage gap:",
        ]
    )
    for row in category_rows:
        if row["coverage_diagnosis"] in {
            COVERAGE_DIAG_TOO_FEW_LOW_RISK,
            COVERAGE_DIAG_INSUFFICIENT_VARIATION,
            COVERAGE_DIAG_UNDER_SPECIFIED,
        }:
            lines.append(
                f"  - `{row['category']}` -> `{row['coverage_diagnosis']}`: {row['coverage_rationale']}"
            )

    lines.extend(
        [
            "",
            "## Final Status",
            "",
            final_status,
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def analyze_v1_3_1_blind_dpo_repair(
    *,
    dpo_holdout_results_path: Path,
    sft_holdout_results_path: Path,
    dpo_probe_results_path: Path,
    sft_probe_results_path: Path,
    dev_dpo_probe_results_path: Path,
    run_config_path: Path,
    train_log_path: Path,
    selected_dpo_path: Path,
    blind_probe_dir: Path,
    delta_review_path: Path,
    probe_failure_review_path: Path,
    coverage_review_path: Path,
    repair_options_path: Path,
    decision_review_path: Path,
) -> dict[str, Any]:
    dpo_holdout_results = read_jsonl(dpo_holdout_results_path)
    sft_holdout_results = read_jsonl(sft_holdout_results_path)
    dpo_probe_results = read_jsonl(dpo_probe_results_path)
    sft_probe_results = read_jsonl(sft_probe_results_path)
    dev_dpo_probe_results = read_jsonl(dev_dpo_probe_results_path)
    run_config = load_json(run_config_path)
    train_log = read_jsonl(train_log_path)
    selected_pairs = read_jsonl(selected_dpo_path)
    probe_specs = blind_probe_specs(blind_probe_dir)

    for path in (
        delta_review_path,
        probe_failure_review_path,
        coverage_review_path,
        repair_options_path,
        decision_review_path,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)

    dpo_holdout_map = {record["scenario_id"]: record for record in dpo_holdout_results}
    sft_holdout_map = {record["scenario_id"]: record for record in sft_holdout_results}
    dpo_holdout_metrics = blind_holdout_summary(dpo_holdout_results)
    sft_holdout_metrics = blind_holdout_summary(sft_holdout_results)
    holdout_comparison = compare_holdout_results(dpo_holdout_map, sft_holdout_map)

    dpo_probe_summary = probe_summary(dpo_probe_results, probe_specs)
    sft_probe_summary = probe_summary(sft_probe_results, probe_specs)
    dev_dpo_probe_summary = probe_summary(dev_dpo_probe_results, probe_specs)
    selected_summary = selected_category_summary(selected_pairs, probe_specs)
    train_log_summary = load_train_log_summary(train_log)

    dpo_probe_rows_by_category = {row["category"]: row for row in dpo_probe_summary["rows"]}
    sft_probe_rows_by_category = {row["category"]: row for row in sft_probe_summary["rows"]}
    dev_probe_rows_by_category = {row["category"]: row for row in dev_dpo_probe_summary["rows"]}
    selected_rows_by_category = {row["category"]: row for row in selected_summary["rows"]}

    category_rows: list[dict[str, Any]] = []
    for category in PRIMARY_CATEGORIES:
        dpo_probe_row = dpo_probe_rows_by_category[category]
        sft_probe_row = sft_probe_rows_by_category[category]
        dev_probe_row = dev_probe_rows_by_category[category]
        selected_row = selected_rows_by_category[category]
        dominant_failure, supporting_failures = dominant_failure_class(
            category,
            [record for record in dpo_probe_row["records"] if not record.get("pass")],
        )
        coverage_diag = coverage_diagnosis(
            category=category,
            category_row=selected_row,
            dev_row=dev_probe_row,
            blind_row=dpo_probe_row,
            dpo_probe_row={
                **dpo_probe_row,
                "dominant_failure": dominant_failure,
            },
            sft_probe_row=sft_probe_row,
            run_config=run_config,
            train_log_summary=train_log_summary,
        )
        assert coverage_diag == NO_COVERAGE_GAP or coverage_diag in APPROVED_COVERAGE_DIAGNOSES
        if coverage_diag == NO_COVERAGE_GAP:
            coverage_rationale = (
                "Development and blind probes both stayed at the full category score, so this category does not currently show a blind coverage gap."
            )
        elif coverage_diag == COVERAGE_DIAG_TOO_FEW_LOW_RISK:
            coverage_rationale = (
                "Development probes were clean, but blind low-risk execute probes dropped to 0/2 while the selected set only has four low-risk pairs spread across several tool shapes."
            )
        elif coverage_diag == COVERAGE_DIAG_UNDER_SPECIFIED:
            coverage_rationale = (
                "The selected category examples preserve the right preference direction but miss blind-required phrasing anchors such as `logged`, which leaves the blind variant under-specified."
            )
        elif coverage_diag == COVERAGE_DIAG_SCORER_BRITTLE:
            coverage_rationale = (
                "The blind failures preserve expected mode and core behaviors, but strict lexical hits still fail on tokens such as `recovery`, so the evidence leans toward scorer brittleness rather than a broken selected pair."
            )
        elif coverage_diag == COVERAGE_DIAG_INSUFFICIENT_VARIATION:
            coverage_rationale = (
                "The selected examples cover the core category, but they are too narrow in paraphrase shape to reliably transfer the preference behavior to the blind prompt wording."
            )
        elif coverage_diag == COVERAGE_DIAG_TRAINER_INTENSITY:
            coverage_rationale = (
                "Coverage looks adequate, so the remaining gap points more toward DPO intensity than missing examples."
            )
        elif coverage_diag == COVERAGE_DIAG_TOO_MUCH_PRESSURE:
            coverage_rationale = (
                "The category appears biased toward aggressive challenge or halt pressure relative to what the blind prompt requires."
            )
        else:
            coverage_rationale = (
                "The re-audit suggests the chosen/rejected contrast in this category is too ambiguous to trust as a blind generalization source."
            )

        category_rows.append(
            {
                "category": category,
                "dpo_pass_count": dpo_probe_row["pass_count"],
                "sft_pass_count": sft_probe_row["pass_count"],
                "total": dpo_probe_row["total"],
                "delta_vs_sft": dpo_probe_row["pass_count"] - sft_probe_row["pass_count"],
                "dpo_failed_ids": dpo_probe_row["failed_ids"],
                "sft_failed_ids": sft_probe_row["failed_ids"],
                "underperformed_vs_sft": dpo_probe_row["pass_count"] < sft_probe_row["pass_count"],
                "dominant_failure": dominant_failure,
                "supporting_failures": supporting_failures,
                "appears_to_cover_failure_pattern": coverage_assessment(selected_row, dpo_probe_row),
                "coverage_diagnosis": coverage_diag,
                "coverage_rationale": coverage_rationale,
            }
        )

    category_rows.sort(key=lambda row: row["category"])
    underperformed_categories = [
        row["category"] for row in category_rows if row["underperformed_vs_sft"]
    ]
    holdout_failures = holdout_failure_shape(dpo_holdout_results, sft_holdout_results)
    final_status, rationale = choose_final_status(
        dpo_holdout_metrics=dpo_holdout_metrics,
        dpo_probe_summary=dpo_probe_summary,
        sft_probe_summary=sft_probe_summary,
        selected_summary=selected_summary,
        coverage_rows=category_rows,
        holdout_failures=holdout_failures,
        run_config=run_config,
    )
    assert final_status in APPROVED_STATUSES

    write_delta_review(
        dpo_holdout_metrics=dpo_holdout_metrics,
        sft_holdout_metrics=sft_holdout_metrics,
        dpo_probe_summary=dpo_probe_summary,
        sft_probe_summary=sft_probe_summary,
        holdout_comparison=holdout_comparison,
        output_path=delta_review_path,
    )
    write_probe_failure_review(
        category_rows=category_rows,
        underperformed_categories=underperformed_categories,
        output_path=probe_failure_review_path,
    )
    write_coverage_review(
        selected_summary=selected_summary,
        dev_probe_summary=dev_dpo_probe_summary,
        blind_probe_summary=dpo_probe_summary,
        category_rows=category_rows,
        output_path=coverage_review_path,
    )
    write_repair_options(repair_options_path)
    write_decision_review(
        dpo_holdout_metrics=dpo_holdout_metrics,
        sft_holdout_metrics=sft_holdout_metrics,
        dpo_probe_summary=dpo_probe_summary,
        sft_probe_summary=sft_probe_summary,
        selected_summary=selected_summary,
        category_rows=category_rows,
        run_config=run_config,
        train_log_summary=train_log_summary,
        final_status=final_status,
        rationale=rationale,
        output_path=decision_review_path,
    )

    return {
        "status": final_status,
        "dpo_holdout_strict": dpo_holdout_metrics["strict_pass_count"],
        "sft_holdout_strict": sft_holdout_metrics["strict_pass_count"],
        "dpo_blind_probe_total": dpo_probe_summary["total_pass"],
        "sft_blind_probe_total": sft_probe_summary["total_pass"],
        "underperformed_categories": underperformed_categories,
        "delta_review_path": str(delta_review_path),
        "probe_failure_review_path": str(probe_failure_review_path),
        "coverage_review_path": str(coverage_review_path),
        "repair_options_path": str(repair_options_path),
        "decision_review_path": str(decision_review_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the v1.3.1 blind DPO repair diagnosis reports from existing blind results."
    )
    parser.add_argument("--dpo-holdout-results", type=Path, default=DEFAULT_DPO_HOLDOUT_RESULTS)
    parser.add_argument("--sft-holdout-results", type=Path, default=DEFAULT_SFT_HOLDOUT_RESULTS)
    parser.add_argument("--dpo-probe-results", type=Path, default=DEFAULT_DPO_PROBE_RESULTS)
    parser.add_argument("--sft-probe-results", type=Path, default=DEFAULT_SFT_PROBE_RESULTS)
    parser.add_argument(
        "--dev-dpo-probe-results", type=Path, default=DEFAULT_DEV_DPO_PROBE_RESULTS
    )
    parser.add_argument("--run-config", type=Path, default=DEFAULT_RUN_CONFIG)
    parser.add_argument("--train-log", type=Path, default=DEFAULT_TRAIN_LOG)
    parser.add_argument("--selected-dpo", type=Path, default=DEFAULT_SELECTED_DPO)
    parser.add_argument("--blind-probe-dir", type=Path, default=DEFAULT_BLIND_PROBE_DIR)
    parser.add_argument("--delta-review", type=Path, default=DEFAULT_DELTA_REVIEW)
    parser.add_argument(
        "--probe-failure-review", type=Path, default=DEFAULT_PROBE_FAILURE_REVIEW
    )
    parser.add_argument("--coverage-review", type=Path, default=DEFAULT_COVERAGE_REVIEW)
    parser.add_argument("--repair-options", type=Path, default=DEFAULT_REPAIR_OPTIONS)
    parser.add_argument("--decision-review", type=Path, default=DEFAULT_DECISION_REVIEW)
    args = parser.parse_args(argv)

    summary = analyze_v1_3_1_blind_dpo_repair(
        dpo_holdout_results_path=args.dpo_holdout_results,
        sft_holdout_results_path=args.sft_holdout_results,
        dpo_probe_results_path=args.dpo_probe_results,
        sft_probe_results_path=args.sft_probe_results,
        dev_dpo_probe_results_path=args.dev_dpo_probe_results,
        run_config_path=args.run_config,
        train_log_path=args.train_log,
        selected_dpo_path=args.selected_dpo,
        blind_probe_dir=args.blind_probe_dir,
        delta_review_path=args.delta_review,
        probe_failure_review_path=args.probe_failure_review,
        coverage_review_path=args.coverage_review,
        repair_options_path=args.repair_options,
        decision_review_path=args.decision_review,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
