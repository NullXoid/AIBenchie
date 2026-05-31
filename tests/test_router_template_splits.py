from __future__ import annotations

import pytest

from training import router_template_splits


def test_split_cases_by_template_family_keeps_families_in_one_split():
    cases = [
        {"id": "a1", "template_family": "family_a"},
        {"id": "a2", "template_family": "family_a"},
        {"id": "b1", "template_family": "family_b"},
        {"id": "c1", "template_family": "family_c"},
    ]

    splits = router_template_splits.split_cases_by_template_family(cases, split_id="test")

    router_template_splits.assert_no_template_family_overlap(splits)
    families = router_template_splits.families_by_split(splits)
    locations = [split_name for split_name, split_families in families.items() if "family_a" in split_families]
    assert len(locations) == 1
    assert sum(1 for case in splits[locations[0]] if case["template_family"] == "family_a") == 2


def test_legacy_missing_template_family_is_marked_and_reported():
    splits = router_template_splits.split_cases_by_template_family([{"id": "legacy"}], split_id="test")
    summary = router_template_splits.split_summary(splits)

    assert sum(item["legacy_unknown_family_count"] for item in summary.values()) == 1


def test_overlap_assertion_detects_manual_split_mistakes():
    with pytest.raises(ValueError, match="template family"):
        router_template_splits.assert_no_template_family_overlap(
            {
                "train": [{"template_family": "dup"}],
                "holdout": [{"template_family": "dup"}],
            }
        )
