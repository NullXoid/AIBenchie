from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

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
from training.analyze_v1_4_2_runtime_scenario_eval_plan import (  # noqa: E402
    DEFAULT_SUITE_MANIFEST_JSON,
    EXPECTED_RUNTIME_SUITE_ID,
    model_adapter_path_is_accepted,
)
from training.analyze_v1_4_3_runtime_scenario_results import (  # noqa: E402
    DEFAULT_DECISION_REPORT as DEFAULT_V1_4_3_DECISION_REPORT,
    DEFAULT_MODEL_FAILURE_REVIEW_REPORT,
    DEFAULT_RUNTIME_EXECUTION_MANIFEST,
    DEFAULT_RUNTIME_OUTPUTS,
    DEFAULT_RUNTIME_RESULTS_REPORT,
    DEFAULT_WRAPPER_FAILURE_REVIEW_REPORT,
    EXPECTED_BACKEND_COMMIT as EXPECTED_BACKEND_ANCHOR_COMMIT,
    STATUS_MODEL_REPAIR,
)
from training.analyze_v1_4_runtime_eval_readiness import (  # noqa: E402
    PROJECT_ROOT,
    last_nonempty_line,
    render_markdown_table,
    write_report,
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"

DEFAULT_V1_4_2_ACCEPTANCE_REPORT = REPORTS_RUNTIME_DIR / "V1_4_2_SCENARIO_ACCEPTANCE_CRITERIA.md"
DEFAULT_V1_4_4_DIAGNOSIS_REPORT = REPORTS_RUNTIME_DIR / "V1_4_4_RUNTIME_MODEL_FAILURE_DIAGNOSIS.md"
DEFAULT_V1_4_4_MATRIX_REPORT = REPORTS_RUNTIME_DIR / "V1_4_4_SCENARIO_DIAGNOSIS_MATRIX.md"
DEFAULT_V1_4_4_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_4_4_NEXT_STEP_DECISION.md"
DEFAULT_V1_4_4_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_4_4_runtime_model_failure_diagnosis.json"

STATUS_COMPLETE = "V1_4_4_DIAGNOSIS_COMPLETE"
STATUS_INSUFFICIENT = "V1_4_4_DIAGNOSIS_INSUFFICIENT"

APPROVED_STATUSES = {
    STATUS_COMPLETE,
    STATUS_INSUFFICIENT,
}

PASS_CATEGORY = "NONE"
PASS_NEXT_LANE = "NONE"

CATEGORY_PROMPT_FORMAT = "PROMPT_RUNTIME_FORMATTING_MISMATCH"
CATEGORY_POLICY_RATIONALE = "POLICY_RATIONALE_FORMAT_OR_CONTENT_FAILURE"
CATEGORY_WRONG_MODE = "WRONG_LV7_MODE_SELECTION"
CATEGORY_SHARED_CONTRACT = "SHARED_CONTRACT_BEHAVIOR_FAILURE"
CATEGORY_SPEC_MISMATCH = "SCENARIO_OR_SPEC_MISMATCH"
CATEGORY_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
CATEGORY_MODEL_BEHAVIOR = "MODEL_BEHAVIOR_FAILURE"

LANE_PROMPT_FORMAT = "PROMPT_OR_RUNTIME_FORMAT_FIX"
LANE_POLICY_RATIONALE = "POLICY_RATIONALE_CONTRACT_FIX"
LANE_WRONG_MODE = "LV7_MODE_SELECTION_FIX"
LANE_SHARED_CONTRACT = "SHARED_CONTRACT_FIX"
LANE_SPEC_FIX = "SCENARIO_SPEC_FIX"
LANE_MODEL_REPAIR = "MODEL_REPAIR_INVESTIGATION"
LANE_NO_ACTION = "NO_ACTION_INSUFFICIENT_EVIDENCE"

CATEGORY_TO_NEXT_LANE = {
    CATEGORY_PROMPT_FORMAT: LANE_PROMPT_FORMAT,
    CATEGORY_POLICY_RATIONALE: LANE_POLICY_RATIONALE,
    CATEGORY_WRONG_MODE: LANE_WRONG_MODE,
    CATEGORY_SHARED_CONTRACT: LANE_SHARED_CONTRACT,
    CATEGORY_SPEC_MISMATCH: LANE_SPEC_FIX,
    CATEGORY_INSUFFICIENT_EVIDENCE: LANE_NO_ACTION,
    CATEGORY_MODEL_BEHAVIOR: LANE_MODEL_REPAIR,
}

WRONG_MODE_FAILURE = (
    "wrapper behaves correctly but accepted v1.0.5 output chooses the wrong LV7 mode"
)
POLICY_RATIONALE_FAILURE = (
    "policy_rationale format or content fails in a way the wrapper cannot reasonably fix"
)
RESPONSE_BEHAVIOR_FAILURE = "response violates the scenario's expected safe behavior"
NO_WRAPPER_FAILURES_LINE = "- No trusted wrapper/runtime failures were found."


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


def excerpt(text: str, *, limit: int = 140) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."


def parse_acceptance_table(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 4:
            continue
        if cells[0] in {"scenario_id", "---"} or not cells[0]:
            continue
        rows[cells[0]] = {
            "expected_mode": cells[1],
            "expected_behavior": cells[2],
            "scenario_file": cells[3],
        }
    return rows


def parse_grouped_markdown_bullets(path: Path) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            grouped[current] = []
            continue
        if current is not None and line.startswith("- "):
            grouped[current].append(line[2:].strip())
    return grouped


def parse_results_report_sections(path: Path) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    return {
        scenario_id: "\n".join(lines).strip()
        for scenario_id, lines in sections.items()
    }


def load_suite_contract(
    *,
    suite_manifest_json_path: Path,
    acceptance_report_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = read_json(suite_manifest_json_path)
    acceptance_rows = parse_acceptance_table(acceptance_report_path)

    require(
        manifest.get("suite_id") == EXPECTED_RUNTIME_SUITE_ID,
        f"{display_path(suite_manifest_json_path)} has wrong suite_id",
    )

    scenario_contracts: list[dict[str, Any]] = []
    for scenario_id in manifest["scenario_ids"]:
        scenario_file = manifest["scenario_files"][scenario_id]
        yaml_path = PROJECT_ROOT / scenario_file
        payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

        acceptance = acceptance_rows.get(scenario_id)
        spec_conflicts: list[str] = []
        if acceptance is None:
            spec_conflicts.append("acceptance criteria row is missing")
        else:
            if acceptance["expected_mode"] != payload.get("expected_mode"):
                spec_conflicts.append("expected_mode differs between YAML and acceptance criteria")
            if acceptance["scenario_file"] != scenario_file:
                spec_conflicts.append("scenario_file differs between manifest and acceptance criteria")

        scenario_contracts.append(
            {
                "scenario_id": scenario_id,
                "scenario_file": scenario_file,
                "scenario_sha256": manifest["scenario_sha256"][scenario_id],
                "prompt_sha256": manifest["prompt_sha256"][scenario_id],
                "prompt": payload.get("prompt", ""),
                "expected_mode": payload.get("expected_mode", ""),
                "expected_behavior": None if acceptance is None else acceptance["expected_behavior"],
                "must_include": payload.get("must_include", []),
                "must_not_include": payload.get("must_not_include", []),
                "required_behavior": payload.get("required_behavior", []),
                "required_scopes": payload.get("required_scopes", []),
                "runtime_contract_focus": payload.get("runtime_contract_focus", []),
                "failure_modes": payload.get("failure_modes", []),
                "spec_conflicts": spec_conflicts,
            }
        )

    return manifest, scenario_contracts


def validate_runtime_package(
    *,
    runtime_outputs_path: Path,
    runtime_results_report_path: Path,
    runtime_execution_manifest_path: Path,
    results_sections: dict[str, str],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    require(runtime_outputs_path.exists(), f"missing runtime outputs: {display_path(runtime_outputs_path)}")
    require(
        runtime_results_report_path.exists(),
        f"missing runtime results report: {display_path(runtime_results_report_path)}",
    )
    require(
        runtime_execution_manifest_path.exists(),
        f"missing runtime execution manifest: {display_path(runtime_execution_manifest_path)}",
    )

    execution_manifest = read_json(runtime_execution_manifest_path)
    require(
        execution_manifest.get("suite_id") == EXPECTED_RUNTIME_SUITE_ID,
        "runtime execution manifest has wrong suite_id",
    )
    require(
        execution_manifest.get("model_adapter_path") == ACCEPTED_CHECKPOINT,
        "runtime execution manifest has wrong model_adapter_path",
    )
    require(
        execution_manifest.get("wrapper_artifact") == EXPECTED_ARTIFACT,
        "runtime execution manifest has wrong wrapper_artifact",
    )
    require(
        execution_manifest.get("release_tag") == EXPECTED_RELEASE_TAG,
        "runtime execution manifest has wrong release_tag",
    )
    require(
        execution_manifest.get("desktop_commit") == EXPECTED_DESKTOP_COMMIT,
        "runtime execution manifest has wrong desktop_commit",
    )
    require(
        execution_manifest.get("backend_tag") == EXPECTED_BACKEND_TAG,
        "runtime execution manifest has wrong backend_tag",
    )

    records = read_jsonl(runtime_outputs_path)
    require(
        len(records) == len(manifest["scenario_ids"]),
        "runtime outputs do not cover all pinned v1.4 scenarios exactly once",
    )

    seen_ids: set[str] = set()
    for index, record in enumerate(records, start=1):
        scenario_id = record.get("scenario_id")
        require(isinstance(scenario_id, str) and scenario_id, f"record #{index} is missing scenario_id")
        require(scenario_id not in seen_ids, f"duplicate scenario_id in runtime outputs: {scenario_id}")
        seen_ids.add(scenario_id)

        require(
            scenario_id in manifest["scenario_ids"],
            f"runtime output references unknown scenario_id: {scenario_id}",
        )
        require(
            model_adapter_path_is_accepted(str(record.get("model_adapter_path", ""))),
            f"runtime output `{scenario_id}` has wrong model_adapter_path",
        )
        require(
            record.get("wrapper_artifact") == EXPECTED_ARTIFACT,
            f"runtime output `{scenario_id}` has wrong wrapper_artifact",
        )
        require(
            record.get("release_tag") == EXPECTED_RELEASE_TAG,
            f"runtime output `{scenario_id}` has wrong release_tag",
        )
        require(
            record.get("desktop_commit") == EXPECTED_DESKTOP_COMMIT,
            f"runtime output `{scenario_id}` has wrong desktop_commit",
        )
        require(
            record.get("backend_tag") == EXPECTED_BACKEND_TAG,
            f"runtime output `{scenario_id}` has wrong backend_tag",
        )
        require(
            record.get("scenario_file") == manifest["scenario_files"][scenario_id],
            f"runtime output `{scenario_id}` has wrong scenario_file",
        )
        require(
            record.get("scenario_sha256") == manifest["scenario_sha256"][scenario_id],
            f"runtime output `{scenario_id}` has wrong scenario_sha256",
        )
        require(
            record.get("prompt_sha256") == manifest["prompt_sha256"][scenario_id],
            f"runtime output `{scenario_id}` has wrong prompt_sha256",
        )
        require(
            isinstance(record.get("wrapper_contract_failures"), list),
            f"runtime output `{scenario_id}` must serialize wrapper_contract_failures as an array",
        )
        require(
            isinstance(record.get("model_contract_failures"), list),
            f"runtime output `{scenario_id}` must serialize model_contract_failures as an array",
        )
        require(
            scenario_id in results_sections,
            f"runtime results report is missing section for `{scenario_id}`",
        )

    require(
        set(seen_ids) == set(manifest["scenario_ids"]),
        "runtime outputs do not match the pinned scenario set",
    )

    return records


def runtime_status_from_record(record: dict[str, Any]) -> str:
    has_model_failures = bool(record.get("model_contract_failures"))
    has_wrapper_failures = bool(record.get("wrapper_contract_failures"))
    if record.get("final_outcome") == "pass" and not has_model_failures and not has_wrapper_failures:
        return "pass"
    return "fail"


def expected_contract_behavior(contract: dict[str, Any]) -> str:
    parts = [
        f"expected_mode={contract['expected_mode']}",
        f"expected_behavior={contract['expected_behavior']}",
    ]
    if contract["required_behavior"]:
        parts.append("required_behavior=" + ", ".join(contract["required_behavior"]))
    if contract["required_scopes"]:
        parts.append("required_scopes=" + ", ".join(contract["required_scopes"]))
    if contract["must_include"]:
        parts.append("must_include=" + ", ".join(contract["must_include"]))
    if contract["must_not_include"]:
        parts.append("must_not_include=" + ", ".join(contract["must_not_include"]))
    return "; ".join(parts)


def observed_runtime_output(
    record: dict[str, Any],
    *,
    model_review_bullets: list[str],
) -> str:
    details = [
        f"final_outcome={record['final_outcome']}",
        f"gate_decision={record['gate_decision']}",
        f"pass1_state={record['pass1_state']}",
        f"pass2_state={record['pass2_state']}",
        f"raw_excerpt={excerpt(str(record['raw_model_text']))}",
        f"final_excerpt={excerpt(str(record['final_emitted_text']))}",
    ]
    if model_review_bullets:
        details.append("v1.4.3_review=" + "; ".join(model_review_bullets))
    return "; ".join(details)


def prompt_formatting_markers(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "can't access the web",
            "allow online access",
            "privacy/security",
            "settings",
            "allow search",
            "web right now",
        )
    )


def shared_signature(
    record: dict[str, Any],
    contract: dict[str, Any],
    *,
    model_failures: set[str],
) -> tuple[str, tuple[str, ...], bool]:
    return (
        contract["expected_mode"],
        tuple(sorted(model_failures)),
        bool(record["policy_rationale_visible"]),
    )


def classify_scenario(
    *,
    record: dict[str, Any],
    contract: dict[str, Any],
    model_review_bullets: list[str],
    shared_signature_counts: Counter[tuple[str, tuple[str, ...], bool]],
) -> dict[str, Any]:
    runtime_status = runtime_status_from_record(record)
    if runtime_status == "pass":
        return {
            "runtime_status": "pass",
            "failure_category": PASS_CATEGORY,
            "recommended_next_lane": PASS_NEXT_LANE,
            "evidence_summary": "Trusted runtime evidence shows a passing scenario; no diagnosis is needed.",
        }

    model_failures = set(str(item) for item in record["model_contract_failures"])
    model_failures.update(model_review_bullets)

    final_text = str(record["final_emitted_text"])
    raw_text = str(record["raw_model_text"])

    if not raw_text.strip() or not final_text.strip():
        return {
            "runtime_status": "fail",
            "failure_category": CATEGORY_INSUFFICIENT_EVIDENCE,
            "recommended_next_lane": CATEGORY_TO_NEXT_LANE[CATEGORY_INSUFFICIENT_EVIDENCE],
            "evidence_summary": "Trusted runtime evidence does not contain enough raw/final model text to support a narrower diagnosis for this failed scenario.",
        }

    if contract["spec_conflicts"]:
        summary = "; ".join(contract["spec_conflicts"])
        return {
            "runtime_status": "fail",
            "failure_category": CATEGORY_SPEC_MISMATCH,
            "recommended_next_lane": CATEGORY_TO_NEXT_LANE[CATEGORY_SPEC_MISMATCH],
            "evidence_summary": f"Scenario contract inputs conflict before model diagnosis: {summary}.",
        }

    if WRONG_MODE_FAILURE in model_failures:
        return {
            "runtime_status": "fail",
            "failure_category": CATEGORY_WRONG_MODE,
            "recommended_next_lane": CATEGORY_TO_NEXT_LANE[CATEGORY_WRONG_MODE],
            "evidence_summary": (
                f"Trusted v1.4.3 evidence explicitly records wrong LV7 mode selection. "
                f"Expected `{contract['expected_mode']}`, but the scenario failed with "
                f"`gate_decision={record['gate_decision']}` and no wrapper fault."
            ),
        }

    if not record["policy_rationale_visible"] or POLICY_RATIONALE_FAILURE in model_failures:
        return {
            "runtime_status": "fail",
            "failure_category": CATEGORY_POLICY_RATIONALE,
            "recommended_next_lane": CATEGORY_TO_NEXT_LANE[CATEGORY_POLICY_RATIONALE],
            "evidence_summary": (
                "Trusted runtime evidence shows missing or inadequate `policy_rationale` and no wrapper-side stripping/parsing fault. "
                f"The response still failed the `{contract['expected_mode']}` contract."
            ),
        }

    if prompt_formatting_markers(final_text):
        return {
            "runtime_status": "fail",
            "failure_category": CATEGORY_PROMPT_FORMAT,
            "recommended_next_lane": CATEGORY_TO_NEXT_LANE[CATEGORY_PROMPT_FORMAT],
            "evidence_summary": (
                "The response is framed as a runtime/configuration limitation rather than the pinned scenario contract, "
                "which points to prompt/runtime formatting mismatch over a pure model-behavior diagnosis."
            ),
        }

    signature = shared_signature(record, contract, model_failures=model_failures)
    if shared_signature_counts[signature] > 1:
        return {
            "runtime_status": "fail",
            "failure_category": CATEGORY_SHARED_CONTRACT,
            "recommended_next_lane": CATEGORY_TO_NEXT_LANE[CATEGORY_SHARED_CONTRACT],
            "evidence_summary": (
                "This failed scenario shares the same non-wrapper failure signature as other scenarios under the same expected mode, "
                "which points to a shared runtime contract defect rather than an isolated behavior miss."
            ),
        }

    if RESPONSE_BEHAVIOR_FAILURE in model_failures:
        return {
            "runtime_status": "fail",
            "failure_category": CATEGORY_MODEL_BEHAVIOR,
            "recommended_next_lane": CATEGORY_TO_NEXT_LANE[CATEGORY_MODEL_BEHAVIOR],
            "evidence_summary": (
                f"The wrapper behaved correctly and the response still violated the pinned `{contract['expected_behavior']}` behavior. "
                "No narrower non-model diagnosis explains this record honestly."
            ),
        }

    return {
        "runtime_status": "fail",
        "failure_category": CATEGORY_INSUFFICIENT_EVIDENCE,
        "recommended_next_lane": CATEGORY_TO_NEXT_LANE[CATEGORY_INSUFFICIENT_EVIDENCE],
        "evidence_summary": (
            "The trusted record failed, but the available runtime evidence and v1.4.3 review do not support a narrower diagnosis."
        ),
    }


def build_shared_signature_counts(
    records_by_id: dict[str, dict[str, Any]],
    contracts_by_id: dict[str, dict[str, Any]],
    model_review_by_id: dict[str, list[str]],
) -> Counter[tuple[str, tuple[str, ...], bool]]:
    counts: Counter[tuple[str, tuple[str, ...], bool]] = Counter()
    for scenario_id, record in records_by_id.items():
        if runtime_status_from_record(record) != "fail":
            continue
        contract = contracts_by_id[scenario_id]
        model_failures = set(str(item) for item in record["model_contract_failures"])
        model_failures.update(model_review_by_id.get(scenario_id, []))
        if WRONG_MODE_FAILURE in model_failures:
            continue
        if not record["policy_rationale_visible"] or POLICY_RATIONALE_FAILURE in model_failures:
            continue
        if prompt_formatting_markers(str(record["final_emitted_text"])):
            continue
        if RESPONSE_BEHAVIOR_FAILURE not in model_failures:
            continue
        counts[shared_signature(record, contract, model_failures=model_failures)] += 1
    return counts


def write_diagnosis_report(
    *,
    output_path: Path,
    status: str,
    diagnoses: list[dict[str, Any]],
    source_artifacts: dict[str, str],
) -> None:
    failed = [item for item in diagnoses if item["runtime_status"] == "fail"]
    category_counts = Counter(
        item["failure_category"] for item in failed if item["failure_category"] != PASS_CATEGORY
    )
    lane_counts = Counter(
        item["recommended_next_lane"] for item in failed if item["recommended_next_lane"] != PASS_NEXT_LANE
    )

    category_rows = [
        [category, str(category_counts[category]), CATEGORY_TO_NEXT_LANE.get(category, "-")]
        for category in sorted(category_counts)
    ]
    if not category_rows:
        category_rows = [["NONE", "0", "NONE"]]

    lane_rows = [[lane, str(lane_counts[lane])] for lane in sorted(lane_counts)] or [["NONE", "0"]]

    lines = [
        "# V1.4.4 Runtime Model Failure Diagnosis",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- Evidence-only adapters remain `{EVIDENCE_ONLY_SFT_ADAPTERS[0]}` and `{EVIDENCE_ONLY_SFT_ADAPTERS[1]}`.",
        f"- Parked DPO adapters remain `{PARKED_DPO_ADAPTERS[0]}` and `{PARKED_DPO_ADAPTERS[1]}`.",
        "- Wrapper-side runtime packaging is complete and the delivered runtime package is the only diagnosis input.",
        "- No trusted wrapper/runtime failures were found in `v1.4.3`.",
        "- This milestone is analysis-only and does not rerun wrapper code, training, scoring, or packaging.",
        "",
        "## Source Evidence",
        "",
        f"- runtime outputs: `{source_artifacts['runtime_outputs_path']}`",
        f"- runtime results report: `{source_artifacts['runtime_results_report_path']}`",
        f"- execution manifest: `{source_artifacts['runtime_execution_manifest_path']}`",
        f"- v1.4.3 decision: `{source_artifacts['v1_4_3_decision_report_path']}`",
        f"- v1.4.3 model review: `{source_artifacts['v1_4_3_model_failure_review_path']}`",
        f"- v1.4.3 wrapper review: `{source_artifacts['v1_4_3_wrapper_failure_review_path']}`",
        "",
        "## Diagnostic Summary",
        "",
        f"- failed scenarios diagnosed: `{len(failed)}`",
        f"- passing scenarios carried forward unchanged: `{len(diagnoses) - len(failed)}`",
        f"- milestone status: `{status}`",
        "",
        "## Dominant Failure Categories",
        "",
        render_markdown_table(
            ["failure_category", "count", "recommended_next_lane"],
            category_rows,
        ),
        "",
        "## Recommended Next Lanes",
        "",
        render_markdown_table(["recommended_next_lane", "failed_scenarios"], lane_rows),
        "",
        "## Wrapper Re-entry Rule",
        "",
        "- wrapper/backend only re-enters if LV7 provides:",
        "  - exact `scenario_id`",
        "  - observed wrapper/runtime behavior",
        "  - expected wrapper/runtime behavior",
        "  - evidence proving wrapper-side fault",
        "",
        "- absent that, wrapper stays closed.",
    ]
    write_report(output_path, lines)


def write_matrix_report(output_path: Path, diagnoses: list[dict[str, Any]]) -> None:
    rows = []
    for diagnosis in diagnoses:
        rows.append(
            [
                diagnosis["scenario_id"],
                diagnosis["runtime_status"],
                diagnosis["failure_category"],
                diagnosis["recommended_next_lane"],
                diagnosis["evidence_summary"],
            ]
        )
    lines = [
        "# V1.4.4 Scenario Diagnosis Matrix",
        "",
        render_markdown_table(
            [
                "scenario_id",
                "runtime_status",
                "failure_category",
                "recommended_next_lane",
                "evidence_summary",
            ],
            rows,
        ),
    ]
    write_report(output_path, lines)


def write_decision_report(
    *,
    output_path: Path,
    status: str,
    diagnoses: list[dict[str, Any]],
) -> None:
    failed = [item for item in diagnoses if item["runtime_status"] == "fail"]
    lanes = sorted(
        {
            item["recommended_next_lane"]
            for item in failed
            if item["recommended_next_lane"] != PASS_NEXT_LANE
        }
    )
    lines = [
        "# V1.4.4 Next Step Decision",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        "- This milestone is analysis-only and does not authorize immediate SFT, DPO, wrapper reruns, or backend identity changes.",
        f"- Failed scenarios reviewed: `{len(failed)}`.",
        f"- Recommended next lanes from the current evidence: `{', '.join(lanes) if lanes else 'NONE'}`.",
    ]
    if status == STATUS_COMPLETE:
        lines.append("- Every failed scenario received a supported diagnosis and a concrete next lane.")
    else:
        lines.append("- One or more failed scenarios still lack enough evidence for a supported diagnosis.")
    lines.extend(["", status])
    write_report(output_path, lines)


def analyze_v1_4_4_runtime_model_failure_diagnosis(
    *,
    runtime_outputs_path: Path = DEFAULT_RUNTIME_OUTPUTS,
    runtime_results_report_path: Path = DEFAULT_RUNTIME_RESULTS_REPORT,
    runtime_execution_manifest_path: Path = DEFAULT_RUNTIME_EXECUTION_MANIFEST,
    v1_4_3_decision_report_path: Path = DEFAULT_V1_4_3_DECISION_REPORT,
    v1_4_3_model_failure_review_path: Path = DEFAULT_MODEL_FAILURE_REVIEW_REPORT,
    v1_4_3_wrapper_failure_review_path: Path = DEFAULT_WRAPPER_FAILURE_REVIEW_REPORT,
    suite_manifest_json_path: Path = DEFAULT_SUITE_MANIFEST_JSON,
    acceptance_report_path: Path = DEFAULT_V1_4_2_ACCEPTANCE_REPORT,
    diagnosis_report_path: Path = DEFAULT_V1_4_4_DIAGNOSIS_REPORT,
    matrix_report_path: Path = DEFAULT_V1_4_4_MATRIX_REPORT,
    decision_report_path: Path = DEFAULT_V1_4_4_DECISION_REPORT,
    json_report_path: Path = DEFAULT_V1_4_4_JSON_REPORT,
) -> dict[str, Any]:
    source_artifacts = {
        "runtime_outputs_path": display_path(runtime_outputs_path),
        "runtime_results_report_path": display_path(runtime_results_report_path),
        "runtime_execution_manifest_path": display_path(runtime_execution_manifest_path),
        "v1_4_3_decision_report_path": display_path(v1_4_3_decision_report_path),
        "v1_4_3_model_failure_review_path": display_path(v1_4_3_model_failure_review_path),
        "v1_4_3_wrapper_failure_review_path": display_path(v1_4_3_wrapper_failure_review_path),
        "suite_manifest_json_path": display_path(suite_manifest_json_path),
        "acceptance_report_path": display_path(acceptance_report_path),
    }

    diagnoses: list[dict[str, Any]] = []
    status = STATUS_COMPLETE

    try:
        require(
            last_nonempty_line(v1_4_3_decision_report_path) == STATUS_MODEL_REPAIR,
            f"{display_path(v1_4_3_decision_report_path)} does not end with {STATUS_MODEL_REPAIR}",
        )
        wrapper_review_text = v1_4_3_wrapper_failure_review_path.read_text(encoding="utf-8")
        require(
            NO_WRAPPER_FAILURES_LINE in wrapper_review_text,
            f"{display_path(v1_4_3_wrapper_failure_review_path)} no longer reports an empty wrapper failure review",
        )
        require(
            (PROJECT_ROOT / ACCEPTED_CHECKPOINT).exists(),
            f"accepted checkpoint is missing: {ACCEPTED_CHECKPOINT}",
        )
        for adapter_path in (*EVIDENCE_ONLY_SFT_ADAPTERS, *PARKED_DPO_ADAPTERS):
            require((PROJECT_ROOT / adapter_path).exists(), f"expected adapter path is missing: {adapter_path}")

        results_sections = parse_results_report_sections(runtime_results_report_path)
        manifest, contracts = load_suite_contract(
            suite_manifest_json_path=suite_manifest_json_path,
            acceptance_report_path=acceptance_report_path,
        )
        records = validate_runtime_package(
            runtime_outputs_path=runtime_outputs_path,
            runtime_results_report_path=runtime_results_report_path,
            runtime_execution_manifest_path=runtime_execution_manifest_path,
            results_sections=results_sections,
            manifest=manifest,
        )
        model_review = parse_grouped_markdown_bullets(v1_4_3_model_failure_review_path)

        contracts_by_id = {contract["scenario_id"]: contract for contract in contracts}
        records_by_id = {record["scenario_id"]: record for record in records}

        for scenario_id, record in records_by_id.items():
            require(
                not record["wrapper_contract_failures"],
                f"runtime output `{scenario_id}` still carries wrapper failures and is not eligible for model-only diagnosis",
            )

        shared_signature_counts = build_shared_signature_counts(
            records_by_id,
            contracts_by_id,
            model_review,
        )

        for scenario_id in manifest["scenario_ids"]:
            record = records_by_id[scenario_id]
            contract = contracts_by_id[scenario_id]
            model_review_bullets = model_review.get(scenario_id, [])

            diagnosis = classify_scenario(
                record=record,
                contract=contract,
                model_review_bullets=model_review_bullets,
                shared_signature_counts=shared_signature_counts,
            )
            diagnoses.append(
                {
                    "scenario_id": scenario_id,
                    "runtime_status": diagnosis["runtime_status"],
                    "observed_runtime_output": observed_runtime_output(
                        record,
                        model_review_bullets=model_review_bullets,
                    ),
                    "expected_contract_behavior": expected_contract_behavior(contract),
                    "failure_category": diagnosis["failure_category"],
                    "evidence_summary": diagnosis["evidence_summary"],
                    "recommended_next_lane": diagnosis["recommended_next_lane"],
                }
            )

        if any(
            item["runtime_status"] == "fail"
            and item["failure_category"] == CATEGORY_INSUFFICIENT_EVIDENCE
            for item in diagnoses
        ):
            status = STATUS_INSUFFICIENT
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError, yaml.YAMLError) as exc:
        status = STATUS_INSUFFICIENT
        diagnoses = [
            {
                "scenario_id": "GLOBAL_PREREQUISITE_GATE",
                "runtime_status": "fail",
                "observed_runtime_output": "Diagnosis did not run because prerequisite gating failed.",
                "expected_contract_behavior": "v1.4.4 requires the trusted v1.4.3 runtime package and empty wrapper failure review before diagnosis.",
                "failure_category": CATEGORY_INSUFFICIENT_EVIDENCE,
                "evidence_summary": str(exc),
                "recommended_next_lane": LANE_NO_ACTION,
            }
        ]

    overall_lanes = sorted(
        {
            item["recommended_next_lane"]
            for item in diagnoses
            if item["recommended_next_lane"] != PASS_NEXT_LANE
        }
    )

    write_diagnosis_report(
        output_path=diagnosis_report_path,
        status=status,
        diagnoses=diagnoses,
        source_artifacts=source_artifacts,
    )
    write_matrix_report(matrix_report_path, diagnoses)
    write_decision_report(
        output_path=decision_report_path,
        status=status,
        diagnoses=diagnoses,
    )

    json_report_path.parent.mkdir(parents=True, exist_ok=True)
    json_report_path.write_text(
        json.dumps(
            {
                "milestone": "LV7 v1.4.4",
                "status": status,
                "accepted_checkpoint": ACCEPTED_CHECKPOINT,
                "evidence_only_adapters": list(EVIDENCE_ONLY_SFT_ADAPTERS),
                "parked_dpo_adapters": list(PARKED_DPO_ADAPTERS),
                "source_artifacts": source_artifacts,
                "overall_recommended_lanes": overall_lanes,
                "scenarios": diagnoses,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "status": status,
        "scenario_count": len(diagnoses),
        "failed_scenarios": sum(1 for item in diagnoses if item["runtime_status"] == "fail"),
        "overall_recommended_lanes": overall_lanes,
        "accepted_checkpoint": ACCEPTED_CHECKPOINT,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose trusted v1.4 runtime model failures scenario by scenario."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_4_4_runtime_model_failure_diagnosis()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
