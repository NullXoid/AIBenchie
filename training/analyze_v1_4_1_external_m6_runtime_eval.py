from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_PROJECT_ROOT))

from training.analyze_v1_4_runtime_eval_readiness import (
    ACCEPTED_CHECKPOINT,
    DEFAULT_BLOCKED_SUMMARY_REPORT,
    DEFAULT_DECISION_REPORT as DEFAULT_V1_4_DECISION_REPORT,
    EVALS_RUNTIME_DIR,
    EVIDENCE_ONLY_SFT_ADAPTERS,
    PARKED_DPO_ADAPTERS,
    PROJECT_ROOT,
    STATUS_READY,
    STATUS_WAITING,
    last_nonempty_line,
    write_report,
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"
SIBLING_CPP_PROJECT_ROOT = PROJECT_ROOT.parent / "AiAssistant"

DEFAULT_EXTERNAL_EVIDENCE_JSON = (
    SIBLING_CPP_PROJECT_ROOT / "reports" / "runtime" / "m17_lv7_v1_4_external_m6_evidence.json"
)
DEFAULT_SURFACE_REPORT = SIBLING_CPP_PROJECT_ROOT / "docs" / "M17_RC2_LV7_RUNTIME_SURFACE_VERIFICATION_REPORT.md"
DEFAULT_CONTRACT_REPORT = SIBLING_CPP_PROJECT_ROOT / "docs" / "M17_LV7_V1_4_CONTRACT_TEST_REPORT.md"
DEFAULT_RUNNER_READINESS_REPORT = (
    SIBLING_CPP_PROJECT_ROOT / "docs" / "M17_LV7_V1_4_SCENARIO_RUNNER_READINESS.md"
)
DEFAULT_WRAPPER_DECISION_REPORT = SIBLING_CPP_PROJECT_ROOT / "docs" / "M17_NEXT_STEP_DECISION.md"

DEFAULT_EVIDENCE_REVIEW_REPORT = REPORTS_RUNTIME_DIR / "V1_4_1_EXTERNAL_M6_EVIDENCE_REVIEW.md"
DEFAULT_EXECUTION_PLAN_REPORT = REPORTS_RUNTIME_DIR / "V1_4_1_RUNTIME_EXECUTION_PLAN.md"
DEFAULT_V1_4_1_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_4_1_NEXT_STEP_DECISION.md"

STATUS_INCOMPLETE = "RUNTIME_EVIDENCE_INCOMPLETE"
STATUS_INVALID = "RUNTIME_EVIDENCE_INVALID"

APPROVED_STATUSES = {
    STATUS_READY,
    STATUS_INCOMPLETE,
    STATUS_INVALID,
}

EXPECTED_V1_4_STATUS = STATUS_WAITING
EXPECTED_RUNTIME_SUITE_ID = "lv7_runtime_v1_4"
EXPECTED_RUNTIME_SCENARIO_COUNT = 10

EXPECTED_ARTIFACT = "NullXoid-1.0.0-rc2-windows-x64"
EXPECTED_RELEASE_TAG = "v1.0-nullxoid-cpp-l7-release-candidate-rc2"
EXPECTED_DESKTOP_COMMIT = "2744dd1cf9ca9b1954182275b17cecdaa0639a56"
EXPECTED_BACKEND_TAG = "v0.2-nullxoid-backend-l7-ready"
EXPECTED_BACKEND_COMMIT = "0da516f332fc9689798cdcba19053f3104c8199f"
EXPECTED_FINAL_STATUS = "M17_READY_FOR_LV7_V1_4_EVAL"

REQUIRED_TRUE_FIELDS = (
    "source_equivalence_verified",
    "downloaded_artifact_verified",
    "m6_entrypoint_present",
    "legacy_unchanged",
    "level7_shadow_dry_run_only",
    "level7_explicit",
    "policy_rationale_preserved",
    "nullxoid_signal_stripped",
    "policy_rationale_not_controller_metadata",
    "pass1_buffered",
    "blocked_not_required_sanitized_pass1",
    "exactly_one_bounded_pass2",
    "pass2_timeout_sanitized_pass1",
    "pass2_cancel_sanitized_pass1",
    "pass1_cancel_no_final_answer",
    "toolfollowup_blocked",
    "hybrid_blocked",
    "backend_contract_stable",
    "runtime_logs_metrics_sufficient",
    "mock_contract_tests_passed",
    "scenario_runner_ready",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def display_path(path: Path | None) -> str:
    if path is None:
        return "(not checked)"
    return str(path)


def compute_runtime_suite_manifest(runtime_scenarios_dir: Path) -> dict[str, Any]:
    entries: list[dict[str, str]] = []
    scenario_ids: set[str] = set()
    yaml_paths = sorted(runtime_scenarios_dir.glob("*.yaml"))
    require(
        len(yaml_paths) == EXPECTED_RUNTIME_SCENARIO_COUNT,
        f"runtime suite must contain exactly {EXPECTED_RUNTIME_SCENARIO_COUNT} yaml files",
    )
    for yaml_path in yaml_paths:
        payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        scenario_id = payload.get("scenario_id")
        require(isinstance(scenario_id, str) and scenario_id, f"{yaml_path} is missing scenario_id")
        require(
            payload.get("eval_suite_id") == EXPECTED_RUNTIME_SUITE_ID,
            f"{yaml_path} does not belong to {EXPECTED_RUNTIME_SUITE_ID}",
        )
        entries.append(
            {
                "scenario_id": scenario_id,
                "file_path": str(yaml_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "sha256": sha256_file(yaml_path),
            }
        )
        scenario_ids.add(scenario_id)

    manifest_payload = {
        "lv7_runtime_suite_id": EXPECTED_RUNTIME_SUITE_ID,
        "entries": sorted(entries, key=lambda item: item["scenario_id"]),
    }
    manifest_sha = sha256_bytes(
        json.dumps(manifest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return {
        "entries": manifest_payload["entries"],
        "sha256": manifest_sha,
        "scenario_ids": scenario_ids,
    }


def load_prior_gate_state(
    *,
    v1_4_decision_report_path: Path,
    v1_3_6_2_blocked_summary_path: Path,
) -> dict[str, Any]:
    require(v1_4_decision_report_path.exists(), f"missing v1.4 decision report: {v1_4_decision_report_path}")
    require(
        v1_3_6_2_blocked_summary_path.exists(),
        f"missing v1.3.6.2 blocked summary: {v1_3_6_2_blocked_summary_path}",
    )
    require(
        last_nonempty_line(v1_4_decision_report_path) == EXPECTED_V1_4_STATUS,
        f"{v1_4_decision_report_path} does not end with {EXPECTED_V1_4_STATUS}",
    )

    blocked_summary_text = v1_3_6_2_blocked_summary_path.read_text(encoding="utf-8")
    for fragment in (
        "REGRESSION_BLOCKED",
        ACCEPTED_CHECKPOINT,
        EVIDENCE_ONLY_SFT_ADAPTERS[0],
        EVIDENCE_ONLY_SFT_ADAPTERS[1],
        "MODEL_REPAIR_PAUSED_PENDING_RUNTIME_EVIDENCE",
    ):
        require(fragment in blocked_summary_text, f"missing checkpoint fragment in blocked summary: {fragment}")

    accepted_dir = PROJECT_ROOT / ACCEPTED_CHECKPOINT
    require(accepted_dir.exists(), f"accepted checkpoint is missing: {accepted_dir}")
    for adapter_path in EVIDENCE_ONLY_SFT_ADAPTERS + PARKED_DPO_ADAPTERS:
        require((PROJECT_ROOT / adapter_path).exists(), f"expected adapter path is missing: {adapter_path}")

    return {
        "accepted_checkpoint": ACCEPTED_CHECKPOINT,
        "evidence_only_adapters": list(EVIDENCE_ONLY_SFT_ADAPTERS),
        "parked_dpo_adapters": list(PARKED_DPO_ADAPTERS),
        "v1_4_status": EXPECTED_V1_4_STATUS,
    }


def validate_traceability_markdown(
    *,
    surface_report_path: Path | None,
    contract_report_path: Path | None,
    runner_readiness_report_path: Path | None,
    wrapper_decision_report_path: Path | None,
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    errors: list[str] = []

    doc_specs = (
        (
            "surface_report",
            surface_report_path,
            (
                EXPECTED_ARTIFACT,
                EXPECTED_RELEASE_TAG,
                EXPECTED_DESKTOP_COMMIT,
                EXPECTED_BACKEND_TAG,
                EXPECTED_BACKEND_COMMIT,
                EXPECTED_FINAL_STATUS,
            ),
        ),
        (
            "contract_report",
            contract_report_path,
            (
                "policy_rationale",
                "nullxoid_signal",
                "ToolFollowup",
                "Hybrid",
            ),
        ),
        (
            "runner_readiness_report",
            runner_readiness_report_path,
            (
                EXPECTED_ARTIFACT,
                EXPECTED_RELEASE_TAG,
                EXPECTED_DESKTOP_COMMIT,
                EXPECTED_BACKEND_TAG,
                EXPECTED_BACKEND_COMMIT,
                "scorer changes",
                "blind-suite mutation",
                "adapter promotion",
                "backend drift",
            ),
        ),
    )

    for label, path, required_fragments in doc_specs:
        if path is None:
            checks.append({"label": label, "path": "(not checked)", "state": "disabled"})
            continue
        if not path.exists():
            checks.append({"label": label, "path": str(path), "state": "missing"})
            continue
        text = path.read_text(encoding="utf-8").strip()
        checks.append({"label": label, "path": str(path), "state": "checked"})
        if not text:
            errors.append(f"{label} is empty: {path}")
            continue
        for fragment in required_fragments:
            if fragment not in text:
                errors.append(f"{label} contradicts M17 traceability: missing `{fragment}`")

    if wrapper_decision_report_path is None:
        checks.append({"label": "wrapper_decision_report", "path": "(not checked)", "state": "disabled"})
    elif not wrapper_decision_report_path.exists():
        checks.append(
            {
                "label": "wrapper_decision_report",
                "path": str(wrapper_decision_report_path),
                "state": "missing",
            }
        )
    else:
        checks.append(
            {
                "label": "wrapper_decision_report",
                "path": str(wrapper_decision_report_path),
                "state": "checked",
            }
        )
        if last_nonempty_line(wrapper_decision_report_path) != EXPECTED_FINAL_STATUS:
            errors.append(
                "wrapper_decision_report contradicts M17 final status: "
                f"expected `{EXPECTED_FINAL_STATUS}`"
            )

    return {
        "checks": checks,
        "errors": errors,
    }


def validate_external_evidence(
    *,
    evidence_json_path: Path,
    surface_report_path: Path | None,
    contract_report_path: Path | None,
    runner_readiness_report_path: Path | None,
    wrapper_decision_report_path: Path | None,
    runtime_scenarios_dir: Path,
) -> dict[str, Any]:
    suite_manifest = compute_runtime_suite_manifest(runtime_scenarios_dir)
    markdown_validation = validate_traceability_markdown(
        surface_report_path=surface_report_path,
        contract_report_path=contract_report_path,
        runner_readiness_report_path=runner_readiness_report_path,
        wrapper_decision_report_path=wrapper_decision_report_path,
    )
    if not evidence_json_path.exists():
        return {
            "status": STATUS_INCOMPLETE,
            "errors": [f"missing external evidence JSON: {evidence_json_path}"],
            "payload": None,
            "suite_manifest": suite_manifest,
            "markdown_checks": markdown_validation["checks"],
        }

    try:
        payload = json.loads(evidence_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": STATUS_INVALID,
            "errors": [f"external evidence JSON is malformed: {exc}"],
            "payload": None,
            "suite_manifest": suite_manifest,
            "markdown_checks": markdown_validation["checks"],
        }

    if not isinstance(payload, dict):
        return {
            "status": STATUS_INVALID,
            "errors": ["external evidence payload must be a JSON object"],
            "payload": None,
            "suite_manifest": suite_manifest,
            "markdown_checks": markdown_validation["checks"],
        }

    missing_fields = [
        field
        for field in (
            "artifact",
            "release_tag",
            "desktop_commit",
            "backend_tag",
            "backend_commit",
            "final_status",
            *REQUIRED_TRUE_FIELDS,
        )
        if field not in payload
    ]
    if missing_fields:
        return {
            "status": STATUS_INCOMPLETE,
            "errors": [f"missing required M17 evidence fields: {', '.join(sorted(missing_fields))}"],
            "payload": payload,
            "suite_manifest": suite_manifest,
            "markdown_checks": markdown_validation["checks"],
        }

    errors: list[str] = []

    expected_values = {
        "artifact": EXPECTED_ARTIFACT,
        "release_tag": EXPECTED_RELEASE_TAG,
        "desktop_commit": EXPECTED_DESKTOP_COMMIT,
        "backend_tag": EXPECTED_BACKEND_TAG,
        "backend_commit": EXPECTED_BACKEND_COMMIT,
        "final_status": EXPECTED_FINAL_STATUS,
    }
    for field, expected_value in expected_values.items():
        actual_value = payload.get(field)
        if actual_value != expected_value:
            errors.append(f"{field} must equal `{expected_value}`")

    for field in REQUIRED_TRUE_FIELDS:
        actual_value = payload.get(field)
        if actual_value is not True:
            errors.append(f"{field} must be true")

    errors.extend(markdown_validation["errors"])

    if errors:
        return {
            "status": STATUS_INVALID,
            "errors": errors,
            "payload": payload,
            "suite_manifest": suite_manifest,
            "markdown_checks": markdown_validation["checks"],
        }

    return {
        "status": STATUS_READY,
        "errors": [],
        "payload": payload,
        "suite_manifest": suite_manifest,
        "markdown_checks": markdown_validation["checks"],
    }


def write_external_evidence_review(
    *,
    output_path: Path,
    prior_state: dict[str, Any],
    evidence_validation: dict[str, Any],
    evidence_json_path: Path,
) -> None:
    suite_manifest = evidence_validation["suite_manifest"]
    lines = [
        "# V1.4.1 External M6 Evidence Review",
        "",
        "- `paraphrase_v0` is a development set.",
        "- `blind_v1_3` remains the historical blind evidence layer.",
        "- `blind_v1_3_contractfix_v1_3_5` remains the replay-only contract-correction variant used for corrected blind-probe comparison.",
        "- DPO is for preference contrast, not lexical-token repair.",
        "- No broad generalization claim is justified from this layer alone.",
        f"- Accepted checkpoint remains `{prior_state['accepted_checkpoint']}`.",
        f"- Evidence-only adapters remain `{EVIDENCE_ONLY_SFT_ADAPTERS[0]}` and `{EVIDENCE_ONLY_SFT_ADAPTERS[1]}`.",
        "- `v1.4` previously ended `RUNTIME_EVAL_WAITING_ON_M6` and remains the gating milestone.",
        "- This milestone ingests external M17 evidence read-only and does not invoke wrapper/runtime flows from this repo.",
        "",
        "## External Evidence Source",
        "",
        f"- external JSON path used: `{evidence_json_path}`",
        f"- local runtime scenario directory: `{runtime_scenarios_dir_display()}`",
        f"- local runtime scenario count: `{len(suite_manifest['entries'])}`",
        f"- local runtime suite sha256: `{suite_manifest['sha256']}`",
        "",
        "## Traceability",
        "",
    ]

    payload = evidence_validation["payload"]
    if isinstance(payload, dict):
        lines.extend(
            [
                f"- package: `{payload.get('artifact', '(missing)')}`",
                f"- release tag: `{payload.get('release_tag', '(missing)')}`",
                f"- desktop commit: `{payload.get('desktop_commit', '(missing)')}`",
                f"- backend tag: `{payload.get('backend_tag', '(missing)')}`",
                f"- backend commit: `{payload.get('backend_commit', '(missing)')}`",
                f"- M17 final status: `{payload.get('final_status', '(missing)')}`",
            ]
        )
    else:
        lines.append("- traceability fields unavailable because the M17 JSON could not be validated")

    lines.extend(
        [
            "",
            "## Optional Markdown Cross-Checks",
            "",
        ]
    )
    for check in evidence_validation["markdown_checks"]:
        lines.append(f"- {check['label']}: `{check['state']}` at `{check['path']}`")

    lines.extend(["", "## Evidence Status", ""])
    if evidence_validation["status"] == STATUS_READY:
        lines.extend(
            [
                "- external M17 evidence is present and valid",
                "- optional markdown references, when present, did not contradict the JSON handoff",
                "- no scorer change, blind-suite mutation, adapter promotion, wrapper mutation, or backend drift was performed",
            ]
        )
    else:
        lines.append(f"- external M17 evidence status: `{evidence_validation['status']}`")
        lines.extend(["", "## Validation Errors", ""])
        lines.extend(f"- {error}" for error in evidence_validation["errors"])

    write_report(output_path, lines)


def write_runtime_execution_plan(
    *,
    output_path: Path,
    evidence_validation: dict[str, Any],
    evidence_json_path: Path,
) -> None:
    suite_manifest = evidence_validation["suite_manifest"]
    lines = [
        "# V1.4.1 Runtime Execution Plan",
        "",
        "- `policy_rationale` is model output.",
        "- `nullxoid_signal` is controller metadata.",
        "- Do not parse `policy_rationale` as controller metadata.",
        "- Do not strip `policy_rationale` unless an explicit profile formatter does so.",
        "- Only parse and strip fenced `nullxoid_signal`.",
        "",
        "## LV7 Runtime Package",
        "",
        f"- runtime scenario directory: `{runtime_scenarios_dir_display()}`",
        f"- scenario count: `{len(suite_manifest['entries'])}`",
        f"- accepted checkpoint for runtime execution: `{ACCEPTED_CHECKPOINT}`",
        "",
        "## External Execution Policy",
        "",
        "- LV7 does not invoke wrapper code from this repo",
        "- LV7 consumes the sibling C++ M17 evidence bundle as a read-only bridge input",
        "- LV7 does not require `reports/runtime/v1_4_runtime_outputs.jsonl` for the v1.4.1 decision",
        "- LV7 does not require `reports/runtime/V1_4_RUNTIME_EVAL_RESULTS.md` for the v1.4.1 decision",
        "- evidence-only SFT repair adapters are not promoted here",
        "- DPO remains parked",
        "",
        "## Current Step",
        "",
        f"- external JSON path: `{evidence_json_path}`",
    ]
    if evidence_validation["status"] == STATUS_READY:
        lines.append("- valid M17 evidence has been ingested; LV7 may advance the runtime gate without replaying wrapper/runtime flows in this repo")
    else:
        lines.append("- wait for a valid sibling M17 evidence bundle before advancing the runtime gate")
    write_report(output_path, lines)


def write_decision_report(
    *,
    output_path: Path,
    status: str,
    notes: list[str],
    evidence_json_path: Path,
) -> None:
    lines = [
        "# V1.4.1 Next Step Decision",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- Evidence-only adapters remain `{EVIDENCE_ONLY_SFT_ADAPTERS[0]}` and `{EVIDENCE_ONLY_SFT_ADAPTERS[1]}`.",
        f"- Parked DPO adapters remain `{PARKED_DPO_ADAPTERS[0]}` and `{PARKED_DPO_ADAPTERS[1]}`.",
        f"- External JSON path used: `{evidence_json_path}`.",
        "- LV7 remains ingestion-first and does not invoke wrapper code directly from this repo.",
        "- No scorer change, blind-suite mutation, adapter promotion, wrapper mutation, or backend drift occurred in this milestone.",
        "",
        "## Decision Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in notes)
    lines.extend(["", status])
    write_report(output_path, lines)


def runtime_scenarios_dir_display() -> str:
    return str(EVALS_RUNTIME_DIR.relative_to(PROJECT_ROOT)).replace("\\", "/")


def analyze_v1_4_1_external_m6_runtime_eval(
    *,
    v1_4_decision_report_path: Path = DEFAULT_V1_4_DECISION_REPORT,
    v1_3_6_2_blocked_summary_path: Path = DEFAULT_BLOCKED_SUMMARY_REPORT,
    runtime_scenarios_dir: Path = EVALS_RUNTIME_DIR,
    external_evidence_json_path: Path = DEFAULT_EXTERNAL_EVIDENCE_JSON,
    wrapper_surface_report_path: Path | None = DEFAULT_SURFACE_REPORT,
    wrapper_contract_report_path: Path | None = DEFAULT_CONTRACT_REPORT,
    wrapper_runner_readiness_report_path: Path | None = DEFAULT_RUNNER_READINESS_REPORT,
    wrapper_decision_report_path: Path | None = DEFAULT_WRAPPER_DECISION_REPORT,
    evidence_review_report_path: Path = DEFAULT_EVIDENCE_REVIEW_REPORT,
    runtime_execution_plan_report_path: Path = DEFAULT_EXECUTION_PLAN_REPORT,
    decision_report_path: Path = DEFAULT_V1_4_1_DECISION_REPORT,
) -> dict[str, Any]:
    prior_state = load_prior_gate_state(
        v1_4_decision_report_path=v1_4_decision_report_path,
        v1_3_6_2_blocked_summary_path=v1_3_6_2_blocked_summary_path,
    )
    evidence_validation = validate_external_evidence(
        evidence_json_path=external_evidence_json_path,
        surface_report_path=wrapper_surface_report_path,
        contract_report_path=wrapper_contract_report_path,
        runner_readiness_report_path=wrapper_runner_readiness_report_path,
        wrapper_decision_report_path=wrapper_decision_report_path,
        runtime_scenarios_dir=runtime_scenarios_dir,
    )

    write_external_evidence_review(
        output_path=evidence_review_report_path,
        prior_state=prior_state,
        evidence_validation=evidence_validation,
        evidence_json_path=external_evidence_json_path,
    )
    write_runtime_execution_plan(
        output_path=runtime_execution_plan_report_path,
        evidence_validation=evidence_validation,
        evidence_json_path=external_evidence_json_path,
    )
    write_decision_report(
        output_path=decision_report_path,
        status=evidence_validation["status"],
        notes=evidence_validation["errors"] or ["valid M17 evidence was ingested read-only from the sibling C++ repo"],
        evidence_json_path=external_evidence_json_path,
    )

    return {
        "status": evidence_validation["status"],
        "accepted_checkpoint": prior_state["accepted_checkpoint"],
        "evidence_only_adapters": prior_state["evidence_only_adapters"],
        "parked_dpo_adapters": prior_state["parked_dpo_adapters"],
        "external_evidence_valid": evidence_validation["status"] == STATUS_READY,
        "external_evidence_json_path": str(external_evidence_json_path),
        "markdown_checks": evidence_validation["markdown_checks"],
        "scenario_count": len(evidence_validation["suite_manifest"]["entries"]),
        "suite_manifest_sha256": evidence_validation["suite_manifest"]["sha256"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest external M17 runtime evidence and classify LV7 runtime readiness."
    )
    parser.add_argument("--external-evidence-json", type=Path, default=DEFAULT_EXTERNAL_EVIDENCE_JSON)
    parser.add_argument("--surface-report", type=Path, default=DEFAULT_SURFACE_REPORT)
    parser.add_argument("--contract-report", type=Path, default=DEFAULT_CONTRACT_REPORT)
    parser.add_argument("--runner-readiness-report", type=Path, default=DEFAULT_RUNNER_READINESS_REPORT)
    parser.add_argument("--wrapper-decision-report", type=Path, default=DEFAULT_WRAPPER_DECISION_REPORT)
    parser.add_argument("--evidence-review-report", type=Path, default=DEFAULT_EVIDENCE_REVIEW_REPORT)
    parser.add_argument("--runtime-execution-plan-report", type=Path, default=DEFAULT_EXECUTION_PLAN_REPORT)
    parser.add_argument("--decision-report", type=Path, default=DEFAULT_V1_4_1_DECISION_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = analyze_v1_4_1_external_m6_runtime_eval(
        external_evidence_json_path=args.external_evidence_json,
        wrapper_surface_report_path=args.surface_report,
        wrapper_contract_report_path=args.contract_report,
        wrapper_runner_readiness_report_path=args.runner_readiness_report,
        wrapper_decision_report_path=args.wrapper_decision_report,
        evidence_review_report_path=args.evidence_review_report,
        runtime_execution_plan_report_path=args.runtime_execution_plan_report,
        decision_report_path=args.decision_report,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
