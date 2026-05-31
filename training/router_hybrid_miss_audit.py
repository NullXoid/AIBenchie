from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from evals import router_gate


RECOMMENDATIONS = {
    "context_dependent_action": "add_context_flags",
    "clear_direct_action_no_context": "add_positive_training_examples",
    "actually_ambiguous_should_R02": "fix_expected_label",
    "mislabeled_case": "fix_expected_label",
    "subtype_only_confusion": "improve_subtype_classifier",
    "needs_manual_review": "manual_review",
}


def load_hybrid_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload.get("results") or []
    if not results:
        raise ValueError(f"{path} has no hybrid results")
    return list(results[0].get("rows") or [])


def audit_reason(row: dict[str, Any]) -> str:
    if row.get("missing_context_flags"):
        return "context_dependent_action"
    if row.get("category") == "ambiguous":
        return "actually_ambiguous_should_R02"
    reason = str(row.get("missed_action_reason") or "")
    if reason == "context_missing":
        return "context_dependent_action"
    if reason in {"subtype_wrong", "subtype_abstained"}:
        return "subtype_only_confusion"
    if reason in {
        "blocked_by_stage0_low_confidence",
        "blocked_by_stage0_low_margin",
        "wrong_stage0_family",
        "threshold_too_strict",
    } or reason.startswith("blocked_by_stage0_"):
        return "clear_direct_action_no_context"
    return "needs_manual_review"


def audit_row(row: dict[str, Any]) -> dict[str, Any]:
    miss_reason = audit_reason(row)
    return {
        "id": row["id"],
        "category": row["category"],
        "template_family": row.get("template_family", "legacy_unknown_family"),
        "text": row["text"],
        "expected_route": row["expected_route"],
        "actual_route": row["actual_route"],
        "stage0_gate": row.get("stage0_gate"),
        "subtype_raw_route": row.get("subtype_raw_route"),
        "missing_context_flags": list(row.get("missing_context_flags") or []),
        "source_missed_action_reason": row.get("missed_action_reason"),
        "stage0_block_reason": row.get("stage0_block_reason"),
        "miss_reason": miss_reason,
        "recommended_next_action": RECOMMENDATIONS[miss_reason],
    }


def build_miss_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missed = [
        row
        for row in rows
        if row.get("expected_route") not in router_gate.SAFE_NON_ACTION_ROUTES
        and row.get("actual_route") != row.get("expected_route")
    ]
    audited = [audit_row(row) for row in missed]
    reason_counts: dict[str, int] = defaultdict(int)
    action_counts: dict[str, int] = defaultdict(int)
    family_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in audited:
        reason_counts[row["miss_reason"]] += 1
        action_counts[row["recommended_next_action"]] += 1
        family_counts[row["template_family"]][row["miss_reason"]] += 1
    return {
        "missed_action_count": len(audited),
        "miss_reason_counts": dict(sorted(reason_counts.items())),
        "recommended_next_action_counts": dict(sorted(action_counts.items())),
        "template_family_reason_counts": {
            family: dict(sorted(counts.items()))
            for family, counts in sorted(family_counts.items())
        },
        "rows": audited,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit missed direct actions from a hybrid router result JSON.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(".suite/local/router_hybrid_miss_audit.json"))
    args = parser.parse_args(argv)
    audit = build_miss_audit(load_hybrid_rows(args.input))
    payload = {
        "suite": "aibenchie.nullxoid.intent_router.hybrid_miss_audit",
        "input": str(args.input),
        **audit,
    }
    write_json(args.output, payload)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "missed_action_count": audit["missed_action_count"],
                "miss_reason_counts": audit["miss_reason_counts"],
                "recommended_next_action_counts": audit["recommended_next_action_counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
