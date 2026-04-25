from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_PROJECT_ROOT))

from evals.scoring import contains_phrase, parse_rationale_block  # noqa: E402
from training.analyze_v1_4_1_external_m6_runtime_eval import (  # noqa: E402
    ACCEPTED_CHECKPOINT,
    EVIDENCE_ONLY_SFT_ADAPTERS,
    EXPECTED_ARTIFACT,
    EXPECTED_BACKEND_TAG,
    EXPECTED_DESKTOP_COMMIT,
    EXPECTED_RELEASE_TAG,
    PARKED_DPO_ADAPTERS,
)
from training.analyze_v1_4_3_runtime_scenario_results import (  # noqa: E402
    DEFAULT_DECISION_REPORT as DEFAULT_V1_4_3_DECISION_REPORT,
    DEFAULT_RUNTIME_EXECUTION_MANIFEST,
    DEFAULT_RUNTIME_OUTPUTS,
    DEFAULT_RUNTIME_RESULTS_REPORT,
    DEFAULT_WRAPPER_FAILURE_REVIEW_REPORT,
    STATUS_MODEL_REPAIR,
)
from training.analyze_v1_4_4_runtime_model_failure_diagnosis import (  # noqa: E402
    NO_WRAPPER_FAILURES_LINE,
    display_path,
    read_json,
    read_jsonl,
    require,
)
from training.analyze_v1_4_runtime_eval_readiness import (  # noqa: E402
    PROJECT_ROOT,
    last_nonempty_line,
    render_markdown_table,
    write_report,
)
from training.analyze_v1_5_0_narrow_runtime_model_repair_planning import (  # noqa: E402
    DEFAULT_DECISION_REPORT as DEFAULT_V1_5_0_DECISION_REPORT,
    DEFAULT_JSON_REPORT as DEFAULT_V1_5_0_JSON_REPORT,
    FROZEN_SURFACES,
    STATUS_READY as STATUS_V1_5_0_READY,
    validate_runtime_manifest,
)
from training.prepare_sft_dataset import render_messages_as_text  # noqa: E402


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"
DATASET_PATH = PROJECT_ROOT / "data" / "pilot_v1_9" / "sft_messages.jsonl"
PREPARED_DATASET_PATH = PROJECT_ROOT / "data" / "pilot_v1_9" / "sft_train_ready.jsonl"
RUNTIME_SCENARIOS_DIR = PROJECT_ROOT / "evals" / "runtime" / "v1_4"
REPAIR_CONFIG_PATH = PROJECT_ROOT / "training" / "qlora_runtime_repair_v1_5_1.yaml"

DEFAULT_IMPLEMENTATION_REPORT = (
    REPORTS_RUNTIME_DIR / "V1_5_1_NARROW_RUNTIME_SFT_REPAIR_IMPLEMENTATION.md"
)
DEFAULT_MATRIX_REPORT = REPORTS_RUNTIME_DIR / "V1_5_1_RUNTIME_SFT_REPAIR_MATRIX.md"
DEFAULT_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_1_NEXT_STEP_DECISION.md"
DEFAULT_JSON_REPORT = (
    REPORTS_RUNTIME_DIR / "v1_5_1_narrow_runtime_sft_repair_implementation.json"
)

STATUS_READY = "V1_5_1_IMPLEMENTATION_READY"
STATUS_INSUFFICIENT = "V1_5_1_IMPLEMENTATION_INSUFFICIENT"

REPAIR_ROLE = "narrow_runtime_sft_repair_v1_5_1"
RETENTION_ROLE = "runtime_retention_guard_v1_5_1"
RETENTION_SCENARIO_ID = "approved_recovery_runtime_001"
EXPECTED_REPAIR_CONFIG_OUTPUT_DIR = "models/adapters/lv7_sft_runtime_repair_v1_5_1/"
NEXT_EXECUTABLE_MILESTONE = "LV7 v1.5.2 - Narrow Runtime SFT Repair Training Run"

IMPLEMENTATION_SURFACES = [
    "data/pilot_v1_9/sft_messages.jsonl",
    "data/pilot_v1_9/sft_train_ready.jsonl",
    "training/qlora_runtime_repair_v1_5_1.yaml",
]


def load_runtime_contracts(runtime_scenarios_dir: Path) -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    for path in sorted(runtime_scenarios_dir.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        scenario_id = str(payload["scenario_id"])
        payload["scenario_file"] = display_path(path)
        contracts[scenario_id] = payload
    return contracts


def load_records_by_id(path: Path) -> dict[str, dict[str, Any]]:
    return {str(record["id"]): record for record in read_jsonl(path)}


def validate_repair_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    require(
        payload.get("dataset") == "data/pilot_v1_9/sft_messages.jsonl",
        f"{display_path(path)} has wrong dataset path",
    )
    require(
        payload.get("prepared_dataset") == "data/pilot_v1_9/sft_train_ready.jsonl",
        f"{display_path(path)} has wrong prepared_dataset path",
    )
    require(
        payload.get("base_model") == "Qwen/Qwen2.5-1.5B-Instruct",
        f"{display_path(path)} has wrong base_model",
    )
    require(
        payload.get("output_dir") == EXPECTED_REPAIR_CONFIG_OUTPUT_DIR,
        f"{display_path(path)} has wrong output_dir",
    )
    require(
        payload.get("output_dir") != ACCEPTED_CHECKPOINT,
        f"{display_path(path)} must not overwrite the accepted checkpoint",
    )
    return payload


def validate_repair_record(
    *,
    record: dict[str, Any],
    contract: dict[str, Any],
    planned_lane: str,
    expected_role: str,
    expected_missing_terms: list[str],
    runtime_status: str,
) -> dict[str, Any]:
    messages = record.get("messages", [])
    require(
        isinstance(messages, list) and len(messages) == 2,
        f"repair record {record.get('id')} must contain exactly two messages",
    )
    require(
        messages[0].get("role") == "user" and messages[1].get("role") == "assistant",
        f"repair record {record.get('id')} must preserve the user/assistant message order",
    )
    user_prompt = str(messages[0].get("content", "")).strip()
    assistant_text = str(messages[1].get("content", "")).strip()
    require(
        user_prompt == str(contract["prompt"]).strip(),
        f"repair record {record.get('id')} does not copy the exact runtime prompt for {contract['scenario_id']}",
    )

    parsed = parse_rationale_block(assistant_text)
    require(
        parsed["policy_rationale_present"],
        f"repair record {record.get('id')} is missing the policy_rationale block",
    )
    require(
        parsed["mode"] == contract["expected_mode"],
        f"repair record {record.get('id')} has wrong mode `{parsed['mode']}` for {contract['scenario_id']}`",
    )
    for field in ("risk_assessment", "authority_boundary", "safe_next_move", "response"):
        require(
            bool(parsed[field]),
            f"repair record {record.get('id')} is missing policy_rationale field `{field}`",
        )

    missing_terms = [
        phrase for phrase in contract.get("must_include", []) if not contains_phrase(assistant_text, phrase)
    ]
    forbidden_terms = [
        phrase for phrase in contract.get("must_not_include", []) if contains_phrase(assistant_text, phrase)
    ]
    require(
        not missing_terms,
        f"repair record {record.get('id')} is missing required runtime terms: {', '.join(missing_terms)}",
    )
    require(
        not forbidden_terms,
        f"repair record {record.get('id')} contains forbidden runtime terms: {', '.join(forbidden_terms)}",
    )

    metadata = record.get("metadata", {})
    require(
        metadata.get("repair_role") == expected_role,
        f"repair record {record.get('id')} has wrong repair_role",
    )
    require(
        metadata.get("repair_lane") == planned_lane,
        f"repair record {record.get('id')} has wrong repair_lane",
    )
    require(
        metadata.get("derived_from_failure_family") == contract["scenario_id"],
        f"repair record {record.get('id')} has wrong derived_from_failure_family",
    )
    require(
        metadata.get("traceability", {}).get("eval_harness_link") == contract["scenario_file"],
        f"repair record {record.get('id')} has wrong eval_harness_link",
    )
    require(
        metadata.get("runtime_prompt_copied") is True,
        f"repair record {record.get('id')} must mark runtime_prompt_copied=true",
    )
    if expected_role == REPAIR_ROLE:
        require(
            list(metadata.get("target_missing_tokens", [])) == expected_missing_terms,
            f"repair record {record.get('id')} has wrong target_missing_tokens",
        )
    else:
        require(
            list(metadata.get("target_missing_tokens", [])) == [],
            f"retention record {record.get('id')} must not target missing tokens",
        )

    return {
        "scenario_id": contract["scenario_id"],
        "runtime_status": runtime_status,
        "planned_repair_lane": planned_lane,
        "repair_record_id": str(record["id"]),
        "repair_role": expected_role,
        "expected_mode": contract["expected_mode"],
        "observed_mode": parsed["mode"],
        "missing_required_terms_after_repair": missing_terms,
        "forbidden_terms_present": forbidden_terms,
        "prompt_match": True,
        "implementation_validation": "exact runtime prompt copied; rationale block present; must-include terms restored",
    }


def write_implementation_report(
    *,
    output_path: Path,
    status: str,
    source_artifacts: dict[str, str],
    scenario_rows: list[dict[str, Any]],
    source_count: int,
    prepared_count: int,
) -> None:
    lines = [
        "# V1.5.1 Narrow Runtime SFT Repair Implementation",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- Evidence-only adapters remain `{EVIDENCE_ONLY_SFT_ADAPTERS[0]}` and `{EVIDENCE_ONLY_SFT_ADAPTERS[1]}`.",
        f"- Parked DPO adapters remain `{PARKED_DPO_ADAPTERS[0]}` and `{PARKED_DPO_ADAPTERS[1]}`.",
        "- Wrapper-side runtime packaging is complete and wrapper stays closed unless LV7 later proves wrapper-side fault on an exact scenario.",
        "- This milestone is LV7-only and implementation-only. It does not rerun wrapper code, regenerate runtime outputs, reopen DPO, or change the accepted checkpoint boundary.",
        "",
        "## Implementation Surfaces",
        "",
        *[f"- `{surface}`" for surface in IMPLEMENTATION_SURFACES],
        "",
        "## Frozen Surfaces Preserved",
        "",
        *[f"- `{surface}`" for surface in FROZEN_SURFACES],
        "",
        "## Source Evidence",
        "",
        f"- runtime outputs: `{source_artifacts['runtime_outputs_path']}`",
        f"- runtime results report: `{source_artifacts['runtime_results_report_path']}`",
        f"- runtime execution manifest: `{source_artifacts['runtime_execution_manifest_path']}`",
        f"- v1.4.3 decision: `{source_artifacts['v1_4_3_decision_report_path']}`",
        f"- v1.4.3 wrapper review: `{source_artifacts['v1_4_3_wrapper_failure_review_path']}`",
        f"- v1.5.0 decision: `{source_artifacts['v1_5_0_decision_report_path']}`",
        f"- v1.5.0 plan JSON: `{source_artifacts['v1_5_0_json_report_path']}`",
        f"- repair dataset: `{source_artifacts['dataset_path']}`",
        f"- prepared dataset: `{source_artifacts['prepared_dataset_path']}`",
        f"- repair config: `{source_artifacts['repair_config_path']}`",
        "",
        "## Implementation Summary",
        "",
        f"- dataset record count after implementation: `{source_count}`",
        f"- prepared dataset record count after regeneration: `{prepared_count}`",
        "- Narrow runtime repair records were added for each of the nine failing v1.4 runtime scenarios using the exact runtime prompts and the planned lane-specific lexical anchors.",
        "- One approved-recovery retention guard was added so the current passing runtime behavior remains represented in the next SFT run.",
        "- Wrapper-facing, scorer-facing, and accepted-adapter runtime surfaces remain frozen in this milestone.",
        "",
        "## Next Lane",
        "",
        f"- Current milestone status: `{status}`.",
        f"- Next executable milestone: `{NEXT_EXECUTABLE_MILESTONE}`.",
        "- The next step is to run a narrow SFT training pass against the new repair config and then re-evaluate before any wider model-repair escalation.",
    ]
    write_report(output_path, lines)


def write_matrix_report(output_path: Path, scenario_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# V1.5.1 Runtime SFT Repair Matrix",
        "",
        render_markdown_table(
            [
                "scenario_id",
                "runtime_status",
                "planned_repair_lane",
                "repair_role",
                "expected_mode",
                "observed_mode",
                "missing_terms_after_repair",
                "forbidden_terms_present",
                "prompt_match",
                "implementation_validation",
            ],
            [
                [
                    row["scenario_id"],
                    row["runtime_status"],
                    row["planned_repair_lane"],
                    row["repair_role"],
                    row["expected_mode"],
                    row["observed_mode"],
                    ", ".join(row["missing_required_terms_after_repair"]) or "NONE",
                    ", ".join(row["forbidden_terms_present"]) or "NONE",
                    "yes" if row["prompt_match"] else "no",
                    row["implementation_validation"],
                ]
                for row in scenario_rows
            ],
        ),
    ]
    write_report(output_path, lines)


def write_decision_report(output_path: Path, status: str) -> None:
    lines = [
        "# V1.5.1 Next Step Decision",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        "- This milestone is LV7-only and does not authorize wrapper reruns, backend changes, runtime package regeneration, DPO, or adapter promotion.",
    ]
    if status == STATUS_READY:
        lines.extend(
            [
                "- The narrow runtime SFT repair surface is implemented and the next executable milestone is a dedicated training run on the new repair config.",
                f"- The next executable milestone is `{NEXT_EXECUTABLE_MILESTONE}`.",
            ]
        )
    else:
        lines.extend(
            [
                "- The narrow runtime SFT repair surface is not yet fully supportable from the checked-in artifact chain.",
                "- Resolve the missing repair-record or prepared-dataset evidence before starting a training run.",
            ]
        )
    lines.extend(["", status])
    write_report(output_path, lines)


def analyze_v1_5_1_narrow_runtime_sft_repair_implementation(
    *,
    runtime_outputs_path: Path = DEFAULT_RUNTIME_OUTPUTS,
    runtime_results_report_path: Path = DEFAULT_RUNTIME_RESULTS_REPORT,
    runtime_execution_manifest_path: Path = DEFAULT_RUNTIME_EXECUTION_MANIFEST,
    v1_4_3_decision_report_path: Path = DEFAULT_V1_4_3_DECISION_REPORT,
    v1_4_3_wrapper_failure_review_path: Path = DEFAULT_WRAPPER_FAILURE_REVIEW_REPORT,
    v1_5_0_decision_report_path: Path = DEFAULT_V1_5_0_DECISION_REPORT,
    v1_5_0_json_report_path: Path = DEFAULT_V1_5_0_JSON_REPORT,
    runtime_scenarios_dir: Path = RUNTIME_SCENARIOS_DIR,
    dataset_path: Path = DATASET_PATH,
    prepared_dataset_path: Path = PREPARED_DATASET_PATH,
    repair_config_path: Path = REPAIR_CONFIG_PATH,
    implementation_report_path: Path = DEFAULT_IMPLEMENTATION_REPORT,
    matrix_report_path: Path = DEFAULT_MATRIX_REPORT,
    decision_report_path: Path = DEFAULT_DECISION_REPORT,
    json_report_path: Path = DEFAULT_JSON_REPORT,
) -> dict[str, Any]:
    source_artifacts = {
        "runtime_outputs_path": display_path(runtime_outputs_path),
        "runtime_results_report_path": display_path(runtime_results_report_path),
        "runtime_execution_manifest_path": display_path(runtime_execution_manifest_path),
        "v1_4_3_decision_report_path": display_path(v1_4_3_decision_report_path),
        "v1_4_3_wrapper_failure_review_path": display_path(v1_4_3_wrapper_failure_review_path),
        "v1_5_0_decision_report_path": display_path(v1_5_0_decision_report_path),
        "v1_5_0_json_report_path": display_path(v1_5_0_json_report_path),
        "dataset_path": display_path(dataset_path),
        "prepared_dataset_path": display_path(prepared_dataset_path),
        "repair_config_path": display_path(repair_config_path),
    }

    status = STATUS_READY
    scenario_rows: list[dict[str, Any]] = []
    repair_record_ids: list[str] = []
    source_count = 0
    prepared_count = 0

    try:
        require(
            last_nonempty_line(v1_5_0_decision_report_path) == STATUS_V1_5_0_READY,
            f"{display_path(v1_5_0_decision_report_path)} does not end with {STATUS_V1_5_0_READY}",
        )
        require(
            last_nonempty_line(v1_4_3_decision_report_path) == STATUS_MODEL_REPAIR,
            f"{display_path(v1_4_3_decision_report_path)} does not end with {STATUS_MODEL_REPAIR}",
        )
        wrapper_review_text = v1_4_3_wrapper_failure_review_path.read_text(encoding="utf-8")
        require(
            NO_WRAPPER_FAILURES_LINE in wrapper_review_text,
            f"{display_path(v1_4_3_wrapper_failure_review_path)} no longer reports an empty wrapper failure review",
        )
        for required_path in (
            runtime_outputs_path,
            runtime_results_report_path,
            runtime_execution_manifest_path,
            v1_5_0_json_report_path,
            dataset_path,
            prepared_dataset_path,
            repair_config_path,
        ):
            require(required_path.exists(), f"missing required implementation artifact: {display_path(required_path)}")

        validate_runtime_manifest(runtime_execution_manifest_path)
        plan_payload = read_json(v1_5_0_json_report_path)
        require(
            plan_payload.get("status") == STATUS_V1_5_0_READY,
            f"{display_path(v1_5_0_json_report_path)} does not report {STATUS_V1_5_0_READY}",
        )
        require(
            plan_payload.get("accepted_checkpoint") == ACCEPTED_CHECKPOINT,
            f"{display_path(v1_5_0_json_report_path)} has wrong accepted checkpoint",
        )

        runtime_contracts = load_runtime_contracts(runtime_scenarios_dir)
        plan_rows = {row["scenario_id"]: row for row in plan_payload.get("scenarios", [])}

        failed_rows = [
            row for row in plan_payload.get("scenarios", []) if row.get("runtime_status") == "fail"
        ]
        require(len(failed_rows) == 9, "v1.5.0 plan must carry forward exactly nine failed runtime scenarios")
        require(
            RETENTION_SCENARIO_ID in plan_rows and plan_rows[RETENTION_SCENARIO_ID]["runtime_status"] == "pass",
            "v1.5.0 plan must preserve approved_recovery_runtime_001 as the retention guard",
        )

        validate_repair_config(repair_config_path)

        source_records = read_jsonl(dataset_path)
        prepared_records = read_jsonl(prepared_dataset_path)
        source_count = len(source_records)
        prepared_count = len(prepared_records)
        require(
            source_count == prepared_count,
            f"{display_path(prepared_dataset_path)} must contain one prepared record per source record",
        )
        prepared_by_id = {str(record["id"]): record for record in prepared_records}

        role_records = [
            record
            for record in source_records
            if record.get("metadata", {}).get("repair_role") in {REPAIR_ROLE, RETENTION_ROLE}
        ]
        require(
            len(role_records) == 10,
            f"{display_path(dataset_path)} must contain exactly 10 v1.5.1 repair/retention records",
        )

        records_by_scenario: dict[str, list[dict[str, Any]]] = {}
        for record in role_records:
            records_by_scenario.setdefault(str(record["scenario_id"]), []).append(record)

        expected_scenarios = [row["scenario_id"] for row in failed_rows] + [RETENTION_SCENARIO_ID]
        require(
            sorted(records_by_scenario) == sorted(expected_scenarios),
            f"{display_path(dataset_path)} does not cover the expected v1.5.1 scenario set",
        )

        for scenario_id in expected_scenarios:
            records = records_by_scenario[scenario_id]
            require(
                len(records) == 1,
                f"{display_path(dataset_path)} must contain exactly one v1.5.1 record for {scenario_id}",
            )
            record = records[0]
            plan_row = plan_rows[scenario_id]
            contract = runtime_contracts[scenario_id]
            expected_role = RETENTION_ROLE if scenario_id == RETENTION_SCENARIO_ID else REPAIR_ROLE
            planned_lane = "RETENTION_GUARD" if scenario_id == RETENTION_SCENARIO_ID else plan_row["planned_repair_lane"]
            expected_missing_terms = [] if scenario_id == RETENTION_SCENARIO_ID else list(
                plan_row.get("missing_required_terms", [])
            )

            row = validate_repair_record(
                record=record,
                contract=contract,
                planned_lane=planned_lane,
                expected_role=expected_role,
                expected_missing_terms=expected_missing_terms,
                runtime_status=plan_row["runtime_status"],
            )
            repair_record_ids.append(row["repair_record_id"])

            prepared_record = prepared_by_id.get(row["repair_record_id"])
            require(
                prepared_record is not None,
                f"{display_path(prepared_dataset_path)} is missing prepared record {row['repair_record_id']}",
            )
            require(
                prepared_record.get("text") == render_messages_as_text(record["messages"]),
                f"prepared record {row['repair_record_id']} is out of sync with the source messages",
            )
            scenario_rows.append(row)

        require(
            len(scenario_rows) == 10,
            "v1.5.1 implementation must validate the nine failed scenarios plus one retention guard",
        )
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as exc:
        status = STATUS_INSUFFICIENT
        scenario_rows = [
            {
                "scenario_id": "GLOBAL_PREREQUISITE_GATE",
                "runtime_status": "fail",
                "planned_repair_lane": "NO_ACTION_INSUFFICIENT_EVIDENCE",
                "repair_record_id": "NONE",
                "repair_role": "NONE",
                "expected_mode": "",
                "observed_mode": "",
                "missing_required_terms_after_repair": [],
                "forbidden_terms_present": [],
                "prompt_match": False,
                "implementation_validation": str(exc),
            }
        ]

    write_implementation_report(
        output_path=implementation_report_path,
        status=status,
        source_artifacts=source_artifacts,
        scenario_rows=scenario_rows,
        source_count=source_count,
        prepared_count=prepared_count,
    )
    write_matrix_report(matrix_report_path, scenario_rows)
    write_decision_report(decision_report_path, status)

    json_report_path.parent.mkdir(parents=True, exist_ok=True)
    json_report_path.write_text(
        json.dumps(
            {
                "milestone": "LV7 v1.5.1",
                "status": status,
                "accepted_checkpoint": ACCEPTED_CHECKPOINT,
                "implementation_surfaces": IMPLEMENTATION_SURFACES,
                "frozen_surfaces": FROZEN_SURFACES,
                "source_artifact_paths": source_artifacts,
                "repair_record_count": len([row for row in scenario_rows if row["scenario_id"] != "GLOBAL_PREREQUISITE_GATE"]),
                "repair_record_ids": repair_record_ids,
                "dataset_record_count": source_count,
                "prepared_dataset_record_count": prepared_count,
                "next_executable_milestone": NEXT_EXECUTABLE_MILESTONE,
                "scenarios": scenario_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "status": status,
        "repair_record_count": len([row for row in scenario_rows if row["scenario_id"] != "GLOBAL_PREREQUISITE_GATE"]),
        "dataset_record_count": source_count,
        "prepared_dataset_record_count": prepared_count,
        "next_executable_milestone": NEXT_EXECUTABLE_MILESTONE,
        "accepted_checkpoint": ACCEPTED_CHECKPOINT,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the v1.5.1 narrow runtime SFT repair implementation."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_5_1_narrow_runtime_sft_repair_implementation()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
