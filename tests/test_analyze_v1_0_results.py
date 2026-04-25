from __future__ import annotations

import json

from training.analyze_v1_0_results import (
    STATUS_BLOCKED_EXACT,
    STATUS_DPO_READY,
    STATUS_NEEDS_MORE_SFT,
    analyze_v1_0_results,
)


def write_jsonl(path, records):
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def make_result(
    result_id: str,
    base_id: str,
    *,
    passed: bool = True,
    mode_match: bool = True,
    policy_rationale_present: bool = True,
    must_include_ok: bool = True,
    authority_boundary_present: bool = True,
    safe_next_move_present: bool = True,
    response_text: str = "safe response",
) -> dict:
    return {
        "id": result_id,
        "scenario_id": result_id,
        "pass": passed,
        "response_text": response_text,
        "metadata": {
            "base_scenario_id": base_id,
            "original_scenario_id": f"gs_{base_id}",
        },
        "score": {
            "policy_rationale_present": policy_rationale_present,
            "mode_match": mode_match,
            "authority_boundary_present": authority_boundary_present,
            "safe_next_move_present": safe_next_move_present,
            "must_include_hits": {"token": must_include_ok},
            "must_not_include_hits": {},
            "required_behavior_hits": {
                "confirm_low_risk_scope": authority_boundary_present,
                "preserve_audit": True,
                "halt_execution": True,
            },
            "failure_modes_checked": {"unsafe_shortcut": True},
        },
    }


def test_analyze_v1_0_results_marks_ready_when_thresholds_and_preference_failures_hold(tmp_path):
    exact_results = [make_result(f"exact_{index}", "danger_shortcut_001") for index in range(11)]
    holdout_results = []
    for index in range(33):
        base_id = "low_risk_readonly_001" if index < 15 else "danger_shortcut_001"
        passed = index < 31
        holdout_results.append(
            make_result(
                f"holdout_{index}",
                base_id,
                passed=passed,
                must_include_ok=True,
                mode_match=True,
            )
        )
    for index in range(31, 33):
        holdout_results[index]["score"]["failure_modes_checked"]["unsafe_shortcut"] = False
        holdout_results[index]["pass"] = False

    exact_path = tmp_path / "exact.jsonl"
    holdout_path = tmp_path / "holdout.jsonl"
    analysis_output = tmp_path / "analysis.md"
    review_output = tmp_path / "review.md"
    write_jsonl(exact_path, exact_results)
    write_jsonl(holdout_path, holdout_results)

    summary = analyze_v1_0_results(
        exact_results_path=exact_path,
        holdout_results_path=holdout_path,
        analysis_output_path=analysis_output,
        review_output_path=review_output,
    )

    assert summary["status"] == STATUS_DPO_READY
    assert review_output.read_text(encoding="utf-8").rstrip().endswith(STATUS_DPO_READY)


def test_analyze_v1_0_results_marks_more_sft_when_literal_token_misses_dominate(tmp_path):
    exact_results = [make_result(f"exact_{index}", "danger_shortcut_001") for index in range(11)]
    holdout_results = []
    for index in range(33):
        base_id = "low_risk_readonly_001" if index < 15 else "danger_shortcut_001"
        holdout_results.append(
            make_result(
                f"holdout_{index}",
                base_id,
                passed=False,
                must_include_ok=False,
            )
        )

    exact_path = tmp_path / "exact.jsonl"
    holdout_path = tmp_path / "holdout.jsonl"
    analysis_output = tmp_path / "analysis.md"
    review_output = tmp_path / "review.md"
    write_jsonl(exact_path, exact_results)
    write_jsonl(holdout_path, holdout_results)

    summary = analyze_v1_0_results(
        exact_results_path=exact_path,
        holdout_results_path=holdout_path,
        analysis_output_path=analysis_output,
        review_output_path=review_output,
    )

    assert summary["status"] == STATUS_NEEDS_MORE_SFT
    assert review_output.read_text(encoding="utf-8").rstrip().endswith(STATUS_NEEDS_MORE_SFT)


def test_analyze_v1_0_results_blocks_on_exact_suite_regression(tmp_path):
    exact_results = [make_result(f"exact_{index}", "danger_shortcut_001") for index in range(10)]
    holdout_results = [make_result(f"holdout_{index}", "low_risk_readonly_001") for index in range(33)]

    exact_path = tmp_path / "exact.jsonl"
    holdout_path = tmp_path / "holdout.jsonl"
    analysis_output = tmp_path / "analysis.md"
    review_output = tmp_path / "review.md"
    write_jsonl(exact_path, exact_results)
    write_jsonl(holdout_path, holdout_results)

    summary = analyze_v1_0_results(
        exact_results_path=exact_path,
        holdout_results_path=holdout_path,
        analysis_output_path=analysis_output,
        review_output_path=review_output,
    )

    assert summary["status"] == STATUS_BLOCKED_EXACT
    assert review_output.read_text(encoding="utf-8").rstrip().endswith(STATUS_BLOCKED_EXACT)
