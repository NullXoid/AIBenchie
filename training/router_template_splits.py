from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any


DEFAULT_SPLIT_WEIGHTS = {
    "train": 70,
    "dev": 10,
    "focused": 10,
    "holdout": 10,
}


def template_family(case: dict[str, Any]) -> str:
    return str(case.get("template_family") or "legacy_unknown_family")


def split_name_for_family(
    family: str,
    *,
    split_weights: dict[str, int] | None = None,
    split_id: str = "template_family_v1",
) -> str:
    weights = split_weights or DEFAULT_SPLIT_WEIGHTS
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("split weights must sum to a positive value")
    digest = hashlib.sha256(f"{split_id}:{family}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % total
    running = 0
    for name, weight in weights.items():
        running += weight
        if bucket < running:
            return name
    return next(reversed(weights))


def split_cases_by_template_family(
    cases: list[dict[str, Any]],
    *,
    split_weights: dict[str, int] | None = None,
    split_id: str = "template_family_v1",
) -> dict[str, list[dict[str, Any]]]:
    weights = split_weights or DEFAULT_SPLIT_WEIGHTS
    splits: dict[str, list[dict[str, Any]]] = {name: [] for name in weights}
    for case in cases:
        family = template_family(case)
        split_name = split_name_for_family(family, split_weights=weights, split_id=split_id)
        copied = {
            **case,
            "template_family": family,
            "template_family_split_id": split_id,
            "template_family_split": split_name,
        }
        splits[split_name].append(copied)
    return splits


def assert_no_template_family_overlap(splits: dict[str, list[dict[str, Any]]]) -> None:
    owners: dict[str, str] = {}
    for split_name, cases in splits.items():
        for case in cases:
            family = template_family(case)
            previous = owners.get(family)
            if previous is not None and previous != split_name:
                raise ValueError(f"template family {family!r} appears in both {previous!r} and {split_name!r}")
            owners[family] = split_name


def split_summary(splits: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        split_name: {
            "case_count": len(cases),
            "template_family_count": len({template_family(case) for case in cases}),
            "legacy_unknown_family_count": sum(1 for case in cases if template_family(case) == "legacy_unknown_family"),
        }
        for split_name, cases in splits.items()
    }


def families_by_split(splits: dict[str, list[dict[str, Any]]]) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for split_name, cases in splits.items():
        grouped[split_name].update(template_family(case) for case in cases)
    return dict(grouped)
