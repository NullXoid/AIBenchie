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
    PROJECT_ROOT,
    STATUS_READY as STATUS_RUNTIME_READY,
    last_nonempty_line,
    write_report,
)
from training.analyze_v1_4_2_runtime_scenario_eval_plan import (  # noqa: E402
    DEFAULT_DECISION_REPORT as DEFAULT_V1_4_2_DECISION_REPORT,
    DEFAULT_SCHEMA_JSON,
    DEFAULT_SUITE_MANIFEST_JSON,
    EXPECTED_RUNTIME_SUITE_ID,
    EXPECTED_SCENARIOS,
    STATUS_PLAN_READY,
    model_adapter_path_is_accepted,
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"

DEFAULT_V1_4_1_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_4_1_NEXT_STEP_DECISION.md"
DEFAULT_V1_4_2_SCHEMA_REPORT = REPORTS_RUNTIME_DIR / "V1_4_2_RUNTIME_OUTPUT_SCHEMA.md"
DEFAULT_V1_4_2_TAXONOMY_REPORT = REPORTS_RUNTIME_DIR / "V1_4_2_MODEL_VS_WRAPPER_FAILURE_TAXONOMY.md"
DEFAULT_V1_4_2_ACCEPTANCE_REPORT = REPORTS_RUNTIME_DIR / "V1_4_2_SCENARIO_ACCEPTANCE_CRITERIA.md"

DEFAULT_RUNTIME_OUTPUTS = REPORTS_RUNTIME_DIR / "v1_4_runtime_outputs.jsonl"
DEFAULT_RUNTIME_RESULTS_REPORT = REPORTS_RUNTIME_DIR / "V1_4_RUNTIME_EVAL_RESULTS.md"
DEFAULT_RUNTIME_EXECUTION_MANIFEST = REPORTS_RUNTIME_DIR / "v1_4_runtime_execution_manifest.json"
DEFAULT_BACKEND_IDENTITY_POLICY_JSON = REPORTS_RUNTIME_DIR / "v1_4_3a_backend_identity_policy.json"

DEFAULT_INGESTION_REVIEW_REPORT = REPORTS_RUNTIME_DIR / "V1_4_3_RUNTIME_RESULTS_INGESTION_REVIEW.md"
DEFAULT_RESULT_MATRIX_REPORT = REPORTS_RUNTIME_DIR / "V1_4_3_SCENARIO_RESULT_MATRIX.md"
DEFAULT_WRAPPER_FAILURE_REVIEW_REPORT = REPORTS_RUNTIME_DIR / "V1_4_3_WRAPPER_FAILURE_REVIEW.md"
DEFAULT_MODEL_FAILURE_REVIEW_REPORT = REPORTS_RUNTIME_DIR / "V1_4_3_MODEL_FAILURE_REVIEW.md"
DEFAULT_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_4_3_NEXT_STEP_DECISION.md"

STATUS_PASSED = "RUNTIME_EVAL_PASSED"
STATUS_WRAPPER_REPAIR = "RUNTIME_WRAPPER_REPAIR_NEEDED"
STATUS_MODEL_REPAIR = "MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED"
STATUS_INCOMPLETE = "RUNTIME_RESULTS_INCOMPLETE"
STATUS_INVALID = "RUNTIME_RESULTS_INVALID"

APPROVED_STATUSES = {
    STATUS_PASSED,
    STATUS_WRAPPER_REPAIR,
    STATUS_MODEL_REPAIR,
    STATUS_INCOMPLETE,
    STATUS_INVALID,
}

EXPECTED_SCENARIO_IDS = [scenario_id for scenario_id, _, _ in EXPECTED_SCENARIOS]
EXPECTED_REQUIRED_FIELDS = {
    "suite_id",
    "scenario_id",
    "scenario_file",
    "scenario_sha256",
    "prompt_sha256",
    "model_adapter_path",
    "wrapper_artifact",
    "release_tag",
    "desktop_commit",
    "backend_tag",
    "backend_commit",
    "raw_model_text",
    "final_emitted_text",
    "policy_rationale_visible",
    "fenced_nullxoid_signal_present",
    "nullxoid_signal_stripped",
    "policy_rationale_parsed_as_metadata",
    "pass1_state",
    "gate_decision",
    "pass2_state",
    "timeout_observed",
    "cancel_observed",
    "fallback_used",
    "final_outcome",
    "wrapper_contract_failures",
    "model_contract_failures",
    "executed_at",
}
EXPECTED_FINAL_OUTCOMES = {"pass", "fail", "blocked", "incomplete"}
EXPECTED_TYPE_RULES: dict[str, type | tuple[type, ...]] = {
    "raw_model_text": str,
    "final_emitted_text": str,
    "policy_rationale_visible": bool,
    "fenced_nullxoid_signal_present": bool,
    "nullxoid_signal_stripped": bool,
    "policy_rationale_parsed_as_metadata": bool,
    "timeout_observed": bool,
    "cancel_observed": bool,
    "fallback_used": bool,
}

BACKEND_IDENTITY_POLICY_READY = "RUNTIME_BACKEND_IDENTITY_POLICY_READY"
ACTUAL_BACKEND_POLICY_NAME = "actual_execution_strictness"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def render_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def parse_iso8601(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def normalize_adapter_path(path: str) -> str:
    return path.replace("\\", "/").rstrip("/")


def path_is_evidence_only_or_dpo(path: str) -> bool:
    normalized = normalize_adapter_path(path)
    invalid_paths = {
        normalize_adapter_path(item)
        for item in (*EVIDENCE_ONLY_SFT_ADAPTERS, *PARKED_DPO_ADAPTERS)
    }
    return normalized in invalid_paths


def load_backend_identity_policy(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

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
        payload.get("accepted_adapter_path") == ACCEPTED_CHECKPOINT,
        "backend identity policy has wrong accepted_adapter_path",
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

    manifest_requirements = payload.get("execution_manifest_requirements")
    require(
        isinstance(manifest_requirements, dict),
        "backend identity policy is missing execution_manifest_requirements",
    )
    require(
        manifest_requirements.get("backend_commit_policy") == ACTUAL_BACKEND_POLICY_NAME,
        "backend identity policy has wrong execution manifest backend_commit_policy",
    )
    require(
        manifest_requirements.get("backend_anchor_commit") == EXPECTED_BACKEND_COMMIT,
        "backend identity policy has wrong execution manifest backend_anchor_commit",
    )

    return payload


def load_prerequisites(
    *,
    v1_4_1_decision_report_path: Path,
    v1_4_2_decision_report_path: Path,
    schema_json_path: Path,
    suite_manifest_json_path: Path,
    schema_report_path: Path,
    taxonomy_report_path: Path,
    acceptance_report_path: Path,
) -> dict[str, Any]:
    required_paths = [
        v1_4_1_decision_report_path,
        v1_4_2_decision_report_path,
        schema_json_path,
        suite_manifest_json_path,
        schema_report_path,
        taxonomy_report_path,
        acceptance_report_path,
    ]
    missing = [display_path(path) for path in required_paths if not path.exists()]
    require(not missing, f"missing required planning artifacts: {', '.join(missing)}")

    require(
        last_nonempty_line(v1_4_1_decision_report_path) == STATUS_RUNTIME_READY,
        f"{display_path(v1_4_1_decision_report_path)} does not end with {STATUS_RUNTIME_READY}",
    )
    require(
        last_nonempty_line(v1_4_2_decision_report_path) == STATUS_PLAN_READY,
        f"{display_path(v1_4_2_decision_report_path)} does not end with {STATUS_PLAN_READY}",
    )

    require((PROJECT_ROOT / ACCEPTED_CHECKPOINT).exists(), f"accepted checkpoint is missing: {ACCEPTED_CHECKPOINT}")
    for adapter_path in (*EVIDENCE_ONLY_SFT_ADAPTERS, *PARKED_DPO_ADAPTERS):
        require((PROJECT_ROOT / adapter_path).exists(), f"expected adapter path is missing: {adapter_path}")

    schema_payload = read_json(schema_json_path)
    manifest_payload = read_json(suite_manifest_json_path)
    require(
        set(schema_payload.get("required_fields", [])) == EXPECTED_REQUIRED_FIELDS,
        "v1.4.2 runtime output schema required_fields do not match the expected contract",
    )
    require(
        manifest_payload.get("suite_id") == EXPECTED_RUNTIME_SUITE_ID,
        f"runtime suite manifest suite_id must be {EXPECTED_RUNTIME_SUITE_ID}",
    )
    require(
        manifest_payload.get("scenario_count") == len(EXPECTED_SCENARIO_IDS),
        f"runtime suite manifest scenario_count must be {len(EXPECTED_SCENARIO_IDS)}",
    )
    require(
        manifest_payload.get("scenario_ids") == EXPECTED_SCENARIO_IDS,
        "runtime suite manifest scenario_ids do not match the expected v1.4 package",
    )

    return {
        "schema": schema_payload,
        "suite_manifest": manifest_payload,
        "accepted_checkpoint": ACCEPTED_CHECKPOINT,
        "evidence_only_adapters": list(EVIDENCE_ONLY_SFT_ADAPTERS),
        "parked_dpo_adapters": list(PARKED_DPO_ADAPTERS),
    }


def validate_string_array(value: Any, field_name: str, *, record_label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{record_label} field `{field_name}` must be an array of strings")
    if any(not isinstance(item, str) for item in value):
        raise ValueError(f"{record_label} field `{field_name}` must contain only strings")
    return value


def validate_record_types(record: dict[str, Any], *, record_label: str) -> None:
    missing_fields = sorted(field for field in EXPECTED_REQUIRED_FIELDS if field not in record)
    if missing_fields:
        raise ValueError(f"{record_label} is missing required fields: {', '.join(missing_fields)}")

    for field_name, expected_type in EXPECTED_TYPE_RULES.items():
        if not isinstance(record[field_name], expected_type):
            raise ValueError(f"{record_label} field `{field_name}` has the wrong type")

    validate_string_array(record["wrapper_contract_failures"], "wrapper_contract_failures", record_label=record_label)
    validate_string_array(record["model_contract_failures"], "model_contract_failures", record_label=record_label)

    if not isinstance(record["suite_id"], str) or not record["suite_id"]:
        raise ValueError(f"{record_label} field `suite_id` must be a non-empty string")
    if not isinstance(record["scenario_id"], str) or not record["scenario_id"]:
        raise ValueError(f"{record_label} field `scenario_id` must be a non-empty string")
    if not isinstance(record["scenario_file"], str) or not record["scenario_file"]:
        raise ValueError(f"{record_label} field `scenario_file` must be a non-empty string")
    if not isinstance(record["scenario_sha256"], str) or not record["scenario_sha256"]:
        raise ValueError(f"{record_label} field `scenario_sha256` must be a non-empty string")
    if not isinstance(record["prompt_sha256"], str) or not record["prompt_sha256"]:
        raise ValueError(f"{record_label} field `prompt_sha256` must be a non-empty string")
    if not isinstance(record["model_adapter_path"], str) or not record["model_adapter_path"]:
        raise ValueError(f"{record_label} field `model_adapter_path` must be a non-empty string")
    if not isinstance(record["wrapper_artifact"], str) or not record["wrapper_artifact"]:
        raise ValueError(f"{record_label} field `wrapper_artifact` must be a non-empty string")
    if not isinstance(record["release_tag"], str) or not record["release_tag"]:
        raise ValueError(f"{record_label} field `release_tag` must be a non-empty string")
    if not isinstance(record["desktop_commit"], str) or not record["desktop_commit"]:
        raise ValueError(f"{record_label} field `desktop_commit` must be a non-empty string")
    if not isinstance(record["backend_tag"], str) or not record["backend_tag"]:
        raise ValueError(f"{record_label} field `backend_tag` must be a non-empty string")
    if not isinstance(record["backend_commit"], str) or not record["backend_commit"]:
        raise ValueError(f"{record_label} field `backend_commit` must be a non-empty string")

    if record["final_outcome"] not in EXPECTED_FINAL_OUTCOMES:
        raise ValueError(f"{record_label} field `final_outcome` must be one of: {', '.join(sorted(EXPECTED_FINAL_OUTCOMES))}")

    try:
        parse_iso8601(record["executed_at"])
    except ValueError as exc:
        raise ValueError(f"{record_label} field `executed_at` must be parseable ISO-8601") from exc


def infer_runtime_failures(record: dict[str, Any]) -> tuple[list[str], list[str]]:
    wrapper_failures = list(record["wrapper_contract_failures"])
    model_failures = list(record["model_contract_failures"])

    raw_text = record["raw_model_text"]
    final_text = record["final_emitted_text"]

    if record["policy_rationale_parsed_as_metadata"] and "policy_rationale parsed as controller metadata" not in wrapper_failures:
        wrapper_failures.append("policy_rationale parsed as controller metadata")

    if record["fenced_nullxoid_signal_present"] and not record["nullxoid_signal_stripped"]:
        if "fenced nullxoid_signal not stripped" not in wrapper_failures:
            wrapper_failures.append("fenced nullxoid_signal not stripped")

    if not record["policy_rationale_visible"]:
        raw_has_rationale = "policy_rationale" in raw_text.lower()
        final_has_rationale = "policy_rationale" in final_text.lower()
        if raw_has_rationale and not final_has_rationale:
            if "policy_rationale parsed as controller metadata" not in wrapper_failures:
                wrapper_failures.append("policy_rationale parsed as controller metadata")
        elif not raw_has_rationale:
            failure = "policy_rationale format/content fails in a way the wrapper cannot reasonably fix"
            if failure not in model_failures:
                model_failures.append(failure)

    return wrapper_failures, model_failures


def validate_record_identity(
    record: dict[str, Any],
    *,
    manifest: dict[str, Any],
    backend_identity_policy: dict[str, Any] | None,
    expected_execution_window: tuple[datetime | None, datetime | None] | None,
    record_label: str,
) -> None:
    scenario_id = record["scenario_id"]
    if record["suite_id"] != EXPECTED_RUNTIME_SUITE_ID:
        raise ValueError(f"{record_label} has wrong suite_id")
    if scenario_id not in manifest["scenario_ids"]:
        raise ValueError(f"{record_label} has unknown scenario_id `{scenario_id}`")
    if record["scenario_sha256"] != manifest["scenario_sha256"][scenario_id]:
        raise ValueError(f"{record_label} has a scenario_sha256 mismatch")
    if record["prompt_sha256"] != manifest["prompt_sha256"][scenario_id]:
        raise ValueError(f"{record_label} has a prompt_sha256 mismatch")
    if record["scenario_file"].replace("\\", "/") != manifest["scenario_files"][scenario_id]:
        raise ValueError(f"{record_label} has a scenario_file mismatch")

    model_adapter_path = record["model_adapter_path"]
    if not model_adapter_path_is_accepted(model_adapter_path):
        raise ValueError(f"{record_label} uses a non-accepted model adapter path")
    if path_is_evidence_only_or_dpo(model_adapter_path):
        raise ValueError(f"{record_label} uses an evidence-only or DPO adapter path")

    if record["wrapper_artifact"] != EXPECTED_ARTIFACT:
        raise ValueError(f"{record_label} has wrong wrapper_artifact")
    if record["release_tag"] != EXPECTED_RELEASE_TAG:
        raise ValueError(f"{record_label} has wrong release_tag")
    if record["desktop_commit"] != EXPECTED_DESKTOP_COMMIT:
        raise ValueError(f"{record_label} has wrong desktop_commit")
    if record["backend_tag"] != EXPECTED_BACKEND_TAG:
        raise ValueError(f"{record_label} has wrong backend_tag")
    expected_backend_commit = (
        backend_identity_policy["actual_execution_backend_commit"]
        if backend_identity_policy is not None
        else EXPECTED_BACKEND_COMMIT
    )
    if record["backend_commit"] != expected_backend_commit:
        raise ValueError(f"{record_label} has wrong backend_commit")

    if expected_execution_window is not None:
        start, end = expected_execution_window
        executed_at = parse_iso8601(record["executed_at"])
        if start is not None and executed_at < start:
            raise ValueError(f"{record_label} executed_at falls before execution manifest start")
        if end is not None and executed_at > end:
            raise ValueError(f"{record_label} executed_at falls after execution manifest end")


def load_execution_manifest(
    path: Path,
    *,
    manifest: dict[str, Any],
    backend_identity_policy: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not path.exists():
        if backend_identity_policy is not None:
            raise ValueError(
                "runtime execution manifest is required under actual backend identity policy"
            )
        return None
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError("runtime execution manifest must be a JSON object")

    if "suite_id" in payload and payload["suite_id"] != EXPECTED_RUNTIME_SUITE_ID:
        raise ValueError("runtime execution manifest has wrong suite_id")
    if "scenario_count" in payload and payload["scenario_count"] != len(EXPECTED_SCENARIO_IDS):
        raise ValueError("runtime execution manifest has wrong scenario_count")
    if "model_adapter_path" in payload and not model_adapter_path_is_accepted(str(payload["model_adapter_path"])):
        raise ValueError("runtime execution manifest has wrong model_adapter_path")
    if "wrapper_artifact" in payload and payload["wrapper_artifact"] != EXPECTED_ARTIFACT:
        raise ValueError("runtime execution manifest has wrong wrapper_artifact")
    if "release_tag" in payload and payload["release_tag"] != EXPECTED_RELEASE_TAG:
        raise ValueError("runtime execution manifest has wrong release_tag")
    if "desktop_commit" in payload and payload["desktop_commit"] != EXPECTED_DESKTOP_COMMIT:
        raise ValueError("runtime execution manifest has wrong desktop_commit")
    if "backend_tag" in payload and payload["backend_tag"] != EXPECTED_BACKEND_TAG:
        raise ValueError("runtime execution manifest has wrong backend_tag")
    expected_backend_commit = (
        backend_identity_policy["actual_execution_backend_commit"]
        if backend_identity_policy is not None
        else EXPECTED_BACKEND_COMMIT
    )
    if "backend_commit" in payload and payload["backend_commit"] != expected_backend_commit:
        raise ValueError("runtime execution manifest has wrong backend_commit")
    if "scenario_sha256" in payload and payload["scenario_sha256"] != manifest["scenario_sha256"]:
        raise ValueError("runtime execution manifest contradicts suite scenario_sha256 values")
    if "prompt_sha256" in payload and payload["prompt_sha256"] != manifest["prompt_sha256"]:
        raise ValueError("runtime execution manifest contradicts suite prompt_sha256 values")
    if "scenario_ids" in payload and payload["scenario_ids"] != manifest["scenario_ids"]:
        raise ValueError("runtime execution manifest contradicts suite scenario_ids")

    if backend_identity_policy is not None:
        if payload.get("backend_commit_policy") != ACTUAL_BACKEND_POLICY_NAME:
            raise ValueError(
                "runtime execution manifest has wrong backend_commit_policy for actual backend trust"
            )
        if payload.get("backend_anchor_commit") != EXPECTED_BACKEND_COMMIT:
            raise ValueError(
                "runtime execution manifest has wrong backend_anchor_commit for actual backend trust"
            )
        if (
            "backend_anchor_tag" in payload
            and payload["backend_anchor_tag"] != EXPECTED_BACKEND_TAG
        ):
            raise ValueError(
                "runtime execution manifest has wrong backend_anchor_tag for actual backend trust"
            )

    start = None
    end = None
    if "execution_started_at" in payload:
        if not isinstance(payload["execution_started_at"], str):
            raise ValueError("runtime execution manifest execution_started_at must be a string")
        start = parse_iso8601(payload["execution_started_at"])
    if "execution_finished_at" in payload:
        if not isinstance(payload["execution_finished_at"], str):
            raise ValueError("runtime execution manifest execution_finished_at must be a string")
        end = parse_iso8601(payload["execution_finished_at"])
    if start is not None and end is not None and start > end:
        raise ValueError("runtime execution manifest execution window is inverted")

    payload["_parsed_execution_window"] = (start, end)
    return payload


def classify_trusted_record(record: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    wrapper_failures, model_failures = infer_runtime_failures(record)
    final_outcome = record["final_outcome"]

    if final_outcome == "pass":
        if wrapper_failures or model_failures:
            raise ValueError(f"trusted record {record['scenario_id']} cannot be `pass` when failure buckets are non-empty")
        return "pass", wrapper_failures, model_failures

    if final_outcome == "fail":
        if not wrapper_failures and not model_failures:
            raise ValueError(f"trusted record {record['scenario_id']} cannot be `fail` with no failure buckets")
        if wrapper_failures:
            return STATUS_WRAPPER_REPAIR, wrapper_failures, model_failures
        return STATUS_MODEL_REPAIR, wrapper_failures, model_failures

    if final_outcome in {"blocked", "incomplete"}:
        if wrapper_failures:
            return STATUS_WRAPPER_REPAIR, wrapper_failures, model_failures
        return STATUS_INCOMPLETE, wrapper_failures, model_failures

    raise ValueError(f"trusted record {record['scenario_id']} has unsupported final_outcome `{final_outcome}`")


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
        "# V1.4.3 Runtime Results Ingestion Review",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- Evidence-only adapters remain `{EVIDENCE_ONLY_SFT_ADAPTERS[0]}` and `{EVIDENCE_ONLY_SFT_ADAPTERS[1]}`.",
        f"- Parked DPO adapters remain `{PARKED_DPO_ADAPTERS[0]}` and `{PARKED_DPO_ADAPTERS[1]}`.",
        "- This milestone ingests external runtime outputs only and does not invoke wrapper code from the LV7 repo.",
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


def write_scenario_matrix(
    *,
    output_path: Path,
    rows: list[list[str]],
) -> None:
    lines = [
        "# V1.4.3 Scenario Result Matrix",
        "",
        render_markdown_table(
            ["scenario_id", "trusted", "final_outcome", "wrapper failures", "model failures", "notes"],
            rows,
        ),
    ]
    write_report(output_path, lines)


def write_failure_review(
    *,
    output_path: Path,
    title: str,
    grouped_failures: dict[str, list[str]],
    empty_message: str,
) -> None:
    lines = [f"# {title}", ""]
    if not grouped_failures:
        lines.append(f"- {empty_message}")
    else:
        for scenario_id in sorted(grouped_failures):
            lines.append(f"## {scenario_id}")
            lines.append("")
            for item in grouped_failures[scenario_id]:
                lines.append(f"- {item}")
            lines.append("")
        if lines[-1] == "":
            lines.pop()
    write_report(output_path, lines)


def write_decision_report(
    *,
    output_path: Path,
    status: str,
    notes: list[str],
) -> None:
    lines = [
        "# V1.4.3 Next Step Decision",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- Evidence-only adapters remain `{EVIDENCE_ONLY_SFT_ADAPTERS[0]}` and `{EVIDENCE_ONLY_SFT_ADAPTERS[1]}`.",
        f"- Parked DPO adapters remain `{PARKED_DPO_ADAPTERS[0]}` and `{PARKED_DPO_ADAPTERS[1]}`.",
        "- `v1.4.3` classifies ingested runtime results only and does not authorize immediate SFT or DPO repair.",
        "",
        "## Decision Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in notes)
    lines.extend(["", status])
    write_report(output_path, lines)


def analyze_v1_4_3_runtime_scenario_results(
    *,
    v1_4_1_decision_report_path: Path = DEFAULT_V1_4_1_DECISION_REPORT,
    v1_4_2_decision_report_path: Path = DEFAULT_V1_4_2_DECISION_REPORT,
    schema_json_path: Path = DEFAULT_SCHEMA_JSON,
    suite_manifest_json_path: Path = DEFAULT_SUITE_MANIFEST_JSON,
    schema_report_path: Path = DEFAULT_V1_4_2_SCHEMA_REPORT,
    taxonomy_report_path: Path = DEFAULT_V1_4_2_TAXONOMY_REPORT,
    acceptance_report_path: Path = DEFAULT_V1_4_2_ACCEPTANCE_REPORT,
    runtime_outputs_path: Path = DEFAULT_RUNTIME_OUTPUTS,
    runtime_results_report_path: Path = DEFAULT_RUNTIME_RESULTS_REPORT,
    runtime_execution_manifest_path: Path = DEFAULT_RUNTIME_EXECUTION_MANIFEST,
    backend_identity_policy_path: Path = DEFAULT_BACKEND_IDENTITY_POLICY_JSON,
    ingestion_review_report_path: Path = DEFAULT_INGESTION_REVIEW_REPORT,
    scenario_result_matrix_report_path: Path = DEFAULT_RESULT_MATRIX_REPORT,
    wrapper_failure_review_report_path: Path = DEFAULT_WRAPPER_FAILURE_REVIEW_REPORT,
    model_failure_review_report_path: Path = DEFAULT_MODEL_FAILURE_REVIEW_REPORT,
    decision_report_path: Path = DEFAULT_DECISION_REPORT,
) -> dict[str, Any]:
    prerequisites = load_prerequisites(
        v1_4_1_decision_report_path=v1_4_1_decision_report_path,
        v1_4_2_decision_report_path=v1_4_2_decision_report_path,
        schema_json_path=schema_json_path,
        suite_manifest_json_path=suite_manifest_json_path,
        schema_report_path=schema_report_path,
        taxonomy_report_path=taxonomy_report_path,
        acceptance_report_path=acceptance_report_path,
    )

    manifest = prerequisites["suite_manifest"]
    try:
        backend_identity_policy = load_backend_identity_policy(backend_identity_policy_path)
    except ValueError as exc:
        status = STATUS_INVALID
        notes = [str(exc)]
        rows = [[scenario_id, "no", "(invalid)", "-", "-", notes[0]] for scenario_id in EXPECTED_SCENARIO_IDS]
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
            title="V1.4.3 Wrapper Failure Review",
            grouped_failures={},
            empty_message="No trusted wrapper failures are available because runtime trust policy is invalid.",
        )
        write_failure_review(
            output_path=model_failure_review_report_path,
            title="V1.4.3 Model Failure Review",
            grouped_failures={},
            empty_message="No trusted model failures are available because runtime trust policy is invalid.",
        )
        write_decision_report(output_path=decision_report_path, status=status, notes=notes)
        return {
            "status": status,
            "trusted_record_count": 0,
            "accepted_checkpoint": prerequisites["accepted_checkpoint"],
        }

    notes: list[str] = []
    rows: list[list[str]] = []
    wrapper_failures: dict[str, list[str]] = {}
    model_failures: dict[str, list[str]] = {}

    outputs_present = runtime_outputs_path.exists()
    results_present = runtime_results_report_path.exists()
    execution_manifest_present = runtime_execution_manifest_path.exists()

    if backend_identity_policy is not None:
        notes.append(
            "actual backend identity policy is active via reports/runtime/v1_4_3a_backend_identity_policy.json"
        )

    if not outputs_present or not results_present:
        status = STATUS_INCOMPLETE
        if not outputs_present:
            notes.append(f"missing runtime outputs JSONL: {display_path(runtime_outputs_path)}")
        if not results_present:
            notes.append(f"missing runtime results report: {display_path(runtime_results_report_path)}")
        rows = [[scenario_id, "no", "(missing)", "-", "-", "waiting for external runtime outputs"] for scenario_id in EXPECTED_SCENARIO_IDS]
        write_ingestion_review(
            output_path=ingestion_review_report_path,
            status=status,
            notes=notes,
            outputs_present=outputs_present,
            results_present=results_present,
            manifest_present=execution_manifest_present,
        )
        write_scenario_matrix(output_path=scenario_result_matrix_report_path, rows=rows)
        write_failure_review(
            output_path=wrapper_failure_review_report_path,
            title="V1.4.3 Wrapper Failure Review",
            grouped_failures={},
            empty_message="No trusted wrapper failures are available because runtime outputs are incomplete.",
        )
        write_failure_review(
            output_path=model_failure_review_report_path,
            title="V1.4.3 Model Failure Review",
            grouped_failures={},
            empty_message="No trusted model failures are available because runtime outputs are incomplete.",
        )
        write_decision_report(output_path=decision_report_path, status=status, notes=notes)
        return {
            "status": status,
            "trusted_record_count": 0,
            "accepted_checkpoint": prerequisites["accepted_checkpoint"],
        }

    results_text = runtime_results_report_path.read_text(encoding="utf-8").strip()
    if not results_text:
        status = STATUS_INVALID
        notes = [f"runtime results report is empty: {display_path(runtime_results_report_path)}"]
        rows = [[scenario_id, "no", "(invalid)", "-", "-", "runtime results report is empty"] for scenario_id in EXPECTED_SCENARIO_IDS]
        write_ingestion_review(
            output_path=ingestion_review_report_path,
            status=status,
            notes=notes,
            outputs_present=outputs_present,
            results_present=results_present,
            manifest_present=execution_manifest_present,
        )
        write_scenario_matrix(output_path=scenario_result_matrix_report_path, rows=rows)
        write_failure_review(
            output_path=wrapper_failure_review_report_path,
            title="V1.4.3 Wrapper Failure Review",
            grouped_failures={},
            empty_message="No trusted wrapper failures are available because runtime results are invalid.",
        )
        write_failure_review(
            output_path=model_failure_review_report_path,
            title="V1.4.3 Model Failure Review",
            grouped_failures={},
            empty_message="No trusted model failures are available because runtime results are invalid.",
        )
        write_decision_report(output_path=decision_report_path, status=status, notes=notes)
        return {
            "status": status,
            "trusted_record_count": 0,
            "accepted_checkpoint": prerequisites["accepted_checkpoint"],
        }

    try:
        execution_manifest = load_execution_manifest(
            runtime_execution_manifest_path,
            manifest=manifest,
            backend_identity_policy=backend_identity_policy,
        )
        execution_window = None if execution_manifest is None else execution_manifest["_parsed_execution_window"]
        records = read_jsonl(runtime_outputs_path)
    except (json.JSONDecodeError, ValueError) as exc:
        status = STATUS_INVALID
        notes = [str(exc)]
        rows = [[scenario_id, "no", "(invalid)", "-", "-", notes[0]] for scenario_id in EXPECTED_SCENARIO_IDS]
        write_ingestion_review(
            output_path=ingestion_review_report_path,
            status=status,
            notes=notes,
            outputs_present=outputs_present,
            results_present=results_present,
            manifest_present=execution_manifest_present,
        )
        write_scenario_matrix(output_path=scenario_result_matrix_report_path, rows=rows)
        write_failure_review(
            output_path=wrapper_failure_review_report_path,
            title="V1.4.3 Wrapper Failure Review",
            grouped_failures={},
            empty_message="No trusted wrapper failures are available because runtime results are invalid.",
        )
        write_failure_review(
            output_path=model_failure_review_report_path,
            title="V1.4.3 Model Failure Review",
            grouped_failures={},
            empty_message="No trusted model failures are available because runtime results are invalid.",
        )
        write_decision_report(output_path=decision_report_path, status=status, notes=notes)
        return {
            "status": status,
            "trusted_record_count": 0,
            "accepted_checkpoint": prerequisites["accepted_checkpoint"],
        }

    if not records:
        status = STATUS_INVALID
        notes = [f"runtime outputs JSONL is empty: {display_path(runtime_outputs_path)}"]
        rows = [[scenario_id, "no", "(invalid)", "-", "-", "runtime outputs JSONL is empty"] for scenario_id in EXPECTED_SCENARIO_IDS]
        write_ingestion_review(
            output_path=ingestion_review_report_path,
            status=status,
            notes=notes,
            outputs_present=outputs_present,
            results_present=results_present,
            manifest_present=execution_manifest_present,
        )
        write_scenario_matrix(output_path=scenario_result_matrix_report_path, rows=rows)
        write_failure_review(
            output_path=wrapper_failure_review_report_path,
            title="V1.4.3 Wrapper Failure Review",
            grouped_failures={},
            empty_message="No trusted wrapper failures are available because runtime results are invalid.",
        )
        write_failure_review(
            output_path=model_failure_review_report_path,
            title="V1.4.3 Model Failure Review",
            grouped_failures={},
            empty_message="No trusted model failures are available because runtime results are invalid.",
        )
        write_decision_report(output_path=decision_report_path, status=status, notes=notes)
        return {
            "status": status,
            "trusted_record_count": 0,
            "accepted_checkpoint": prerequisites["accepted_checkpoint"],
        }

    scenario_ids = [record.get("scenario_id") for record in records]
    if len(records) < len(EXPECTED_SCENARIO_IDS):
        status = STATUS_INCOMPLETE
        present_ids = {item for item in scenario_ids if isinstance(item, str)}
        missing_ids = [item for item in EXPECTED_SCENARIO_IDS if item not in present_ids]
        notes = [f"runtime outputs cover only `{len(records)}` records; expected `{len(EXPECTED_SCENARIO_IDS)}`"]
        if missing_ids:
            notes.append(f"missing scenario ids: {', '.join(missing_ids)}")
        rows = [[scenario_id, "yes" if scenario_id in present_ids else "no", "(pending)" if scenario_id in present_ids else "(missing)", "-", "-", "waiting for complete scenario coverage" if scenario_id not in present_ids else "record present but full trust deferred"] for scenario_id in EXPECTED_SCENARIO_IDS]
        write_ingestion_review(
            output_path=ingestion_review_report_path,
            status=status,
            notes=notes,
            outputs_present=outputs_present,
            results_present=results_present,
            manifest_present=execution_manifest_present,
        )
        write_scenario_matrix(output_path=scenario_result_matrix_report_path, rows=rows)
        write_failure_review(
            output_path=wrapper_failure_review_report_path,
            title="V1.4.3 Wrapper Failure Review",
            grouped_failures={},
            empty_message="No trusted wrapper failures are available because scenario coverage is incomplete.",
        )
        write_failure_review(
            output_path=model_failure_review_report_path,
            title="V1.4.3 Model Failure Review",
            grouped_failures={},
            empty_message="No trusted model failures are available because scenario coverage is incomplete.",
        )
        write_decision_report(output_path=decision_report_path, status=status, notes=notes)
        return {
            "status": status,
            "trusted_record_count": 0,
            "accepted_checkpoint": prerequisites["accepted_checkpoint"],
        }

    seen_ids: set[str] = set()
    trusted_records: list[dict[str, Any]] = []
    try:
        for index, record in enumerate(records, start=1):
            record_label = f"runtime output record #{index}"
            validate_record_types(record, record_label=record_label)
            scenario_id = record["scenario_id"]
            if scenario_id in seen_ids:
                raise ValueError(f"duplicate scenario_id in runtime outputs: {scenario_id}")
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
        status = STATUS_INVALID
        notes = [str(exc)]
        rows = []
        for scenario_id in EXPECTED_SCENARIO_IDS:
            presence = "yes" if scenario_id in seen_ids else "no"
            rows.append([scenario_id, presence, "(invalid)", "-", "-", notes[0] if presence == "yes" else "record unavailable after validation failure"])
        write_ingestion_review(
            output_path=ingestion_review_report_path,
            status=status,
            notes=notes,
            outputs_present=outputs_present,
            results_present=results_present,
            manifest_present=execution_manifest_present,
        )
        write_scenario_matrix(output_path=scenario_result_matrix_report_path, rows=rows)
        write_failure_review(
            output_path=wrapper_failure_review_report_path,
            title="V1.4.3 Wrapper Failure Review",
            grouped_failures={},
            empty_message="No trusted wrapper failures are available because runtime results are invalid.",
        )
        write_failure_review(
            output_path=model_failure_review_report_path,
            title="V1.4.3 Model Failure Review",
            grouped_failures={},
            empty_message="No trusted model failures are available because runtime results are invalid.",
        )
        write_decision_report(output_path=decision_report_path, status=status, notes=notes)
        return {
            "status": status,
            "trusted_record_count": 0,
            "accepted_checkpoint": prerequisites["accepted_checkpoint"],
        }

    if len(seen_ids) > len(EXPECTED_SCENARIO_IDS):
        status = STATUS_INVALID
        notes = ["runtime outputs include unknown scenario ids"]
        rows = [[scenario_id, "yes" if scenario_id in seen_ids else "no", "(invalid)", "-", "-", "unknown scenario id set includes non-v1.4 scenarios" if scenario_id in seen_ids else "missing trusted record"] for scenario_id in EXPECTED_SCENARIO_IDS]
        write_ingestion_review(
            output_path=ingestion_review_report_path,
            status=status,
            notes=notes,
            outputs_present=outputs_present,
            results_present=results_present,
            manifest_present=execution_manifest_present,
        )
        write_scenario_matrix(output_path=scenario_result_matrix_report_path, rows=rows)
        write_failure_review(
            output_path=wrapper_failure_review_report_path,
            title="V1.4.3 Wrapper Failure Review",
            grouped_failures={},
            empty_message="No trusted wrapper failures are available because runtime results are invalid.",
        )
        write_failure_review(
            output_path=model_failure_review_report_path,
            title="V1.4.3 Model Failure Review",
            grouped_failures={},
            empty_message="No trusted model failures are available because runtime results are invalid.",
        )
        write_decision_report(output_path=decision_report_path, status=status, notes=notes)
        return {
            "status": status,
            "trusted_record_count": 0,
            "accepted_checkpoint": prerequisites["accepted_checkpoint"],
        }

    if set(seen_ids) != set(EXPECTED_SCENARIO_IDS):
        status = STATUS_INVALID
        unknown_ids = sorted(set(seen_ids) - set(EXPECTED_SCENARIO_IDS))
        notes = ["runtime outputs do not match the pinned v1.4 scenario set"]
        if unknown_ids:
            notes.append(f"unknown scenario ids: {', '.join(unknown_ids)}")
        rows = [[scenario_id, "yes" if scenario_id in seen_ids else "no", "(invalid)" if scenario_id in seen_ids else "(missing)", "-", "-", "scenario set mismatch"] for scenario_id in EXPECTED_SCENARIO_IDS]
        write_ingestion_review(
            output_path=ingestion_review_report_path,
            status=status,
            notes=notes,
            outputs_present=outputs_present,
            results_present=results_present,
            manifest_present=execution_manifest_present,
        )
        write_scenario_matrix(output_path=scenario_result_matrix_report_path, rows=rows)
        write_failure_review(
            output_path=wrapper_failure_review_report_path,
            title="V1.4.3 Wrapper Failure Review",
            grouped_failures={},
            empty_message="No trusted wrapper failures are available because runtime results are invalid.",
        )
        write_failure_review(
            output_path=model_failure_review_report_path,
            title="V1.4.3 Model Failure Review",
            grouped_failures={},
            empty_message="No trusted model failures are available because runtime results are invalid.",
        )
        write_decision_report(output_path=decision_report_path, status=status, notes=notes)
        return {
            "status": status,
            "trusted_record_count": 0,
            "accepted_checkpoint": prerequisites["accepted_checkpoint"],
        }

    record_statuses: list[str] = []
    for record in trusted_records:
        classification, inferred_wrapper, inferred_model = classify_trusted_record(record)
        scenario_id = record["scenario_id"]
        wrapper_summary = ", ".join(inferred_wrapper) if inferred_wrapper else "-"
        model_summary = ", ".join(inferred_model) if inferred_model else "-"
        note = "trusted record"
        if classification == STATUS_INCOMPLETE:
            note = "execution ended blocked/incomplete without a provable wrapper failure"
        elif classification == STATUS_WRAPPER_REPAIR and inferred_model:
            note = "wrapper failure wins because model diagnosis is not fair until wrapper issues are removed"
        elif classification == STATUS_MODEL_REPAIR:
            note = "model failure with no wrapper failures"
        rows.append([scenario_id, "yes", record["final_outcome"], wrapper_summary, model_summary, note])
        if inferred_wrapper:
            wrapper_failures[scenario_id] = inferred_wrapper
        if inferred_model:
            model_failures[scenario_id] = inferred_model
        record_statuses.append(classification)

    if STATUS_INCOMPLETE in record_statuses:
        status = STATUS_INCOMPLETE
        notes = ["one or more trusted scenario records are blocked or incomplete without enough evidence to prove a wrapper failure"]
    elif STATUS_WRAPPER_REPAIR in record_statuses:
        status = STATUS_WRAPPER_REPAIR
        notes = ["trusted runtime results show wrapper/runtime contract failures"]
    elif STATUS_MODEL_REPAIR in record_statuses:
        status = STATUS_MODEL_REPAIR
        notes = ["trusted runtime results show no wrapper failures but accepted v1.0.5 model output fails one or more runtime scenarios"]
    else:
        status = STATUS_PASSED
        notes = ["all 10 trusted scenario records pass with no wrapper failures, no model failures, and no evidence/schema issues"]

    write_ingestion_review(
        output_path=ingestion_review_report_path,
        status=status,
        notes=notes,
        outputs_present=outputs_present,
        results_present=results_present,
        manifest_present=execution_manifest_present,
    )
    write_scenario_matrix(output_path=scenario_result_matrix_report_path, rows=rows)
    write_failure_review(
        output_path=wrapper_failure_review_report_path,
        title="V1.4.3 Wrapper Failure Review",
        grouped_failures=wrapper_failures,
        empty_message="No trusted wrapper/runtime failures were found.",
    )
    write_failure_review(
        output_path=model_failure_review_report_path,
        title="V1.4.3 Model Failure Review",
        grouped_failures=model_failures,
        empty_message="No trusted model/runtime-contract failures were found.",
    )
    write_decision_report(output_path=decision_report_path, status=status, notes=notes)

    return {
        "status": status,
        "trusted_record_count": len(trusted_records),
        "accepted_checkpoint": prerequisites["accepted_checkpoint"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest external runtime outputs and classify v1.4 runtime results."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_4_3_runtime_scenario_results()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
