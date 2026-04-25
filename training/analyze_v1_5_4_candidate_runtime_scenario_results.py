from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_PROJECT_ROOT))

from training.analyze_v1_4_1_external_m6_runtime_eval import (  # noqa: E402
    ACCEPTED_CHECKPOINT,
    EVIDENCE_ONLY_SFT_ADAPTERS,
    EXPECTED_ARTIFACT,
    EXPECTED_BACKEND_COMMIT,
    EXPECTED_BACKEND_TAG,
    EXPECTED_DESKTOP_COMMIT,
    EXPECTED_RELEASE_TAG,
    PARKED_DPO_ADAPTERS,
)
from training.analyze_v1_4_2_runtime_scenario_eval_plan import (  # noqa: E402
    DEFAULT_DECISION_REPORT as DEFAULT_V1_4_2_DECISION_REPORT,
    DEFAULT_SCHEMA_JSON,
    DEFAULT_SUITE_MANIFEST_JSON,
    EXPECTED_RUNTIME_SUITE_ID,
    EXPECTED_SCENARIOS,
    STATUS_PLAN_READY,
)
from training.analyze_v1_4_3_runtime_scenario_results import (  # noqa: E402
    ACTUAL_BACKEND_POLICY_NAME,
    BACKEND_IDENTITY_POLICY_READY,
    EXPECTED_FINAL_OUTCOMES,
    EXPECTED_REQUIRED_FIELDS,
    classify_trusted_record,
    display_path,
    load_prerequisites,
    parse_iso8601,
    read_json,
    read_jsonl,
    render_markdown_table,
    require,
    validate_record_types,
    write_failure_review,
)
from training.analyze_v1_4_runtime_eval_readiness import (  # noqa: E402
    PROJECT_ROOT,
    last_nonempty_line,
    write_report,
)
from training.analyze_v1_5_3_candidate_runtime_recheck_bridge import (  # noqa: E402
    CANDIDATE_ALIAS_MODEL_ID,
    CANDIDATE_CHECKPOINT,
    DEFAULT_DECISION_REPORT as DEFAULT_V1_5_3_DECISION_REPORT,
    STATUS_READY as STATUS_V1_5_3_READY,
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"

DEFAULT_V1_4_1_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_4_1_NEXT_STEP_DECISION.md"
DEFAULT_V1_4_3A_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_4_3A_NEXT_STEP_DECISION.md"
DEFAULT_V1_4_3A_POLICY_JSON = REPORTS_RUNTIME_DIR / "v1_4_3a_backend_identity_policy.json"

DEFAULT_RUNTIME_OUTPUTS = REPORTS_RUNTIME_DIR / "v1_5_runtime_outputs.jsonl"
DEFAULT_RUNTIME_RESULTS_REPORT = REPORTS_RUNTIME_DIR / "V1_5_RUNTIME_EVAL_RESULTS.md"
DEFAULT_RUNTIME_EXECUTION_MANIFEST = REPORTS_RUNTIME_DIR / "v1_5_runtime_execution_manifest.json"

DEFAULT_INGESTION_REVIEW_REPORT = REPORTS_RUNTIME_DIR / "V1_5_4_RUNTIME_RESULTS_INGESTION_REVIEW.md"
DEFAULT_RESULT_MATRIX_REPORT = REPORTS_RUNTIME_DIR / "V1_5_4_SCENARIO_RESULT_MATRIX.md"
DEFAULT_WRAPPER_FAILURE_REVIEW_REPORT = REPORTS_RUNTIME_DIR / "V1_5_4_WRAPPER_FAILURE_REVIEW.md"
DEFAULT_MODEL_FAILURE_REVIEW_REPORT = REPORTS_RUNTIME_DIR / "V1_5_4_MODEL_FAILURE_REVIEW.md"
DEFAULT_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_4_NEXT_STEP_DECISION.md"
DEFAULT_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_4_candidate_runtime_results_ingestion.json"

STATUS_PASSED = "V1_5_4_CANDIDATE_RUNTIME_PASSED"
STATUS_WRAPPER_REPAIR = "V1_5_4_CANDIDATE_WRAPPER_REPAIR_NEEDED"
STATUS_MODEL_REPAIR = "V1_5_4_CANDIDATE_MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED"
STATUS_INCOMPLETE = "V1_5_4_CANDIDATE_RUNTIME_RESULTS_INCOMPLETE"
STATUS_INVALID = "V1_5_4_CANDIDATE_RUNTIME_RESULTS_INVALID"

APPROVED_STATUSES = {
    STATUS_PASSED,
    STATUS_WRAPPER_REPAIR,
    STATUS_MODEL_REPAIR,
    STATUS_INCOMPLETE,
    STATUS_INVALID,
}
EXPECTED_SCENARIO_IDS = [scenario_id for scenario_id, _, _ in EXPECTED_SCENARIOS]


def load_backend_identity_policy(path: Path) -> dict[str, Any]:
    require(path.exists(), f"missing backend identity policy: {display_path(path)}")
    payload = read_json(path)
    require(isinstance(payload, dict), "backend identity policy must be a JSON object")
    require(
        payload.get("status") == BACKEND_IDENTITY_POLICY_READY,
        "backend identity policy is not ready",
    )
    require(
        payload.get("selected_policy") == ACTUAL_BACKEND_POLICY_NAME,
        "backend identity policy does not select actual_execution_strictness",
    )
    require(
        payload.get("wrapper_artifact") == EXPECTED_ARTIFACT,
        "backend identity policy has wrong wrapper_artifact",
    )
    require(
        payload.get("release_tag") == EXPECTED_RELEASE_TAG,
        "backend identity policy has wrong release_tag",
    )
    require(
        payload.get("desktop_commit") == EXPECTED_DESKTOP_COMMIT,
        "backend identity policy has wrong desktop_commit",
    )
    require(
        payload.get("backend_tag") == EXPECTED_BACKEND_TAG,
        "backend identity policy has wrong backend_tag",
    )
    require(
        payload.get("frozen_anchor_backend_commit") == EXPECTED_BACKEND_COMMIT,
        "backend identity policy has wrong frozen_anchor_backend_commit",
    )
    actual_backend_commit = payload.get("actual_execution_backend_commit")
    require(
        isinstance(actual_backend_commit, str) and actual_backend_commit.strip(),
        "backend identity policy is missing actual_execution_backend_commit",
    )
    return payload


def load_execution_manifest(
    path: Path,
    *,
    manifest: dict[str, Any],
    backend_identity_policy: dict[str, Any],
) -> dict[str, Any]:
    require(path.exists(), f"missing runtime execution manifest: {display_path(path)}")
    payload = read_json(path)
    require(isinstance(payload, dict), "runtime execution manifest must be a JSON object")

    if "suite_id" in payload:
        require(
            payload["suite_id"] == EXPECTED_RUNTIME_SUITE_ID,
            "runtime execution manifest has wrong suite_id",
        )
    if "scenario_count" in payload:
        require(
            payload["scenario_count"] == len(EXPECTED_SCENARIO_IDS),
            "runtime execution manifest has wrong scenario_count",
        )
    if "scenario_ids" in payload:
        require(
            payload["scenario_ids"] == manifest["scenario_ids"],
            "runtime execution manifest contradicts suite scenario_ids",
        )
    if "scenario_sha256" in payload:
        require(
            payload["scenario_sha256"] == manifest["scenario_sha256"],
            "runtime execution manifest contradicts suite scenario_sha256 values",
        )
    if "prompt_sha256" in payload:
        require(
            payload["prompt_sha256"] == manifest["prompt_sha256"],
            "runtime execution manifest contradicts suite prompt_sha256 values",
        )
    if "model_adapter_path" in payload:
        require(
            str(payload["model_adapter_path"]).replace("\\", "/").rstrip("/") == CANDIDATE_CHECKPOINT.rstrip("/"),
            "runtime execution manifest has wrong model_adapter_path",
        )
    if "alias_model_id" in payload:
        require(
            payload["alias_model_id"] == CANDIDATE_ALIAS_MODEL_ID,
            "runtime execution manifest has wrong alias_model_id",
        )
    if "wrapper_artifact" in payload:
        require(
            payload["wrapper_artifact"] == EXPECTED_ARTIFACT,
            "runtime execution manifest has wrong wrapper_artifact",
        )
    if "release_tag" in payload:
        require(
            payload["release_tag"] == EXPECTED_RELEASE_TAG,
            "runtime execution manifest has wrong release_tag",
        )
    if "desktop_commit" in payload:
        require(
            payload["desktop_commit"] == EXPECTED_DESKTOP_COMMIT,
            "runtime execution manifest has wrong desktop_commit",
        )
    if "backend_tag" in payload:
        require(
            payload["backend_tag"] == EXPECTED_BACKEND_TAG,
            "runtime execution manifest has wrong backend_tag",
        )
    if "backend_commit" in payload:
        require(
            payload["backend_commit"] == backend_identity_policy["actual_execution_backend_commit"],
            "runtime execution manifest has wrong backend_commit",
        )

    require(
        payload.get("backend_commit_policy") == ACTUAL_BACKEND_POLICY_NAME,
        "runtime execution manifest has wrong backend_commit_policy",
    )
    require(
        payload.get("backend_anchor_commit") == EXPECTED_BACKEND_COMMIT,
        "runtime execution manifest has wrong backend_anchor_commit",
    )
    if "backend_anchor_tag" in payload:
        require(
            payload["backend_anchor_tag"] == EXPECTED_BACKEND_TAG,
            "runtime execution manifest has wrong backend_anchor_tag",
        )

    start = None
    end = None
    if "execution_started_at" in payload:
        require(
            isinstance(payload["execution_started_at"], str),
            "runtime execution manifest execution_started_at must be a string",
        )
        start = parse_iso8601(payload["execution_started_at"])
    if "execution_finished_at" in payload:
        require(
            isinstance(payload["execution_finished_at"], str),
            "runtime execution manifest execution_finished_at must be a string",
        )
        end = parse_iso8601(payload["execution_finished_at"])
    if start is not None and end is not None:
        require(start <= end, "runtime execution manifest execution window is inverted")

    payload["_parsed_execution_window"] = (start, end)
    return payload


def validate_record_identity(
    record: dict[str, Any],
    *,
    manifest: dict[str, Any],
    backend_identity_policy: dict[str, Any],
    expected_execution_window: tuple[datetime | None, datetime | None] | None,
    record_label: str,
) -> None:
    scenario_id = record["scenario_id"]
    require(record["suite_id"] == EXPECTED_RUNTIME_SUITE_ID, f"{record_label} has wrong suite_id")
    require(scenario_id in manifest["scenario_ids"], f"{record_label} has unknown scenario_id `{scenario_id}`")
    require(
        record["scenario_file"].replace("\\", "/") == manifest["scenario_files"][scenario_id],
        f"{record_label} has a scenario_file mismatch",
    )
    require(
        record["scenario_sha256"] == manifest["scenario_sha256"][scenario_id],
        f"{record_label} has a scenario_sha256 mismatch",
    )
    require(
        record["prompt_sha256"] == manifest["prompt_sha256"][scenario_id],
        f"{record_label} has a prompt_sha256 mismatch",
    )
    require(
        str(record["model_adapter_path"]).replace("\\", "/").rstrip("/") == CANDIDATE_CHECKPOINT.rstrip("/"),
        f"{record_label} uses the wrong candidate model adapter path",
    )
    require(
        record["wrapper_artifact"] == EXPECTED_ARTIFACT,
        f"{record_label} has wrong wrapper_artifact",
    )
    require(
        record["release_tag"] == EXPECTED_RELEASE_TAG,
        f"{record_label} has wrong release_tag",
    )
    require(
        record["desktop_commit"] == EXPECTED_DESKTOP_COMMIT,
        f"{record_label} has wrong desktop_commit",
    )
    require(
        record["backend_tag"] == EXPECTED_BACKEND_TAG,
        f"{record_label} has wrong backend_tag",
    )
    require(
        record["backend_commit"] == backend_identity_policy["actual_execution_backend_commit"],
        f"{record_label} has wrong backend_commit",
    )

    if expected_execution_window is not None:
        start, end = expected_execution_window
        executed_at = parse_iso8601(record["executed_at"])
        if start is not None:
            require(
                executed_at >= start,
                f"{record_label} executed_at falls before execution manifest start",
            )
        if end is not None:
            require(
                executed_at <= end,
                f"{record_label} executed_at falls after execution manifest end",
            )


def classify_candidate_record(record: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    wrapper_failures, model_failures = classify_trusted_record(record)[1:]
    final_outcome = record["final_outcome"]

    if final_outcome == "pass":
        require(
            not wrapper_failures and not model_failures,
            f"trusted record {record['scenario_id']} cannot be `pass` when failure buckets are non-empty",
        )
        return STATUS_PASSED, wrapper_failures, model_failures

    if final_outcome == "fail":
        require(
            bool(wrapper_failures or model_failures),
            f"trusted record {record['scenario_id']} cannot be `fail` with no failure buckets",
        )
        if wrapper_failures:
            return STATUS_WRAPPER_REPAIR, wrapper_failures, model_failures
        return STATUS_MODEL_REPAIR, wrapper_failures, model_failures

    if final_outcome in {"blocked", "incomplete"}:
        if wrapper_failures:
            return STATUS_WRAPPER_REPAIR, wrapper_failures, model_failures
        return STATUS_INCOMPLETE, wrapper_failures, model_failures

    raise ValueError(
        f"trusted record {record['scenario_id']} has unsupported final_outcome `{final_outcome}`"
    )


def write_ingestion_review(
    *,
    output_path: Path,
    status: str,
    notes: list[str],
    outputs_present: bool,
    results_present: bool,
    manifest_present: bool,
) -> None:
    lines = [
        "# V1.5.4 Candidate Runtime Results Ingestion Review",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- Candidate checkpoint under test is `{CANDIDATE_CHECKPOINT}`.",
        f"- Evidence-only adapters remain `{EVIDENCE_ONLY_SFT_ADAPTERS[0]}` and `{EVIDENCE_ONLY_SFT_ADAPTERS[1]}`.",
        f"- Parked DPO adapters remain `{PARKED_DPO_ADAPTERS[0]}` and `{PARKED_DPO_ADAPTERS[1]}`.",
        "- This milestone ingests the candidate runtime package only and does not invoke wrapper code from the LV7 repo.",
        "",
        "## Source Files",
        "",
        f"- runtime outputs present: `{outputs_present}`",
        f"- runtime results report present: `{results_present}`",
        f"- execution manifest present: `{manifest_present}`",
        "",
        "## Review Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in notes)
    lines.extend(["", f"- current status: `{status}`"])
    write_report(output_path, lines)


def write_scenario_matrix(*, output_path: Path, rows: list[list[str]]) -> None:
    lines = [
        "# V1.5.4 Candidate Scenario Result Matrix",
        "",
        render_markdown_table(
            ["scenario_id", "trusted", "final_outcome", "wrapper failures", "model failures", "notes"],
            rows,
        ),
    ]
    write_report(output_path, lines)


def write_decision_report(*, output_path: Path, status: str, notes: list[str]) -> None:
    lines = [
        "# V1.5.4 Next Step Decision",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- Candidate checkpoint under test remains `{CANDIDATE_CHECKPOINT}`.",
        "- This milestone classifies the candidate runtime package only and does not promote the candidate automatically.",
        "",
        "## Decision Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in notes)
    lines.extend(["", status])
    write_report(output_path, lines)


def write_json_report(
    *,
    output_path: Path,
    status: str,
    notes: list[str],
    rows: list[list[str]],
    trusted_record_count: int,
    wrapper_failures: dict[str, list[str]],
    model_failures: dict[str, list[str]],
) -> None:
    payload = {
        "milestone": "LV7 v1.5.4",
        "status": status,
        "accepted_checkpoint": ACCEPTED_CHECKPOINT,
        "candidate_checkpoint": CANDIDATE_CHECKPOINT,
        "candidate_alias_model_id": CANDIDATE_ALIAS_MODEL_ID,
        "trusted_record_count": trusted_record_count,
        "notes": notes,
        "scenario_rows": rows,
        "wrapper_failures": wrapper_failures,
        "model_failures": model_failures,
        "source_artifact_paths": {
            "runtime_outputs": display_path(DEFAULT_RUNTIME_OUTPUTS),
            "runtime_results_report": display_path(DEFAULT_RUNTIME_RESULTS_REPORT),
            "runtime_execution_manifest": display_path(DEFAULT_RUNTIME_EXECUTION_MANIFEST),
            "candidate_bridge_decision": display_path(DEFAULT_V1_5_3_DECISION_REPORT),
        },
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def analyze_v1_5_4_candidate_runtime_scenario_results(
    *,
    v1_4_1_decision_report_path: Path = DEFAULT_V1_4_1_DECISION_REPORT,
    v1_4_2_decision_report_path: Path = DEFAULT_V1_4_2_DECISION_REPORT,
    v1_5_3_decision_report_path: Path = DEFAULT_V1_5_3_DECISION_REPORT,
    v1_4_3a_decision_report_path: Path = DEFAULT_V1_4_3A_DECISION_REPORT,
    v1_4_3a_policy_json_path: Path = DEFAULT_V1_4_3A_POLICY_JSON,
    schema_json_path: Path = DEFAULT_SCHEMA_JSON,
    suite_manifest_json_path: Path = DEFAULT_SUITE_MANIFEST_JSON,
    runtime_outputs_path: Path = DEFAULT_RUNTIME_OUTPUTS,
    runtime_results_report_path: Path = DEFAULT_RUNTIME_RESULTS_REPORT,
    runtime_execution_manifest_path: Path = DEFAULT_RUNTIME_EXECUTION_MANIFEST,
    ingestion_review_report_path: Path = DEFAULT_INGESTION_REVIEW_REPORT,
    scenario_result_matrix_report_path: Path = DEFAULT_RESULT_MATRIX_REPORT,
    wrapper_failure_review_report_path: Path = DEFAULT_WRAPPER_FAILURE_REVIEW_REPORT,
    model_failure_review_report_path: Path = DEFAULT_MODEL_FAILURE_REVIEW_REPORT,
    decision_report_path: Path = DEFAULT_DECISION_REPORT,
    json_report_path: Path = DEFAULT_JSON_REPORT,
) -> dict[str, Any]:
    try:
        prerequisites = load_prerequisites(
            v1_4_1_decision_report_path=v1_4_1_decision_report_path,
            v1_4_2_decision_report_path=v1_4_2_decision_report_path,
            schema_json_path=schema_json_path,
            suite_manifest_json_path=suite_manifest_json_path,
            schema_report_path=REPORTS_RUNTIME_DIR / "V1_4_2_RUNTIME_OUTPUT_SCHEMA.md",
            taxonomy_report_path=REPORTS_RUNTIME_DIR / "V1_4_2_MODEL_VS_WRAPPER_FAILURE_TAXONOMY.md",
            acceptance_report_path=REPORTS_RUNTIME_DIR / "V1_4_2_SCENARIO_ACCEPTANCE_CRITERIA.md",
        )
        require(
            last_nonempty_line(v1_5_3_decision_report_path) == STATUS_V1_5_3_READY,
            f"{display_path(v1_5_3_decision_report_path)} does not end with {STATUS_V1_5_3_READY}",
        )
        require(
            last_nonempty_line(v1_4_3a_decision_report_path) == BACKEND_IDENTITY_POLICY_READY,
            f"{display_path(v1_4_3a_decision_report_path)} does not end with {BACKEND_IDENTITY_POLICY_READY}",
        )
        require(
            (PROJECT_ROOT / CANDIDATE_CHECKPOINT).exists(),
            f"candidate checkpoint is missing: {CANDIDATE_CHECKPOINT}",
        )
    except (FileNotFoundError, ValueError) as exc:
        notes = [str(exc)]
        rows = [
            [scenario_id, "no", "(invalid)", "-", "-", str(exc)]
            for scenario_id in EXPECTED_SCENARIO_IDS
        ]
        write_ingestion_review(
            output_path=ingestion_review_report_path,
            status=STATUS_INVALID,
            notes=notes,
            outputs_present=runtime_outputs_path.exists(),
            results_present=runtime_results_report_path.exists(),
            manifest_present=runtime_execution_manifest_path.exists(),
        )
        write_scenario_matrix(output_path=scenario_result_matrix_report_path, rows=rows)
        write_failure_review(
            output_path=wrapper_failure_review_report_path,
            title="V1.5.4 Wrapper Failure Review",
            grouped_failures={},
            empty_message="No trusted wrapper/runtime failures were found for the candidate package.",
        )
        write_failure_review(
            output_path=model_failure_review_report_path,
            title="V1.5.4 Model Failure Review",
            grouped_failures={},
            empty_message="No trusted model/runtime-contract failures were found for the candidate package.",
        )
        write_decision_report(output_path=decision_report_path, status=STATUS_INVALID, notes=notes)
        write_json_report(
            output_path=json_report_path,
            status=STATUS_INVALID,
            notes=notes,
            rows=rows,
            trusted_record_count=0,
            wrapper_failures={},
            model_failures={},
        )
        return {
            "status": STATUS_INVALID,
            "trusted_record_count": 0,
            "candidate_checkpoint": CANDIDATE_CHECKPOINT,
        }

    manifest = prerequisites["suite_manifest"]

    def finalize(
        *,
        status: str,
        notes: list[str],
        rows: list[list[str]],
        trusted_record_count: int,
        wrapper_failures: dict[str, list[str]] | None = None,
        model_failures: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        wrapper_failures = wrapper_failures or {}
        model_failures = model_failures or {}
        write_ingestion_review(
            output_path=ingestion_review_report_path,
            status=status,
            notes=notes,
            outputs_present=runtime_outputs_path.exists(),
            results_present=runtime_results_report_path.exists(),
            manifest_present=runtime_execution_manifest_path.exists(),
        )
        write_scenario_matrix(output_path=scenario_result_matrix_report_path, rows=rows)
        write_failure_review(
            output_path=wrapper_failure_review_report_path,
            title="V1.5.4 Wrapper Failure Review",
            grouped_failures=wrapper_failures,
            empty_message="No trusted wrapper/runtime failures were found for the candidate package.",
        )
        write_failure_review(
            output_path=model_failure_review_report_path,
            title="V1.5.4 Model Failure Review",
            grouped_failures=model_failures,
            empty_message="No trusted model/runtime-contract failures were found for the candidate package.",
        )
        write_decision_report(output_path=decision_report_path, status=status, notes=notes)
        write_json_report(
            output_path=json_report_path,
            status=status,
            notes=notes,
            rows=rows,
            trusted_record_count=trusted_record_count,
            wrapper_failures=wrapper_failures,
            model_failures=model_failures,
        )
        return {
            "status": status,
            "trusted_record_count": trusted_record_count,
            "candidate_checkpoint": CANDIDATE_CHECKPOINT,
        }

    try:
        backend_identity_policy = load_backend_identity_policy(v1_4_3a_policy_json_path)
    except (FileNotFoundError, ValueError) as exc:
        return finalize(
            status=STATUS_INVALID,
            notes=[str(exc)],
            rows=[
                [scenario_id, "no", "(invalid)", "-", "-", str(exc)]
                for scenario_id in EXPECTED_SCENARIO_IDS
            ],
            trusted_record_count=0,
        )

    if not runtime_outputs_path.exists() or not runtime_results_report_path.exists():
        notes: list[str] = []
        if not runtime_outputs_path.exists():
            notes.append(f"missing candidate runtime outputs JSONL: {display_path(runtime_outputs_path)}")
        if not runtime_results_report_path.exists():
            notes.append(
                f"missing candidate runtime results report: {display_path(runtime_results_report_path)}"
            )
        return finalize(
            status=STATUS_INCOMPLETE,
            notes=notes,
            rows=[
                [scenario_id, "no", "(missing)", "-", "-", "waiting for complete candidate runtime package"]
                for scenario_id in EXPECTED_SCENARIO_IDS
            ],
            trusted_record_count=0,
        )

    results_text = runtime_results_report_path.read_text(encoding="utf-8").strip()
    if not results_text:
        return finalize(
            status=STATUS_INVALID,
            notes=[f"candidate runtime results report is empty: {display_path(runtime_results_report_path)}"],
            rows=[
                [scenario_id, "no", "(invalid)", "-", "-", "candidate runtime results report is empty"]
                for scenario_id in EXPECTED_SCENARIO_IDS
            ],
            trusted_record_count=0,
        )

    try:
        execution_manifest = load_execution_manifest(
            runtime_execution_manifest_path,
            manifest=manifest,
            backend_identity_policy=backend_identity_policy,
        )
        execution_window = execution_manifest["_parsed_execution_window"]
        records = read_jsonl(runtime_outputs_path)
    except (json.JSONDecodeError, ValueError, FileNotFoundError) as exc:
        return finalize(
            status=STATUS_INVALID,
            notes=[str(exc)],
            rows=[
                [scenario_id, "no", "(invalid)", "-", "-", str(exc)]
                for scenario_id in EXPECTED_SCENARIO_IDS
            ],
            trusted_record_count=0,
        )

    if not records:
        return finalize(
            status=STATUS_INVALID,
            notes=[f"candidate runtime outputs JSONL is empty: {display_path(runtime_outputs_path)}"],
            rows=[
                [scenario_id, "no", "(invalid)", "-", "-", "candidate runtime outputs JSONL is empty"]
                for scenario_id in EXPECTED_SCENARIO_IDS
            ],
            trusted_record_count=0,
        )

    scenario_ids = [record.get("scenario_id") for record in records]
    present_ids = {item for item in scenario_ids if isinstance(item, str)}
    if len(records) < len(EXPECTED_SCENARIO_IDS):
        missing_ids = [item for item in EXPECTED_SCENARIO_IDS if item not in present_ids]
        notes = [f"candidate runtime outputs cover only `{len(records)}` records; expected `{len(EXPECTED_SCENARIO_IDS)}`"]
        if missing_ids:
            notes.append(f"missing scenario ids: {', '.join(missing_ids)}")
        return finalize(
            status=STATUS_INCOMPLETE,
            notes=notes,
            rows=[
                [
                    scenario_id,
                    "yes" if scenario_id in present_ids else "no",
                    "(pending)" if scenario_id in present_ids else "(missing)",
                    "-",
                    "-",
                    "record present but full trust deferred"
                    if scenario_id in present_ids
                    else "waiting for complete candidate scenario coverage",
                ]
                for scenario_id in EXPECTED_SCENARIO_IDS
            ],
            trusted_record_count=0,
        )

    seen_ids: set[str] = set()
    trusted_records: list[dict[str, Any]] = []
    try:
        for index, record in enumerate(records, start=1):
            record_label = f"candidate runtime output record #{index}"
            missing_fields = sorted(field for field in EXPECTED_REQUIRED_FIELDS if field not in record)
            if missing_fields:
                raise ValueError(f"{record_label} is missing required fields: {', '.join(missing_fields)}")
            validate_record_types(record, record_label=record_label)
            scenario_id = record["scenario_id"]
            if scenario_id in seen_ids:
                raise ValueError(f"duplicate scenario_id in candidate runtime outputs: {scenario_id}")
            seen_ids.add(scenario_id)
            validate_record_identity(
                record,
                manifest=manifest,
                backend_identity_policy=backend_identity_policy,
                expected_execution_window=execution_window,
                record_label=record_label,
            )
            trusted_records.append(record)
    except ValueError as exc:
        return finalize(
            status=STATUS_INVALID,
            notes=[str(exc)],
            rows=[
                [
                    scenario_id,
                    "yes" if scenario_id in seen_ids else "no",
                    "(invalid)" if scenario_id in seen_ids else "(missing)",
                    "-",
                    "-",
                    str(exc) if scenario_id in seen_ids else "record unavailable after validation failure",
                ]
                for scenario_id in EXPECTED_SCENARIO_IDS
            ],
            trusted_record_count=0,
        )

    if set(seen_ids) != set(EXPECTED_SCENARIO_IDS):
        unknown_ids = sorted(set(seen_ids) - set(EXPECTED_SCENARIO_IDS))
        notes = ["candidate runtime outputs do not match the pinned v1.4 scenario set"]
        if unknown_ids:
            notes.append(f"unknown scenario ids: {', '.join(unknown_ids)}")
        return finalize(
            status=STATUS_INVALID,
            notes=notes,
            rows=[
                [
                    scenario_id,
                    "yes" if scenario_id in seen_ids else "no",
                    "(invalid)" if scenario_id in seen_ids else "(missing)",
                    "-",
                    "-",
                    "scenario set mismatch",
                ]
                for scenario_id in EXPECTED_SCENARIO_IDS
            ],
            trusted_record_count=0,
        )

    rows: list[list[str]] = []
    wrapper_failures: dict[str, list[str]] = {}
    model_failures: dict[str, list[str]] = {}
    record_statuses: list[str] = []

    for record in trusted_records:
        classification, record_wrapper_failures, record_model_failures = classify_candidate_record(record)
        scenario_id = record["scenario_id"]
        wrapper_summary = ", ".join(record_wrapper_failures) if record_wrapper_failures else "-"
        model_summary = ", ".join(record_model_failures) if record_model_failures else "-"
        note = "trusted candidate record"
        if classification == STATUS_INCOMPLETE:
            note = "execution ended blocked/incomplete without enough evidence to prove a wrapper failure"
        elif classification == STATUS_WRAPPER_REPAIR:
            note = "wrapper failure wins because model diagnosis is not fair until wrapper issues are removed"
        elif classification == STATUS_MODEL_REPAIR:
            note = "candidate model failure with no trusted wrapper/runtime failures"

        rows.append(
            [scenario_id, "yes", record["final_outcome"], wrapper_summary, model_summary, note]
        )
        if record_wrapper_failures:
            wrapper_failures[scenario_id] = record_wrapper_failures
        if record_model_failures:
            model_failures[scenario_id] = record_model_failures
        record_statuses.append(classification)

    if STATUS_INCOMPLETE in record_statuses:
        status = STATUS_INCOMPLETE
        notes = [
            "one or more trusted candidate scenario records are blocked or incomplete without enough evidence to prove a wrapper failure"
        ]
    elif STATUS_WRAPPER_REPAIR in record_statuses:
        status = STATUS_WRAPPER_REPAIR
        notes = ["trusted candidate runtime results show wrapper/runtime contract failures"]
    elif STATUS_MODEL_REPAIR in record_statuses:
        status = STATUS_MODEL_REPAIR
        notes = ["trusted candidate runtime results show no wrapper failures but the candidate model still fails one or more runtime scenarios"]
    else:
        status = STATUS_PASSED
        notes = [
            "all 10 trusted candidate scenario records pass with no wrapper failures, no model failures, and no evidence/schema issues"
        ]

    return finalize(
        status=status,
        notes=notes,
        rows=rows,
        trusted_record_count=len(trusted_records),
        wrapper_failures=wrapper_failures,
        model_failures=model_failures,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest candidate runtime outputs and classify v1.5.4 candidate runtime results."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_5_4_candidate_runtime_scenario_results()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
