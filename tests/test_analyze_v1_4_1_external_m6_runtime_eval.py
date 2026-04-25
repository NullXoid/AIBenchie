from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_4_1_external_m6_runtime_eval import (
    APPROVED_STATUSES,
    EXPECTED_ARTIFACT,
    EXPECTED_BACKEND_COMMIT,
    EXPECTED_BACKEND_TAG,
    EXPECTED_DESKTOP_COMMIT,
    EXPECTED_FINAL_STATUS,
    EXPECTED_RELEASE_TAG,
    REQUIRED_TRUE_FIELDS,
    STATUS_INCOMPLETE,
    STATUS_INVALID,
    STATUS_READY,
    analyze_v1_4_1_external_m6_runtime_eval,
)
from training.analyze_v1_4_runtime_eval_readiness import STATUS_WAITING


REPORTS_RUNTIME_DIR = ROOT / "reports" / "runtime"
RUNTIME_EVAL_DIR = ROOT / "evals" / "runtime" / "v1_4"
BLIND_HOLDOUT_DIR = ROOT / "evals" / "holdout" / "blind_v1_3"
BLIND_PROBE_DIR = ROOT / "evals" / "dpo_probes" / "blind_v1_3"
BLIND_PROBE_CONTRACTFIX_DIR = ROOT / "evals" / "dpo_probes" / "blind_v1_3_contractfix_v1_3_5"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def last_nonempty_line(path: Path) -> str:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][-1]


def suite_hashes(directory: Path) -> dict[str, str]:
    return {path.name: sha256(path) for path in sorted(directory.glob("*.yaml"))}


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_valid_evidence() -> dict[str, object]:
    payload: dict[str, object] = {
        "artifact": EXPECTED_ARTIFACT,
        "release_tag": EXPECTED_RELEASE_TAG,
        "desktop_commit": EXPECTED_DESKTOP_COMMIT,
        "backend_tag": EXPECTED_BACKEND_TAG,
        "backend_commit": EXPECTED_BACKEND_COMMIT,
        "final_status": EXPECTED_FINAL_STATUS,
    }
    payload.update({field: True for field in REQUIRED_TRUE_FIELDS})
    return payload


def write_consistent_markdown_bundle(runtime_dir: Path) -> tuple[Path, Path, Path, Path]:
    surface_report_path = runtime_dir / "M17_RC2_LV7_RUNTIME_SURFACE_VERIFICATION_REPORT.md"
    contract_report_path = runtime_dir / "M17_LV7_V1_4_CONTRACT_TEST_REPORT.md"
    runner_readiness_report_path = runtime_dir / "M17_LV7_V1_4_SCENARIO_RUNNER_READINESS.md"
    decision_report_path = runtime_dir / "M17_NEXT_STEP_DECISION.md"

    write_markdown(
        surface_report_path,
        [
            "# surface",
            EXPECTED_ARTIFACT,
            EXPECTED_RELEASE_TAG,
            EXPECTED_DESKTOP_COMMIT,
            EXPECTED_BACKEND_TAG,
            EXPECTED_BACKEND_COMMIT,
            EXPECTED_FINAL_STATUS,
        ],
    )
    write_markdown(
        contract_report_path,
        [
            "# contract",
            "policy_rationale",
            "nullxoid_signal",
            "ToolFollowup",
            "Hybrid",
        ],
    )
    write_markdown(
        runner_readiness_report_path,
        [
            "# runner",
            EXPECTED_ARTIFACT,
            EXPECTED_RELEASE_TAG,
            EXPECTED_DESKTOP_COMMIT,
            EXPECTED_BACKEND_TAG,
            EXPECTED_BACKEND_COMMIT,
            "scorer changes",
            "blind-suite mutation",
            "adapter promotion",
            "backend drift",
        ],
    )
    write_markdown(
        decision_report_path,
        [
            "# decision",
            EXPECTED_FINAL_STATUS,
        ],
    )
    return (
        surface_report_path,
        contract_report_path,
        runner_readiness_report_path,
        decision_report_path,
    )


def test_v1_4_1_missing_external_evidence_fails_closed_to_incomplete_without_mutation(tmp_path):
    scoring_path = ROOT / "evals" / "scoring.py"
    run_eval_path = ROOT / "evals" / "run_eval.py"
    scoring_hash_before = sha256(scoring_path)
    run_eval_hash_before = sha256(run_eval_path)
    blind_holdout_hashes_before = suite_hashes(BLIND_HOLDOUT_DIR)
    blind_probe_hashes_before = suite_hashes(BLIND_PROBE_DIR)
    blind_probe_contractfix_hashes_before = suite_hashes(BLIND_PROBE_CONTRACTFIX_DIR)

    runtime_dir = tmp_path / "reports" / "runtime"
    summary = analyze_v1_4_1_external_m6_runtime_eval(
        evidence_review_report_path=runtime_dir / "V1_4_1_EXTERNAL_M6_EVIDENCE_REVIEW.md",
        runtime_execution_plan_report_path=runtime_dir / "V1_4_1_RUNTIME_EXECUTION_PLAN.md",
        decision_report_path=runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md",
        external_evidence_json_path=runtime_dir / "m17_lv7_v1_4_external_m6_evidence.json",
        wrapper_surface_report_path=None,
        wrapper_contract_report_path=None,
        wrapper_runner_readiness_report_path=None,
        wrapper_decision_report_path=None,
    )

    evidence_review_text = (runtime_dir / "V1_4_1_EXTERNAL_M6_EVIDENCE_REVIEW.md").read_text(
        encoding="utf-8"
    )

    assert summary["status"] == STATUS_INCOMPLETE
    assert summary["external_evidence_valid"] is False
    assert "missing external evidence JSON" in evidence_review_text
    assert last_nonempty_line(runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md") == STATUS_INCOMPLETE
    assert sha256(scoring_path) == scoring_hash_before
    assert sha256(run_eval_path) == run_eval_hash_before
    assert suite_hashes(BLIND_HOLDOUT_DIR) == blind_holdout_hashes_before
    assert suite_hashes(BLIND_PROBE_DIR) == blind_probe_hashes_before
    assert suite_hashes(BLIND_PROBE_CONTRACTFIX_DIR) == blind_probe_contractfix_hashes_before


def test_v1_4_1_missing_required_fields_are_incomplete(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    evidence_json_path = runtime_dir / "m17_lv7_v1_4_external_m6_evidence.json"

    payload = build_valid_evidence()
    del payload["scenario_runner_ready"]
    write_json(evidence_json_path, payload)

    summary = analyze_v1_4_1_external_m6_runtime_eval(
        evidence_review_report_path=runtime_dir / "V1_4_1_EXTERNAL_M6_EVIDENCE_REVIEW.md",
        runtime_execution_plan_report_path=runtime_dir / "V1_4_1_RUNTIME_EXECUTION_PLAN.md",
        decision_report_path=runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md",
        external_evidence_json_path=evidence_json_path,
        wrapper_surface_report_path=None,
        wrapper_contract_report_path=None,
        wrapper_runner_readiness_report_path=None,
        wrapper_decision_report_path=None,
    )

    assert summary["status"] == STATUS_INCOMPLETE
    assert last_nonempty_line(runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md") == STATUS_INCOMPLETE


def test_v1_4_1_malformed_json_is_invalid(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    evidence_json_path = runtime_dir / "m17_lv7_v1_4_external_m6_evidence.json"
    evidence_json_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_json_path.write_text("{not-json", encoding="utf-8")

    summary = analyze_v1_4_1_external_m6_runtime_eval(
        evidence_review_report_path=runtime_dir / "V1_4_1_EXTERNAL_M6_EVIDENCE_REVIEW.md",
        runtime_execution_plan_report_path=runtime_dir / "V1_4_1_RUNTIME_EXECUTION_PLAN.md",
        decision_report_path=runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md",
        external_evidence_json_path=evidence_json_path,
        wrapper_surface_report_path=None,
        wrapper_contract_report_path=None,
        wrapper_runner_readiness_report_path=None,
        wrapper_decision_report_path=None,
    )

    assert summary["status"] == STATUS_INVALID
    assert last_nonempty_line(runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md") == STATUS_INVALID


def test_v1_4_1_identity_mismatch_and_false_contract_booleans_are_invalid(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    evidence_json_path = runtime_dir / "m17_lv7_v1_4_external_m6_evidence.json"

    payload = build_valid_evidence()
    payload["desktop_commit"] = "deadbeef"
    payload["hybrid_blocked"] = False
    write_json(evidence_json_path, payload)

    summary = analyze_v1_4_1_external_m6_runtime_eval(
        evidence_review_report_path=runtime_dir / "V1_4_1_EXTERNAL_M6_EVIDENCE_REVIEW.md",
        runtime_execution_plan_report_path=runtime_dir / "V1_4_1_RUNTIME_EXECUTION_PLAN.md",
        decision_report_path=runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md",
        external_evidence_json_path=evidence_json_path,
        wrapper_surface_report_path=None,
        wrapper_contract_report_path=None,
        wrapper_runner_readiness_report_path=None,
        wrapper_decision_report_path=None,
    )

    assert summary["status"] == STATUS_INVALID
    assert last_nonempty_line(runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md") == STATUS_INVALID


def test_v1_4_1_valid_real_shape_m17_json_without_markdown_yields_ready(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    evidence_json_path = runtime_dir / "m17_lv7_v1_4_external_m6_evidence.json"
    write_json(evidence_json_path, build_valid_evidence())

    summary = analyze_v1_4_1_external_m6_runtime_eval(
        evidence_review_report_path=runtime_dir / "V1_4_1_EXTERNAL_M6_EVIDENCE_REVIEW.md",
        runtime_execution_plan_report_path=runtime_dir / "V1_4_1_RUNTIME_EXECUTION_PLAN.md",
        decision_report_path=runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md",
        external_evidence_json_path=evidence_json_path,
        wrapper_surface_report_path=None,
        wrapper_contract_report_path=None,
        wrapper_runner_readiness_report_path=None,
        wrapper_decision_report_path=None,
    )

    evidence_review_text = (runtime_dir / "V1_4_1_EXTERNAL_M6_EVIDENCE_REVIEW.md").read_text(
        encoding="utf-8"
    )

    assert summary["status"] == STATUS_READY
    assert summary["external_evidence_valid"] is True
    assert "external M17 evidence is present and valid" in evidence_review_text
    assert last_nonempty_line(runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md") == STATUS_READY


def test_v1_4_1_valid_json_plus_consistent_markdown_references_yields_ready(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    evidence_json_path = runtime_dir / "m17_lv7_v1_4_external_m6_evidence.json"
    write_json(evidence_json_path, build_valid_evidence())
    (
        surface_report_path,
        contract_report_path,
        runner_readiness_report_path,
        decision_report_path,
    ) = write_consistent_markdown_bundle(runtime_dir)

    summary = analyze_v1_4_1_external_m6_runtime_eval(
        evidence_review_report_path=runtime_dir / "V1_4_1_EXTERNAL_M6_EVIDENCE_REVIEW.md",
        runtime_execution_plan_report_path=runtime_dir / "V1_4_1_RUNTIME_EXECUTION_PLAN.md",
        decision_report_path=runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md",
        external_evidence_json_path=evidence_json_path,
        wrapper_surface_report_path=surface_report_path,
        wrapper_contract_report_path=contract_report_path,
        wrapper_runner_readiness_report_path=runner_readiness_report_path,
        wrapper_decision_report_path=decision_report_path,
    )

    assert summary["status"] == STATUS_READY
    assert len(summary["markdown_checks"]) == 4
    assert last_nonempty_line(runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md") == STATUS_READY


def test_v1_4_1_explicit_markdown_contradiction_is_invalid(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    evidence_json_path = runtime_dir / "m17_lv7_v1_4_external_m6_evidence.json"
    write_json(evidence_json_path, build_valid_evidence())
    (
        surface_report_path,
        contract_report_path,
        runner_readiness_report_path,
        decision_report_path,
    ) = write_consistent_markdown_bundle(runtime_dir)
    write_markdown(
        decision_report_path,
        [
            "# decision",
            "M17_CONTRACT_REPAIR_NEEDED",
        ],
    )

    summary = analyze_v1_4_1_external_m6_runtime_eval(
        evidence_review_report_path=runtime_dir / "V1_4_1_EXTERNAL_M6_EVIDENCE_REVIEW.md",
        runtime_execution_plan_report_path=runtime_dir / "V1_4_1_RUNTIME_EXECUTION_PLAN.md",
        decision_report_path=runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md",
        external_evidence_json_path=evidence_json_path,
        wrapper_surface_report_path=surface_report_path,
        wrapper_contract_report_path=contract_report_path,
        wrapper_runner_readiness_report_path=runner_readiness_report_path,
        wrapper_decision_report_path=decision_report_path,
    )

    assert summary["status"] == STATUS_INVALID
    assert last_nonempty_line(runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md") == STATUS_INVALID


def test_v1_4_1_analyzer_source_avoids_training_replay_and_wrapper_invocation():
    source = (
        ROOT / "training" / "analyze_v1_4_1_external_m6_runtime_eval.py"
    ).read_text(encoding="utf-8")

    banned_fragments = [
        "train_sft_qlora",
        "run_holdout_eval",
        "run_eval",
        "evaluate_adapter_suite(",
        "subprocess",
        "ctypes",
        "Popen(",
        "DEFAULT_RUNTIME_OUTPUTS",
        "DEFAULT_RUNTIME_RESULTS_REPORT",
        "validate_runtime_outputs(",
    ]
    for fragment in banned_fragments:
        assert fragment not in source, f"Analyzer should not reference forbidden entrypoint or artifact: {fragment}"


def test_v1_4_1_repo_artifacts_exist_and_runtime_gate_advances_from_valid_evidence(tmp_path):
    required = [
        ROOT / "training" / "analyze_v1_4_1_external_m6_runtime_eval.py",
        ROOT / "reports" / "runtime" / "V1_4_1_EXTERNAL_M6_EVIDENCE_REVIEW.md",
        ROOT / "reports" / "runtime" / "V1_4_1_RUNTIME_EXECUTION_PLAN.md",
        ROOT / "reports" / "runtime" / "V1_4_1_NEXT_STEP_DECISION.md",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.4.1 artifact: {path}"

    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_4_NEXT_STEP_DECISION.md") == STATUS_WAITING

    runtime_dir = tmp_path / "reports" / "runtime"
    evidence_json_path = runtime_dir / "m17_lv7_v1_4_external_m6_evidence.json"
    write_json(evidence_json_path, build_valid_evidence())

    summary = analyze_v1_4_1_external_m6_runtime_eval(
        evidence_review_report_path=runtime_dir / "V1_4_1_EXTERNAL_M6_EVIDENCE_REVIEW.md",
        runtime_execution_plan_report_path=runtime_dir / "V1_4_1_RUNTIME_EXECUTION_PLAN.md",
        decision_report_path=runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md",
        external_evidence_json_path=evidence_json_path,
        wrapper_surface_report_path=None,
        wrapper_contract_report_path=None,
        wrapper_runner_readiness_report_path=None,
        wrapper_decision_report_path=None,
    )

    assert summary["status"] == STATUS_READY
    assert last_nonempty_line(runtime_dir / "V1_4_1_NEXT_STEP_DECISION.md") == STATUS_READY
    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_4_1_NEXT_STEP_DECISION.md") in APPROVED_STATUSES
