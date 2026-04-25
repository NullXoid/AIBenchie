from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
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
    require,
)
from training.analyze_v1_4_8_mode_selection_contract_implementation import (  # noqa: E402
    DEFAULT_DECISION_REPORT as DEFAULT_V1_4_8_DECISION_REPORT,
    STATUS_READY as STATUS_V1_4_8_READY,
)
from training.analyze_v1_4_9_runtime_model_repair_investigation import (  # noqa: E402
    CATEGORY_BOUNDARY_ENFORCEMENT,
    CATEGORY_EXECUTE_PATH,
    CATEGORY_MODE_RETENTION,
    DEFAULT_DECISION_REPORT as DEFAULT_V1_4_9_DECISION_REPORT,
    DEFAULT_JSON_REPORT as DEFAULT_V1_4_9_JSON_REPORT,
    LANE_BOUNDARY_ENFORCEMENT,
    LANE_EXECUTE_PATH,
    LANE_MODE_RETENTION,
    STATUS_READY as STATUS_V1_4_9_READY,
)
from training.analyze_v1_4_runtime_eval_readiness import (  # noqa: E402
    PROJECT_ROOT,
    last_nonempty_line,
    render_markdown_table,
    write_report,
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"
REPORTS_TRAINING_DIR = PROJECT_ROOT / "reports" / "training"

ADAPTER_REFERENCE_PATH = PROJECT_ROOT / "evals" / "adapters.py"
SCORING_REFERENCE_PATH = PROJECT_ROOT / "evals" / "scoring.py"
SFT_CONFIG_PATH = PROJECT_ROOT / "training" / "qlora_smoke_config.yaml"
PREPARE_DATASET_PATH = PROJECT_ROOT / "training" / "prepare_sft_dataset.py"
FREEZE_MANIFEST_PATH = REPORTS_TRAINING_DIR / "v1_0_5_artifact_manifest.json"
FREEZE_MARKDOWN_PATH = REPORTS_TRAINING_DIR / "V1_0_5_FREEZE.md"

DEFAULT_PLAN_REPORT = REPORTS_RUNTIME_DIR / "V1_5_0_NARROW_RUNTIME_MODEL_REPAIR_PLAN.md"
DEFAULT_MATRIX_REPORT = REPORTS_RUNTIME_DIR / "V1_5_0_REPAIR_LANE_MATRIX.md"
DEFAULT_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_0_NEXT_STEP_DECISION.md"
DEFAULT_JSON_REPORT = (
    REPORTS_RUNTIME_DIR / "v1_5_0_narrow_runtime_model_repair_plan.json"
)

STATUS_READY = "V1_5_0_REPAIR_PLAN_READY"
STATUS_INSUFFICIENT = "V1_5_0_REPAIR_PLAN_INSUFFICIENT"

NEXT_EXECUTABLE_MILESTONE = "LV7 v1.5.1 - Narrow Runtime SFT Repair Implementation"

FROZEN_SURFACES = [
    "models/adapters/lv7_sft_smoke_v1_0_5/chat_template.jinja",
    "evals/scoring.py",
    "reports/runtime/v1_4_runtime_outputs.jsonl",
    "reports/runtime/V1_4_RUNTIME_EVAL_RESULTS.md",
    "reports/runtime/v1_4_runtime_execution_manifest.json",
]

REPAIR_IMPLEMENTATION_SURFACES = [
    "data/pilot_v1_9/sft_messages.jsonl",
    "data/pilot_v1_9/sft_train_ready.jsonl",
    "training/prepare_sft_dataset.py",
    "training/qlora_smoke_config.yaml",
]

NONE_CATEGORY = "NONE"
NONE_LANE = "NONE"

LANE_PLAN_TEMPLATES: dict[str, dict[str, Any]] = {
    LANE_MODE_RETENTION: {
        "primary_categories": [CATEGORY_MODE_RETENTION],
        "repair_objective": (
            "Recover stable mode selection on the accepted checkpoint for clarify and fallback scenarios while preserving visible policy_rationale and avoiding generic search/clarify detours."
        ),
        "required_response_targets": [
            "emit the expected LV7 mode token explicitly",
            "retain visible policy_rationale fields on the final output",
            "keep clarify outputs read-only and choice-seeking",
            "keep fallback outputs sanitized with no partial execution leakage",
        ],
        "recommended_implementation_surfaces": REPAIR_IMPLEMENTATION_SURFACES,
        "frozen_surfaces": FROZEN_SURFACES,
        "requires_wrapper_reentry": False,
        "requires_dpo": False,
        "requires_scorer_change": False,
        "requires_template_change": False,
        "implementation_owner": "LV7",
        "non_goals": [
            "wrapper rerun",
            "backend change",
            "DPO reopen",
            "adapter promotion",
        ],
    },
    LANE_EXECUTE_PATH: {
        "primary_categories": [CATEGORY_EXECUTE_PATH],
        "repair_objective": (
            "Recover bounded execute-path behavior for low-risk read-only and test-run scenarios using the typed tool gateway contract instead of generic refusal or generic task-start text."
        ),
        "required_response_targets": [
            "retain execute mode with visible policy_rationale",
            "state low-risk, bounded, read-only or test-run scope correctly",
            "reference the required typed scopes directly",
            "return a bounded summary instead of generic placeholder text",
        ],
        "recommended_implementation_surfaces": REPAIR_IMPLEMENTATION_SURFACES,
        "frozen_surfaces": FROZEN_SURFACES,
        "requires_wrapper_reentry": False,
        "requires_dpo": False,
        "requires_scorer_change": False,
        "requires_template_change": False,
        "implementation_owner": "LV7",
        "non_goals": [
            "wrapper rerun",
            "backend change",
            "runtime schema change",
            "DPO reopen",
        ],
    },
    LANE_BOUNDARY_ENFORCEMENT: {
        "primary_categories": [CATEGORY_BOUNDARY_ENFORCEMENT],
        "repair_objective": (
            "Recover challenge, halt, and escalate boundary enforcement so the accepted checkpoint refuses unsafe shortcuts, honors shutdown, preserves audit, requires approved lease, and avoids hidden persistence."
        ),
        "required_response_targets": [
            "retain the expected challenge, halt, or escalate mode explicitly",
            "keep visible policy_rationale with concrete risk, authority, and safe-next-step fields",
            "name the required boundary term(s) from the scenario contract",
            "avoid generic clarify/search detours when the boundary decision is already known",
        ],
        "recommended_implementation_surfaces": REPAIR_IMPLEMENTATION_SURFACES,
        "frozen_surfaces": FROZEN_SURFACES,
        "requires_wrapper_reentry": False,
        "requires_dpo": False,
        "requires_scorer_change": False,
        "requires_template_change": False,
        "implementation_owner": "LV7",
        "non_goals": [
            "wrapper rerun",
            "backend change",
            "DPO reopen",
            "relaxing the runtime suite or scorer to accept unsafe behavior",
        ],
    },
}

SHARED_CONSTRAINTS = [
    "accepted checkpoint remains models/adapters/lv7_sft_smoke_v1_0_5/",
    "wrapper/backend remain closed unless exact wrapper fault evidence is produced",
    "runtime package schema and backend identity policy remain unchanged",
    "policy_rationale remains model output and nullxoid_signal remains controller metadata",
    "chat_template.jinja and evals/scoring.py stay frozen during the next model-repair implementation unless a later milestone explicitly reopens them",
    "DPO remains parked",
]


def summarize_missing_terms(rows: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for term in row.get("missing_required_terms", []):
            if term not in seen:
                seen.add(term)
                ordered.append(term)
    return ordered


def summarize_markers(rows: list[dict[str, Any]]) -> list[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        for marker in row.get("cross_cutting_markers", []):
            counts[str(marker)] += 1
    return [
        marker
        for marker, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def validate_runtime_manifest(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    require(
        payload.get("model_adapter_path") == ACCEPTED_CHECKPOINT,
        f"{display_path(path)} has wrong model_adapter_path",
    )
    require(
        payload.get("wrapper_artifact") == EXPECTED_ARTIFACT,
        f"{display_path(path)} has wrong wrapper_artifact",
    )
    require(
        payload.get("release_tag") == EXPECTED_RELEASE_TAG,
        f"{display_path(path)} has wrong release_tag",
    )
    require(
        payload.get("desktop_commit") == EXPECTED_DESKTOP_COMMIT,
        f"{display_path(path)} has wrong desktop_commit",
    )
    require(
        payload.get("backend_tag") == EXPECTED_BACKEND_TAG,
        f"{display_path(path)} has wrong backend_tag",
    )
    return payload


def build_lane_entry(
    lane_id: str,
    scenario_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    template = LANE_PLAN_TEMPLATES[lane_id]
    scenario_ids = [row["scenario_id"] for row in scenario_rows]
    expected_modes = sorted({row["expected_mode"] for row in scenario_rows})
    missing_terms = summarize_missing_terms(scenario_rows)
    markers = summarize_markers(scenario_rows)
    return {
        "lane_id": lane_id,
        "targeted_scenarios": scenario_ids,
        "targeted_expected_modes": expected_modes,
        "primary_categories": list(template["primary_categories"]),
        "repair_objective": template["repair_objective"],
        "required_response_targets": list(template["required_response_targets"]),
        "shared_missing_required_terms": missing_terms,
        "cross_cutting_markers": markers,
        "recommended_implementation_surfaces": list(
            template["recommended_implementation_surfaces"]
        ),
        "frozen_surfaces": list(template["frozen_surfaces"]),
        "requires_wrapper_reentry": template["requires_wrapper_reentry"],
        "requires_dpo": template["requires_dpo"],
        "requires_scorer_change": template["requires_scorer_change"],
        "requires_template_change": template["requires_template_change"],
        "implementation_owner": template["implementation_owner"],
        "non_goals": list(template["non_goals"]),
    }


def write_plan_report(
    *,
    output_path: Path,
    status: str,
    source_artifacts: dict[str, str],
    lane_entries: list[dict[str, Any]],
    scenario_rows: list[dict[str, Any]],
) -> None:
    failed_rows = [row for row in scenario_rows if row["runtime_status"] == "fail"]
    lane_table_rows = [
        [
            lane["lane_id"],
            ", ".join(lane["targeted_scenarios"]),
            ", ".join(lane["targeted_expected_modes"]),
            lane["repair_objective"],
        ]
        for lane in lane_entries
    ] or [["NONE", "NONE", "NONE", "NONE"]]

    shared_marker_counts = Counter()
    for row in failed_rows:
        for marker in row["cross_cutting_markers"]:
            shared_marker_counts[str(marker)] += 1
    shared_marker_rows = [
        [marker, str(shared_marker_counts[marker])]
        for marker in sorted(shared_marker_counts)
    ] or [["NONE", "0"]]

    lines = [
        "# V1.5.0 Narrow Runtime Model Repair Plan",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- Evidence-only adapters remain `{EVIDENCE_ONLY_SFT_ADAPTERS[0]}` and `{EVIDENCE_ONLY_SFT_ADAPTERS[1]}`.",
        f"- Parked DPO adapters remain `{PARKED_DPO_ADAPTERS[0]}` and `{PARKED_DPO_ADAPTERS[1]}`.",
        "- Wrapper-side runtime packaging is complete and wrapper stays closed unless LV7 later proves wrapper-side fault on an exact scenario.",
        "- This milestone is LV7-only and planning-only. It does not rerun wrapper code, regenerate runtime outputs, reopen DPO, or promote adapters.",
        "",
        "## Source Evidence",
        "",
        f"- runtime outputs: `{source_artifacts['runtime_outputs_path']}`",
        f"- runtime results report: `{source_artifacts['runtime_results_report_path']}`",
        f"- runtime execution manifest: `{source_artifacts['runtime_execution_manifest_path']}`",
        f"- v1.4.3 decision: `{source_artifacts['v1_4_3_decision_report_path']}`",
        f"- v1.4.3 wrapper review: `{source_artifacts['v1_4_3_wrapper_failure_review_path']}`",
        f"- v1.4.8 decision: `{source_artifacts['v1_4_8_decision_report_path']}`",
        f"- v1.4.9 decision: `{source_artifacts['v1_4_9_decision_report_path']}`",
        f"- v1.4.9 JSON report: `{source_artifacts['v1_4_9_json_report_path']}`",
        f"- adapter reference: `{source_artifacts['adapters_reference_path']}`",
        f"- scoring reference: `{source_artifacts['scoring_reference_path']}`",
        f"- SFT config: `{source_artifacts['sft_config_path']}`",
        f"- dataset prep script: `{source_artifacts['prepare_dataset_path']}`",
        f"- freeze manifest: `{source_artifacts['freeze_manifest_path']}`",
        f"- freeze markdown: `{source_artifacts['freeze_markdown_path']}`",
        "",
        "## Planning Summary",
        "",
        f"- failed scenarios carried into planning: `{len(failed_rows)}`",
        f"- repair lanes: `{len(lane_entries)}`",
        f"- milestone status: `{status}`",
        f"- next executable milestone: `{NEXT_EXECUTABLE_MILESTONE}`",
        "",
        "## Lane Overview",
        "",
        render_markdown_table(
            ["repair_lane", "targeted_scenarios", "expected_modes", "repair_objective"],
            lane_table_rows,
        ),
        "",
        "## Shared Frozen Surfaces",
        "",
        *[f"- `{surface}`" for surface in FROZEN_SURFACES],
        "",
        "## Shared Constraints",
        "",
        *[f"- {constraint}" for constraint in SHARED_CONSTRAINTS],
        "",
        "## Cross-Cutting Markers From Refreshed Runtime Evidence",
        "",
        render_markdown_table(
            ["cross_cutting_marker", "count"],
            shared_marker_rows,
        ),
        "",
        "## Current Interpretation",
        "",
        "- The refreshed runtime package still shows no trusted wrapper/runtime failures.",
        "- The next honest step is a narrow LV7-owned model repair implementation against the accepted checkpoint lineage.",
        "- The plan intentionally freezes wrapper-facing and scorer-facing surfaces so the next milestone isolates model-repair effects.",
    ]
    write_report(output_path, lines)


def write_matrix_report(output_path: Path, scenario_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# V1.5.0 Repair Lane Matrix",
        "",
        render_markdown_table(
            [
                "scenario_id",
                "runtime_status",
                "primary_failure_category",
                "planned_repair_lane",
                "expected_mode",
                "missing_required_terms",
                "wrapper_reentry",
            ],
            [
                [
                    row["scenario_id"],
                    row["runtime_status"],
                    row["primary_failure_category"],
                    row["planned_repair_lane"],
                    row["expected_mode"],
                    ", ".join(row["missing_required_terms"])
                    if row["missing_required_terms"]
                    else "NONE",
                    "yes" if row["requires_wrapper_reentry"] else "no",
                ]
                for row in scenario_rows
            ],
        ),
    ]
    write_report(output_path, lines)


def write_decision_report(*, output_path: Path, status: str, lane_entries: list[dict[str, Any]]) -> None:
    lane_ids = [entry["lane_id"] for entry in lane_entries]
    lines = [
        "# V1.5.0 Next Step Decision",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        "- This milestone is planning-only and does not authorize wrapper reruns, backend changes, runtime package regeneration, DPO, or adapter promotion.",
        f"- Planned narrow repair lanes from the refreshed evidence: `{', '.join(lane_ids) if lane_ids else 'NONE'}`.",
    ]
    if status == STATUS_READY:
        lines.extend(
            [
                "- Every failed scenario from the refreshed runtime package is assigned to a supported LV7-only repair lane with frozen wrapper/scorer boundaries.",
                f"- The next executable milestone is `{NEXT_EXECUTABLE_MILESTONE}`.",
            ]
        )
    else:
        lines.append(
            "- One or more refreshed runtime failures still lack a supported LV7-only repair lane or the prerequisite evidence chain is incomplete."
        )
    lines.extend(["", status])
    write_report(output_path, lines)


def analyze_v1_5_0_narrow_runtime_model_repair_planning(
    *,
    runtime_outputs_path: Path = DEFAULT_RUNTIME_OUTPUTS,
    runtime_results_report_path: Path = DEFAULT_RUNTIME_RESULTS_REPORT,
    runtime_execution_manifest_path: Path = DEFAULT_RUNTIME_EXECUTION_MANIFEST,
    v1_4_3_decision_report_path: Path = DEFAULT_V1_4_3_DECISION_REPORT,
    v1_4_3_wrapper_failure_review_path: Path = DEFAULT_WRAPPER_FAILURE_REVIEW_REPORT,
    v1_4_8_decision_report_path: Path = DEFAULT_V1_4_8_DECISION_REPORT,
    v1_4_9_decision_report_path: Path = DEFAULT_V1_4_9_DECISION_REPORT,
    v1_4_9_json_report_path: Path = DEFAULT_V1_4_9_JSON_REPORT,
    adapters_reference_path: Path = ADAPTER_REFERENCE_PATH,
    scoring_reference_path: Path = SCORING_REFERENCE_PATH,
    sft_config_path: Path = SFT_CONFIG_PATH,
    prepare_dataset_path: Path = PREPARE_DATASET_PATH,
    freeze_manifest_path: Path = FREEZE_MANIFEST_PATH,
    freeze_markdown_path: Path = FREEZE_MARKDOWN_PATH,
    plan_report_path: Path = DEFAULT_PLAN_REPORT,
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
        "v1_4_8_decision_report_path": display_path(v1_4_8_decision_report_path),
        "v1_4_9_decision_report_path": display_path(v1_4_9_decision_report_path),
        "v1_4_9_json_report_path": display_path(v1_4_9_json_report_path),
        "adapters_reference_path": display_path(adapters_reference_path),
        "scoring_reference_path": display_path(scoring_reference_path),
        "sft_config_path": display_path(sft_config_path),
        "prepare_dataset_path": display_path(prepare_dataset_path),
        "freeze_manifest_path": display_path(freeze_manifest_path),
        "freeze_markdown_path": display_path(freeze_markdown_path),
    }

    status = STATUS_READY
    lane_entries: list[dict[str, Any]] = []
    scenario_rows: list[dict[str, Any]] = []

    try:
        require(
            last_nonempty_line(v1_4_8_decision_report_path) == STATUS_V1_4_8_READY,
            f"{display_path(v1_4_8_decision_report_path)} does not end with {STATUS_V1_4_8_READY}",
        )
        require(
            last_nonempty_line(v1_4_9_decision_report_path) == STATUS_V1_4_9_READY,
            f"{display_path(v1_4_9_decision_report_path)} does not end with {STATUS_V1_4_9_READY}",
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
            v1_4_9_json_report_path,
            adapters_reference_path,
            scoring_reference_path,
            sft_config_path,
            prepare_dataset_path,
            freeze_manifest_path,
            freeze_markdown_path,
        ):
            require(required_path.exists(), f"missing required planning artifact: {display_path(required_path)}")

        validate_runtime_manifest(runtime_execution_manifest_path)
        freeze_manifest = read_json(freeze_manifest_path)
        require(
            freeze_manifest.get("adapter_path") == ACCEPTED_CHECKPOINT,
            f"{display_path(freeze_manifest_path)} has wrong adapter_path",
        )
        freeze_markdown_text = freeze_markdown_path.read_text(encoding="utf-8")
        require(
            ACCEPTED_CHECKPOINT in freeze_markdown_text,
            f"{display_path(freeze_markdown_path)} does not mention the accepted checkpoint",
        )

        payload = read_json(v1_4_9_json_report_path)
        require(
            payload.get("status") == STATUS_V1_4_9_READY,
            f"{display_path(v1_4_9_json_report_path)} does not report {STATUS_V1_4_9_READY}",
        )
        require(
            payload.get("accepted_checkpoint") == ACCEPTED_CHECKPOINT,
            f"{display_path(v1_4_9_json_report_path)} has wrong accepted checkpoint",
        )
        scenarios = payload.get("scenarios", [])
        require(
            isinstance(scenarios, list) and scenarios,
            f"{display_path(v1_4_9_json_report_path)} does not contain scenario rows",
        )

        lane_to_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for scenario in scenarios:
            scenario_id = str(scenario["scenario_id"])
            runtime_status = str(scenario["runtime_status"])
            primary_category = str(scenario["primary_failure_category"])
            expected_mode = str(scenario["expected_mode"])
            missing_required_terms = [
                str(item) for item in scenario.get("missing_required_terms", [])
            ]
            markers = [str(item) for item in scenario.get("cross_cutting_markers", [])]
            evidence_summary = str(scenario.get("evidence_summary", ""))
            recommended_lane = str(scenario["recommended_next_lane"])

            if runtime_status == "pass":
                require(
                    primary_category == NONE_CATEGORY and recommended_lane == NONE_LANE,
                    f"{display_path(v1_4_9_json_report_path)} has inconsistent pass row for {scenario_id}",
                )
                scenario_rows.append(
                    {
                        "scenario_id": scenario_id,
                        "runtime_status": runtime_status,
                        "primary_failure_category": primary_category,
                        "planned_repair_lane": NONE_LANE,
                        "expected_mode": expected_mode,
                        "missing_required_terms": missing_required_terms,
                        "cross_cutting_markers": markers,
                        "evidence_summary": evidence_summary,
                        "requires_wrapper_reentry": False,
                    }
                )
                continue

            require(
                recommended_lane in LANE_PLAN_TEMPLATES,
                f"{display_path(v1_4_9_json_report_path)} contains unsupported repair lane `{recommended_lane}` for {scenario_id}",
            )
            require(
                primary_category in LANE_PLAN_TEMPLATES[recommended_lane]["primary_categories"],
                f"{display_path(v1_4_9_json_report_path)} maps {scenario_id} to unsupported category `{primary_category}` for lane `{recommended_lane}`",
            )
            lane_to_rows[recommended_lane].append(
                {
                    "scenario_id": scenario_id,
                    "expected_mode": expected_mode,
                    "missing_required_terms": missing_required_terms,
                    "cross_cutting_markers": markers,
                    "evidence_summary": evidence_summary,
                }
            )
            scenario_rows.append(
                {
                    "scenario_id": scenario_id,
                    "runtime_status": runtime_status,
                    "primary_failure_category": primary_category,
                    "planned_repair_lane": recommended_lane,
                    "expected_mode": expected_mode,
                    "missing_required_terms": missing_required_terms,
                    "cross_cutting_markers": markers,
                    "evidence_summary": evidence_summary,
                    "requires_wrapper_reentry": False,
                }
            )

        for lane_id in sorted(lane_to_rows):
            lane_entries.append(build_lane_entry(lane_id, lane_to_rows[lane_id]))

        require(
            any(entry["lane_id"] == LANE_MODE_RETENTION for entry in lane_entries),
            "v1.5.0 planning expected a mode retention lane from the refreshed runtime evidence",
        )
        require(
            any(entry["lane_id"] == LANE_EXECUTE_PATH for entry in lane_entries),
            "v1.5.0 planning expected an execute-path lane from the refreshed runtime evidence",
        )
        require(
            any(entry["lane_id"] == LANE_BOUNDARY_ENFORCEMENT for entry in lane_entries),
            "v1.5.0 planning expected a boundary-enforcement lane from the refreshed runtime evidence",
        )
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as exc:
        status = STATUS_INSUFFICIENT
        lane_entries = []
        scenario_rows = [
            {
                "scenario_id": "GLOBAL_PREREQUISITE_GATE",
                "runtime_status": "fail",
                "primary_failure_category": "INSUFFICIENT_EVIDENCE",
                "planned_repair_lane": "NO_ACTION_INSUFFICIENT_EVIDENCE",
                "expected_mode": "",
                "missing_required_terms": [],
                "cross_cutting_markers": [],
                "evidence_summary": str(exc),
                "requires_wrapper_reentry": False,
            }
        ]

    write_plan_report(
        output_path=plan_report_path,
        status=status,
        source_artifacts=source_artifacts,
        lane_entries=lane_entries,
        scenario_rows=scenario_rows,
    )
    write_matrix_report(matrix_report_path, scenario_rows)
    write_decision_report(
        output_path=decision_report_path,
        status=status,
        lane_entries=lane_entries,
    )

    json_report_path.parent.mkdir(parents=True, exist_ok=True)
    json_report_path.write_text(
        json.dumps(
            {
                "milestone": "LV7 v1.5.0",
                "status": status,
                "accepted_checkpoint": ACCEPTED_CHECKPOINT,
                "source_artifact_paths": source_artifacts,
                "shared_constraints": SHARED_CONSTRAINTS,
                "frozen_surfaces": FROZEN_SURFACES,
                "next_executable_milestone": NEXT_EXECUTABLE_MILESTONE,
                "overall_repair_lanes": [entry["lane_id"] for entry in lane_entries],
                "lanes": lane_entries,
                "scenarios": scenario_rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "status": status,
        "repair_lane_count": len(lane_entries),
        "failed_scenarios": sum(1 for row in scenario_rows if row["runtime_status"] == "fail"),
        "overall_repair_lanes": [entry["lane_id"] for entry in lane_entries],
        "next_executable_milestone": NEXT_EXECUTABLE_MILESTONE,
        "accepted_checkpoint": ACCEPTED_CHECKPOINT,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan the narrow LV7 model repair lanes from the refreshed runtime evidence."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_5_0_narrow_runtime_model_repair_planning()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
