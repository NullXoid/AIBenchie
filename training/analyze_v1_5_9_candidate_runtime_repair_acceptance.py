from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_PROJECT_ROOT))

from training.analyze_v1_4_1_external_m6_runtime_eval import (  # noqa: E402
    ACCEPTED_CHECKPOINT,
    EVIDENCE_ONLY_SFT_ADAPTERS,
    EXPECTED_ARTIFACT,
    EXPECTED_BACKEND_TAG,
    EXPECTED_DESKTOP_COMMIT,
    EXPECTED_RELEASE_TAG,
    PARKED_DPO_ADAPTERS,
)
from training.analyze_v1_4_runtime_eval_readiness import (  # noqa: E402
    PROJECT_ROOT,
    last_nonempty_line,
    write_report,
)
from training.analyze_v1_5_3_candidate_runtime_recheck_bridge import (  # noqa: E402
    CANDIDATE_ALIAS_MODEL_ID,
    CANDIDATE_CHECKPOINT,
    EXPECTED_BASE_MODEL,
)
from training.analyze_v1_5_4_candidate_runtime_scenario_results import (  # noqa: E402
    STATUS_PASSED as STATUS_V1_5_4_PASSED,
    read_json,
    read_jsonl,
    render_markdown_table,
)
from training.analyze_v1_5_5_candidate_runtime_failure_diagnosis import (  # noqa: E402
    STATUS_COMPLETE as STATUS_V1_5_5_COMPLETE,
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"

DEFAULT_RUNTIME_OUTPUTS = REPORTS_RUNTIME_DIR / "v1_5_runtime_outputs.jsonl"
DEFAULT_RUNTIME_EXECUTION_MANIFEST = REPORTS_RUNTIME_DIR / "v1_5_runtime_execution_manifest.json"
DEFAULT_SUITE_MANIFEST_JSON = REPORTS_RUNTIME_DIR / "v1_4_2_runtime_suite_manifest.json"
DEFAULT_V1_5_4_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_4_NEXT_STEP_DECISION.md"
DEFAULT_V1_5_4_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_4_candidate_runtime_results_ingestion.json"
DEFAULT_V1_5_5_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_5_NEXT_STEP_DECISION.md"
DEFAULT_V1_5_5_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_5_candidate_runtime_failure_diagnosis.json"
DEFAULT_V1_5_8_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_8_targeted_repair_attempt_loop.json"

DEFAULT_ACCEPTANCE_REPORT = REPORTS_RUNTIME_DIR / "V1_5_9_CANDIDATE_RUNTIME_REPAIR_ACCEPTANCE.md"
DEFAULT_ACCEPTANCE_MATRIX = REPORTS_RUNTIME_DIR / "V1_5_9_ACCEPTANCE_MATRIX.md"
DEFAULT_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_9_NEXT_STEP_DECISION.md"
DEFAULT_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_9_candidate_runtime_repair_acceptance.json"

STATUS_ACCEPTED = "V1_5_9_CANDIDATE_ACCEPTED_FOR_PROMOTION"
STATUS_BLOCKED = "V1_5_9_ACCEPTANCE_BLOCKED"
APPROVED_STATUSES = {STATUS_ACCEPTED, STATUS_BLOCKED}

EXPECTED_BACKEND_COMMIT = "1b990260e10eaaf34550f4c13abfb92f66073d68"
EXPECTED_BACKEND_ANCHOR_COMMIT = "0da516f332fc9689798cdcba19053f3104c8199f"
EXPECTED_BACKEND_COMMIT_POLICY = "actual_execution_strictness"
NEXT_EXECUTABLE_MILESTONE = "LV7 v1.5.10 - Accepted Runtime Repair Promotion"


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def scenario_rows(records: list[dict[str, Any]], scenario_ids: list[str]) -> list[list[str]]:
    by_id = {record["scenario_id"]: record for record in records}
    rows: list[list[str]] = []
    for scenario_id in scenario_ids:
        record = by_id[scenario_id]
        rows.append(
            [
                scenario_id,
                str(record["final_outcome"]),
                str(record["gate_decision"]),
                str(record["pass2_state"]),
                "yes" if not record["wrapper_contract_failures"] else "no",
                "yes" if not record["model_contract_failures"] else "no",
            ]
        )
    return rows


def validate_acceptance_evidence(
    *,
    runtime_outputs_path: Path,
    runtime_execution_manifest_path: Path,
    suite_manifest_json_path: Path,
    v1_5_4_decision_report_path: Path,
    v1_5_4_json_report_path: Path,
    v1_5_5_decision_report_path: Path,
    v1_5_5_json_report_path: Path,
    v1_5_8_json_report_path: Path,
) -> dict[str, Any]:
    require(
        last_nonempty_line(v1_5_4_decision_report_path) == STATUS_V1_5_4_PASSED,
        f"{display_path(v1_5_4_decision_report_path)} must end with {STATUS_V1_5_4_PASSED}",
    )
    require(
        last_nonempty_line(v1_5_5_decision_report_path) == STATUS_V1_5_5_COMPLETE,
        f"{display_path(v1_5_5_decision_report_path)} must end with {STATUS_V1_5_5_COMPLETE}",
    )
    require((PROJECT_ROOT / ACCEPTED_CHECKPOINT).exists(), f"accepted checkpoint missing: {ACCEPTED_CHECKPOINT}")
    require((PROJECT_ROOT / CANDIDATE_CHECKPOINT).exists(), f"candidate checkpoint missing: {CANDIDATE_CHECKPOINT}")

    suite_manifest = read_json(suite_manifest_json_path)
    records = read_jsonl(runtime_outputs_path)
    execution_manifest = read_json(runtime_execution_manifest_path)
    v1_5_4_payload = read_json(v1_5_4_json_report_path)
    v1_5_5_payload = read_json(v1_5_5_json_report_path)
    v1_5_8_payload = read_json(v1_5_8_json_report_path)

    scenario_ids = suite_manifest["scenario_ids"]
    require(len(records) == len(scenario_ids), "candidate runtime record count must match pinned suite")
    require(
        sorted(record["scenario_id"] for record in records) == sorted(scenario_ids),
        "candidate runtime records must contain each pinned scenario exactly once",
    )

    require(v1_5_4_payload.get("status") == STATUS_V1_5_4_PASSED, "v1.5.4 JSON must report candidate runtime passed")
    require(v1_5_4_payload.get("trusted_record_count") == 10, "v1.5.4 JSON must report ten trusted records")
    require(not v1_5_4_payload.get("wrapper_failures"), "v1.5.4 JSON must contain no wrapper failures")
    require(not v1_5_4_payload.get("model_failures"), "v1.5.4 JSON must contain no model failures")

    require(v1_5_5_payload.get("status") == STATUS_V1_5_5_COMPLETE, "v1.5.5 JSON must report complete diagnosis")
    require(v1_5_5_payload.get("failed_scenarios", 0) == 0, "v1.5.5 JSON must report zero failed scenarios")
    require(
        v1_5_8_payload.get("status") == "V1_5_8_TARGETED_REPAIR_COMPLETE",
        "v1.5.8 repair loop must be complete",
    )
    require(
        v1_5_8_payload.get("final_candidate_runtime_status") == STATUS_V1_5_4_PASSED,
        "v1.5.8 repair loop must end with candidate runtime passed",
    )

    require(execution_manifest.get("model_adapter_path") == CANDIDATE_CHECKPOINT, "manifest has wrong candidate adapter")
    require(execution_manifest.get("alias_model_id") == CANDIDATE_ALIAS_MODEL_ID, "manifest has wrong candidate alias")
    require(execution_manifest.get("backend_commit") == EXPECTED_BACKEND_COMMIT, "manifest has wrong backend_commit")
    require(
        execution_manifest.get("backend_commit_policy") == EXPECTED_BACKEND_COMMIT_POLICY,
        "manifest has wrong backend_commit_policy",
    )
    require(
        execution_manifest.get("backend_anchor_commit") == EXPECTED_BACKEND_ANCHOR_COMMIT,
        "manifest has wrong backend_anchor_commit",
    )

    for record in records:
        scenario_id = record["scenario_id"]
        require(record.get("suite_id") == suite_manifest["suite_id"], f"{scenario_id} has wrong suite_id")
        require(record.get("scenario_file") == suite_manifest["scenario_files"][scenario_id], f"{scenario_id} file mismatch")
        require(record.get("scenario_sha256") == suite_manifest["scenario_sha256"][scenario_id], f"{scenario_id} sha mismatch")
        require(record.get("prompt_sha256") == suite_manifest["prompt_sha256"][scenario_id], f"{scenario_id} prompt hash mismatch")
        require(record.get("model_adapter_path") == CANDIDATE_CHECKPOINT, f"{scenario_id} wrong model_adapter_path")
        require(record.get("wrapper_artifact") == EXPECTED_ARTIFACT, f"{scenario_id} wrong wrapper_artifact")
        require(record.get("release_tag") == EXPECTED_RELEASE_TAG, f"{scenario_id} wrong release_tag")
        require(record.get("desktop_commit") == EXPECTED_DESKTOP_COMMIT, f"{scenario_id} wrong desktop_commit")
        require(record.get("backend_tag") == EXPECTED_BACKEND_TAG, f"{scenario_id} wrong backend_tag")
        require(record.get("backend_commit") == EXPECTED_BACKEND_COMMIT, f"{scenario_id} wrong backend_commit")
        require(record.get("final_outcome") == "pass", f"{scenario_id} must pass")
        require(not record.get("wrapper_contract_failures"), f"{scenario_id} has wrapper failures")
        require(not record.get("model_contract_failures"), f"{scenario_id} has model failures")

    return {
        "records": records,
        "scenario_ids": scenario_ids,
        "scenario_rows": scenario_rows(records, scenario_ids),
    }


def write_acceptance_report(
    *,
    output_path: Path,
    status: str,
    summary: dict[str, Any],
    source_artifacts: dict[str, str],
) -> None:
    rows = summary.get("scenario_rows", [])
    lines = [
        "# V1.5.9 Candidate Runtime Repair Acceptance",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}` until an explicit promotion milestone changes it.",
        f"- Candidate checkpoint under review: `{CANDIDATE_CHECKPOINT}`.",
        f"- Candidate alias: `{CANDIDATE_ALIAS_MODEL_ID}`.",
        f"- Base model: `{EXPECTED_BASE_MODEL}`.",
        f"- Evidence-only SFT adapters remain `{EVIDENCE_ONLY_SFT_ADAPTERS[0]}` and `{EVIDENCE_ONLY_SFT_ADAPTERS[1]}`.",
        f"- Parked DPO adapters remain `{PARKED_DPO_ADAPTERS[0]}` and `{PARKED_DPO_ADAPTERS[1]}`.",
        "- This milestone does not promote the candidate automatically.",
        "",
        "## Evidence Inputs",
        "",
        f"- runtime outputs: `{source_artifacts['runtime_outputs']}`",
        f"- runtime execution manifest: `{source_artifacts['runtime_execution_manifest']}`",
        f"- v1.5.4 decision: `{source_artifacts['v1_5_4_decision_report']}`",
        f"- v1.5.8 repair loop: `{source_artifacts['v1_5_8_repair_loop_json']}`",
        "",
        "## Acceptance Summary",
        "",
        f"- milestone status: `{status}`",
        f"- trusted scenario records: `{len(summary.get('scenario_ids', []))}`",
        "- wrapper failures: `0`",
        "- model failures: `0`",
        "- final runtime status: `V1_5_4_CANDIDATE_RUNTIME_PASSED`",
        "",
        "## Scenario Evidence",
        "",
        render_markdown_table(
            [
                "scenario_id",
                "final_outcome",
                "gate_decision",
                "pass2_state",
                "no_wrapper_failures",
                "no_model_failures",
            ],
            rows,
        ),
        "",
        "## Decision",
        "",
    ]
    if status == STATUS_ACCEPTED:
        lines.extend(
            [
                f"The candidate is accepted for a separate promotion milestone: `{NEXT_EXECUTABLE_MILESTONE}`.",
                "Promotion remains a distinct change because the accepted checkpoint boundary is still the v1.0.5 adapter.",
            ]
        )
    else:
        lines.append("The candidate is not ready for promotion from the current evidence.")
    write_report(output_path, lines)


def write_matrix_report(*, output_path: Path, rows: list[list[str]]) -> None:
    write_report(
        output_path,
        [
            "# V1.5.9 Acceptance Matrix",
            "",
            render_markdown_table(
                [
                    "scenario_id",
                    "final_outcome",
                    "gate_decision",
                    "pass2_state",
                    "no_wrapper_failures",
                    "no_model_failures",
                ],
                rows,
            ),
        ],
    )


def write_decision_report(*, output_path: Path, status: str) -> None:
    lines = [
        "# V1.5.9 Next Step Decision",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- Candidate checkpoint remains `{CANDIDATE_CHECKPOINT}`.",
        "- Candidate promotion is not performed by this milestone.",
        f"- Next executable milestone if accepted: `{NEXT_EXECUTABLE_MILESTONE}`.",
        "",
        status,
    ]
    write_report(output_path, lines)


def analyze_v1_5_9_candidate_runtime_repair_acceptance(
    *,
    runtime_outputs_path: Path = DEFAULT_RUNTIME_OUTPUTS,
    runtime_execution_manifest_path: Path = DEFAULT_RUNTIME_EXECUTION_MANIFEST,
    suite_manifest_json_path: Path = DEFAULT_SUITE_MANIFEST_JSON,
    v1_5_4_decision_report_path: Path = DEFAULT_V1_5_4_DECISION_REPORT,
    v1_5_4_json_report_path: Path = DEFAULT_V1_5_4_JSON_REPORT,
    v1_5_5_decision_report_path: Path = DEFAULT_V1_5_5_DECISION_REPORT,
    v1_5_5_json_report_path: Path = DEFAULT_V1_5_5_JSON_REPORT,
    v1_5_8_json_report_path: Path = DEFAULT_V1_5_8_JSON_REPORT,
    acceptance_report_path: Path = DEFAULT_ACCEPTANCE_REPORT,
    acceptance_matrix_path: Path = DEFAULT_ACCEPTANCE_MATRIX,
    decision_report_path: Path = DEFAULT_DECISION_REPORT,
    json_report_path: Path = DEFAULT_JSON_REPORT,
) -> dict[str, Any]:
    source_artifacts = {
        "runtime_outputs": display_path(runtime_outputs_path),
        "runtime_execution_manifest": display_path(runtime_execution_manifest_path),
        "suite_manifest_json": display_path(suite_manifest_json_path),
        "v1_5_4_decision_report": display_path(v1_5_4_decision_report_path),
        "v1_5_4_json_report": display_path(v1_5_4_json_report_path),
        "v1_5_5_decision_report": display_path(v1_5_5_decision_report_path),
        "v1_5_5_json_report": display_path(v1_5_5_json_report_path),
        "v1_5_8_repair_loop_json": display_path(v1_5_8_json_report_path),
    }
    status = STATUS_ACCEPTED
    summary: dict[str, Any] = {"records": [], "scenario_ids": [], "scenario_rows": []}
    notes: list[str] = []
    try:
        summary = validate_acceptance_evidence(
            runtime_outputs_path=runtime_outputs_path,
            runtime_execution_manifest_path=runtime_execution_manifest_path,
            suite_manifest_json_path=suite_manifest_json_path,
            v1_5_4_decision_report_path=v1_5_4_decision_report_path,
            v1_5_4_json_report_path=v1_5_4_json_report_path,
            v1_5_5_decision_report_path=v1_5_5_decision_report_path,
            v1_5_5_json_report_path=v1_5_5_json_report_path,
            v1_5_8_json_report_path=v1_5_8_json_report_path,
        )
        notes.append("candidate runtime repair evidence is complete and promotion-ready")
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as exc:
        status = STATUS_BLOCKED
        notes.append(str(exc))

    write_acceptance_report(
        output_path=acceptance_report_path,
        status=status,
        summary=summary,
        source_artifacts=source_artifacts,
    )
    write_matrix_report(output_path=acceptance_matrix_path, rows=summary.get("scenario_rows", []))
    write_decision_report(output_path=decision_report_path, status=status)

    payload = {
        "milestone": "LV7 v1.5.9",
        "status": status,
        "accepted_checkpoint": ACCEPTED_CHECKPOINT,
        "candidate_checkpoint": CANDIDATE_CHECKPOINT,
        "candidate_alias_model_id": CANDIDATE_ALIAS_MODEL_ID,
        "candidate_base_model": EXPECTED_BASE_MODEL,
        "wrapper_artifact": EXPECTED_ARTIFACT,
        "release_tag": EXPECTED_RELEASE_TAG,
        "desktop_commit": EXPECTED_DESKTOP_COMMIT,
        "backend_tag": EXPECTED_BACKEND_TAG,
        "backend_commit": EXPECTED_BACKEND_COMMIT,
        "backend_commit_policy": EXPECTED_BACKEND_COMMIT_POLICY,
        "backend_anchor_commit": EXPECTED_BACKEND_ANCHOR_COMMIT,
        "source_artifact_paths": source_artifacts,
        "trusted_record_count": len(summary.get("scenario_ids", [])),
        "pass_count": len(summary.get("scenario_ids", [])) if status == STATUS_ACCEPTED else 0,
        "fail_count": 0 if status == STATUS_ACCEPTED else None,
        "promotion_recommended": status == STATUS_ACCEPTED,
        "promoted_by_this_milestone": False,
        "next_executable_milestone": NEXT_EXECUTABLE_MILESTONE if status == STATUS_ACCEPTED else "resolve blocked acceptance evidence",
        "notes": notes,
    }
    json_report_path.parent.mkdir(parents=True, exist_ok=True)
    json_report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decide whether the passing candidate runtime repair is ready for promotion."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_5_9_candidate_runtime_repair_acceptance()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
