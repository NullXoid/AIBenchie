from __future__ import annotations

from training import router_hybrid_miss_audit as audit


def row(**overrides):
    payload = {
        "id": "one",
        "category": "console_run_command",
        "template_family": "family_run",
        "text": "Run tests now.",
        "expected_route": "console.run_command",
        "actual_route": "ask_clarifying_question",
        "stage0_gate": "G02",
        "subtype_raw_route": None,
        "missing_context_flags": [],
        "missed_action_reason": "blocked_by_stage0_low_confidence",
        "stage0_block_reason": "blocked_by_stage0_low_confidence",
    }
    payload.update(overrides)
    return payload


def test_audit_maps_context_missing_only_from_explicit_missing_flags():
    audited = audit.audit_row(
        row(
            text="Apply that.",
            missing_context_flags=["LAST_ASSISTANT_OFFERED_PATCH"],
            missed_action_reason="context_missing",
        )
    )

    assert audited["miss_reason"] == "context_dependent_action"
    assert audited["recommended_next_action"] == "add_context_flags"


def test_audit_maps_stage0_and_subtype_misses_to_actions():
    blocked = audit.audit_row(row())
    subtype = audit.audit_row(row(missed_action_reason="subtype_wrong", stage0_gate="G04", subtype_raw_route="console.edit_file"))
    ambiguous = audit.audit_row(row(category="ambiguous", missed_action_reason="blocked_by_stage0_clarification"))

    assert blocked["miss_reason"] == "clear_direct_action_no_context"
    assert blocked["recommended_next_action"] == "add_positive_training_examples"
    assert subtype["miss_reason"] == "subtype_only_confusion"
    assert subtype["recommended_next_action"] == "improve_subtype_classifier"
    assert ambiguous["miss_reason"] == "actually_ambiguous_should_R02"
    assert ambiguous["recommended_next_action"] == "fix_expected_label"


def test_build_miss_audit_summarizes_reasons_and_template_families():
    result = audit.build_miss_audit(
        [
            row(id="one", template_family="family_a"),
            row(id="two", template_family="family_a", missed_action_reason="subtype_wrong"),
            row(id="safe", expected_route="answer.question", actual_route="ask_clarifying_question"),
        ]
    )

    assert result["missed_action_count"] == 2
    assert result["miss_reason_counts"] == {
        "clear_direct_action_no_context": 1,
        "subtype_only_confusion": 1,
    }
    assert result["template_family_reason_counts"]["family_a"] == {
        "clear_direct_action_no_context": 1,
        "subtype_only_confusion": 1,
    }
