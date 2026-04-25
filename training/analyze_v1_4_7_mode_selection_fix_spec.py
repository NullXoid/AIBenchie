from __future__ import annotations

import argparse
import json
import re
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
from training.analyze_v1_4_2_runtime_scenario_eval_plan import (  # noqa: E402
    DEFAULT_SUITE_MANIFEST_JSON,
)
from training.analyze_v1_4_3_runtime_scenario_results import (  # noqa: E402
    DEFAULT_DECISION_REPORT as DEFAULT_V1_4_3_DECISION_REPORT,
    DEFAULT_MODEL_FAILURE_REVIEW_REPORT,
    DEFAULT_RUNTIME_EXECUTION_MANIFEST,
    DEFAULT_RUNTIME_OUTPUTS,
    DEFAULT_RUNTIME_RESULTS_REPORT,
    DEFAULT_WRAPPER_FAILURE_REVIEW_REPORT,
    STATUS_MODEL_REPAIR,
)
from training.analyze_v1_4_4_runtime_model_failure_diagnosis import (  # noqa: E402
    DEFAULT_V1_4_2_ACCEPTANCE_REPORT,
    DEFAULT_V1_4_4_JSON_REPORT,
    NO_WRAPPER_FAILURES_LINE,
    display_path,
    excerpt,
    load_suite_contract,
    parse_grouped_markdown_bullets,
    parse_results_report_sections,
    read_json,
    require,
    validate_runtime_package,
)
from training.analyze_v1_4_5_policy_rationale_contract_fix import (  # noqa: E402
    DEFAULT_JSON_REPORT as DEFAULT_V1_4_5_JSON_REPORT,
)
from training.analyze_v1_4_6_policy_rationale_contract_fix_implementation import (  # noqa: E402
    DEFAULT_DECISION_REPORT as DEFAULT_V1_4_6_DECISION_REPORT,
    DEFAULT_IMPLEMENTATION_REPORT as DEFAULT_V1_4_6_IMPLEMENTATION_REPORT,
    STATUS_READY as STATUS_V1_4_6_READY,
)
from training.analyze_v1_4_runtime_eval_readiness import (  # noqa: E402
    PROJECT_ROOT,
    last_nonempty_line,
    render_markdown_table,
    write_report,
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"
CHAT_TEMPLATE_PATH = PROJECT_ROOT / ACCEPTED_CHECKPOINT / "chat_template.jinja"
PROMPT_REFERENCE_PATH = PROJECT_ROOT / "evals" / "collect_model_outputs.py"
SCORING_REFERENCE_PATH = PROJECT_ROOT / "evals" / "scoring.py"
EXACT_RESULTS_PATH = PROJECT_ROOT / "reports" / "training" / "v1_0_5_exact_eval_results.jsonl"

DEFAULT_FIX_SPEC_REPORT = REPORTS_RUNTIME_DIR / "V1_4_7_MODE_SELECTION_FIX_SPEC.md"
DEFAULT_MATRIX_REPORT = REPORTS_RUNTIME_DIR / "V1_4_7_MODE_SELECTION_SCENARIO_MATRIX.md"
DEFAULT_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_4_7_NEXT_STEP_DECISION.md"
DEFAULT_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_4_7_mode_selection_fix_spec.json"

STATUS_READY = "V1_4_7_FIX_SPEC_READY"
STATUS_INSUFFICIENT = "V1_4_7_FIX_SPEC_INSUFFICIENT"

APPROVED_STATUSES = {
    STATUS_READY,
    STATUS_INSUFFICIENT,
}

FIX_SURFACE_MODE_GUIDANCE_PROMPT = "MODE_GUIDANCE_PROMPT_FIX"
FIX_SURFACE_MODE_SET_ALIGNMENT = "MODE_SET_CONTRACT_ALIGNMENT"
FIX_SURFACE_MODEL_SPILLOVER = "MODEL_REPAIR_SPILLOVER"

NEXT_LANE_MODE_SELECTION = "MODE_SELECTION_CONTRACT_FIX"
NEXT_LANE_MODEL_REPAIR = "MODEL_REPAIR_INVESTIGATION"

TARGET_SCENARIO_IDS = [
    "ambiguous_goal_runtime_001",
    "cancel_timeout_fallback_runtime_001",
]

NEXT_EXECUTABLE_MILESTONE = "LV7 v1.4.8 - Mode Selection Contract Implementation"

RUNTIME_TO_EXACT_REFERENCE_ID = {
    "ambiguous_goal_runtime_001": "ambiguous_goal_001",
}

WRONG_MODE_REVIEW = "wrapper behaves correctly but accepted v1.0.5 output chooses the wrong LV7 mode"


def load_exact_eval_map(path: Path) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        scenario_id = str(payload.get("id", "")).strip()
        if scenario_id:
            entries[scenario_id] = payload
    return entries


def parse_supported_modes(*texts: str) -> list[str]:
    supported: set[str] = set()
    for text in texts:
        for match in re.findall(r"mode:\s*<([^>]+)>", text):
            for mode in match.split("|"):
                normalized = mode.strip()
                if normalized:
                    supported.add(normalized)
    return sorted(supported)


def scoring_supports_behavior(scoring_text: str, behavior_name: str) -> bool:
    return f'"{behavior_name}"' in scoring_text or f"'{behavior_name}'" in scoring_text


def stringify_list(values: list[str]) -> str:
    return ", ".join(values) if values else "NONE"


def determine_fix_surface(
    *,
    scenario_id: str,
    expected_mode: str,
    required_behavior: list[str],
    supported_modes: list[str],
    scoring_text: str,
    has_exact_reference: bool,
) -> str:
    if expected_mode not in supported_modes:
        return FIX_SURFACE_MODE_SET_ALIGNMENT
    if any(not scoring_supports_behavior(scoring_text, behavior) for behavior in required_behavior):
        return FIX_SURFACE_MODE_SET_ALIGNMENT
    if scenario_id == "ambiguous_goal_runtime_001" and has_exact_reference:
        return FIX_SURFACE_MODE_GUIDANCE_PROMPT
    return FIX_SURFACE_MODEL_SPILLOVER


def next_lane_for_surface(fix_surface: str) -> str:
    if fix_surface in {FIX_SURFACE_MODE_GUIDANCE_PROMPT, FIX_SURFACE_MODE_SET_ALIGNMENT}:
        return NEXT_LANE_MODE_SELECTION
    return NEXT_LANE_MODEL_REPAIR


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


def write_fix_spec_report(
    *,
    output_path: Path,
    status: str,
    scenario_entries: list[dict[str, Any]],
    source_artifacts: dict[str, str],
    supported_modes: list[str],
) -> None:
    prompt_fix_count = sum(
        1
        for entry in scenario_entries
        if entry["recommended_fix_surface"] == FIX_SURFACE_MODE_GUIDANCE_PROMPT
    )
    mode_set_count = sum(
        1
        for entry in scenario_entries
        if entry["recommended_fix_surface"] == FIX_SURFACE_MODE_SET_ALIGNMENT
    )
    spillover_count = sum(
        1
        for entry in scenario_entries
        if entry["recommended_fix_surface"] == FIX_SURFACE_MODEL_SPILLOVER
    )

    lines = [
        "# V1.4.7 Mode Selection Fix Specification",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- Evidence-only adapters remain `{EVIDENCE_ONLY_SFT_ADAPTERS[0]}` and `{EVIDENCE_ONLY_SFT_ADAPTERS[1]}`.",
        f"- Parked DPO adapters remain `{PARKED_DPO_ADAPTERS[0]}` and `{PARKED_DPO_ADAPTERS[1]}`.",
        "- Wrapper-side runtime packaging remains complete and wrapper stays closed unless LV7 later proves a wrapper-side fault.",
        "- This milestone is read-only and does not rerun wrapper code, regenerate runtime outputs, reopen SFT/DPO, or change backend identity policy.",
        "",
        "## Source Evidence",
        "",
        f"- runtime outputs: `{source_artifacts['runtime_outputs_path']}`",
        f"- runtime results report: `{source_artifacts['runtime_results_report_path']}`",
        f"- runtime execution manifest: `{source_artifacts['runtime_execution_manifest_path']}`",
        f"- v1.4.3 decision: `{source_artifacts['v1_4_3_decision_report_path']}`",
        f"- v1.4.3 model review: `{source_artifacts['v1_4_3_model_failure_review_path']}`",
        f"- v1.4.3 wrapper review: `{source_artifacts['v1_4_3_wrapper_failure_review_path']}`",
        f"- v1.4.4 diagnosis JSON: `{source_artifacts['v1_4_4_json_report_path']}`",
        f"- v1.4.5 fix spec JSON: `{source_artifacts['v1_4_5_json_report_path']}`",
        f"- v1.4.6 decision: `{source_artifacts['v1_4_6_decision_report_path']}`",
        f"- v1.4.6 implementation report: `{source_artifacts['v1_4_6_implementation_report_path']}`",
        f"- current adapter template: `{source_artifacts['chat_template_path']}`",
        f"- current prompt reference: `{source_artifacts['prompt_reference_path']}`",
        f"- current scoring reference: `{source_artifacts['scoring_reference_path']}`",
        f"- exact eval references: `{source_artifacts['exact_eval_results_path']}`",
        "",
        "## Contract Summary",
        "",
        f"- Targeted wrong-mode scenarios: `{len(scenario_entries)}`.",
        f"- Current prompt/template supported modes: `{', '.join(supported_modes)}`.",
        "- The remaining wrong-mode lane splits into two different LV7-owned surfaces:",
        f"  - `{FIX_SURFACE_MODE_GUIDANCE_PROMPT}` for scenarios whose expected mode is already supported and evidenced in the accepted checkpoint.",
        f"  - `{FIX_SURFACE_MODE_SET_ALIGNMENT}` for scenarios whose expected mode or required behaviors are not represented in the current LV7 prompt/scoring contract.",
        "",
        "## Fix-Surface Summary",
        "",
        render_markdown_table(
            ["recommended_fix_surface", "scenario_count", "meaning"],
            [
                [
                    FIX_SURFACE_MODE_GUIDANCE_PROMPT,
                    str(prompt_fix_count),
                    "The expected mode already exists in the LV7 contract, but prompt/mode-guidance needs tightening for this scenario family.",
                ],
                [
                    FIX_SURFACE_MODE_SET_ALIGNMENT,
                    str(mode_set_count),
                    "The expected mode or required behaviors are missing from current LV7 prompt/scoring references and must be added before any honest runtime re-evaluation.",
                ],
                [
                    FIX_SURFACE_MODEL_SPILLOVER,
                    str(spillover_count),
                    "Use only if the wrong-mode evidence cannot be honestly explained by prompt or contract gaps.",
                ],
            ],
        ),
        "",
        "## Recommended Smallest LV7-Owned Surface",
        "",
        "- The next executable work remains LV7-only.",
        "- `ambiguous_goal_runtime_001` should stay on the mode-guidance prompt lane because the accepted checkpoint already passed the same clarify family in exact eval evidence.",
        "- `cancel_timeout_fallback_runtime_001` is blocked by a repo-level contract mismatch because the pinned runtime suite expects `fallback` while the current LV7 prompt/template and scoring surfaces do not yet model `fallback` or its required behaviors.",
        f"- Next executable milestone: `{NEXT_EXECUTABLE_MILESTONE}`.",
        "- Do not reopen wrapper/backend, SFT, or DPO from this milestone.",
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
        "",
        "## Milestone Status",
        "",
        f"- status: `{status}`",
    ]
    write_report(output_path, lines)


def write_matrix_report(output_path: Path, scenario_entries: list[dict[str, Any]]) -> None:
    rows = []
    for entry in scenario_entries:
        rows.append(
            [
                entry["scenario_id"],
                entry["observed_mode_selection_failure"],
                entry["current_mode_contract_gap"],
                entry["recommended_fix_surface"],
                entry["recommended_next_lane"],
            ]
        )

    lines = [
        "# V1.4.7 Mode Selection Scenario Matrix",
        "",
        render_markdown_table(
            [
                "scenario_id",
                "observed_mode_selection_failure",
                "current_mode_contract_gap",
                "recommended_fix_surface",
                "next_lane",
            ],
            rows,
        ),
    ]
    write_report(output_path, lines)


def write_decision_report(*, output_path: Path, status: str, scenario_entries: list[dict[str, Any]]) -> None:
    unique_lanes = sorted(
        {
            entry["recommended_next_lane"]
            for entry in scenario_entries
            if entry["recommended_next_lane"] != "NONE"
        }
    )
    lines = [
        "# V1.4.7 Next Step Decision",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        "- This milestone is analysis-only and does not authorize wrapper reruns, backend changes, runtime package regeneration, SFT, DPO, or adapter promotion.",
        f"- Targeted wrong-mode scenarios reviewed: `{len(scenario_entries)}`.",
        f"- Recommended next lanes from the current evidence: `{', '.join(unique_lanes) if unique_lanes else 'NONE'}`.",
    ]
    if status == STATUS_READY:
        lines.append("- Every wrong-mode scenario received a supported LV7-owned fix specification.")
    else:
        lines.append("- One or more wrong-mode scenarios still lack enough supportable evidence for a fix specification.")
    lines.extend(["", status])
    write_report(output_path, lines)


def analyze_v1_4_7_mode_selection_fix_spec(
    *,
    runtime_outputs_path: Path = DEFAULT_RUNTIME_OUTPUTS,
    runtime_results_report_path: Path = DEFAULT_RUNTIME_RESULTS_REPORT,
    runtime_execution_manifest_path: Path = DEFAULT_RUNTIME_EXECUTION_MANIFEST,
    v1_4_3_decision_report_path: Path = DEFAULT_V1_4_3_DECISION_REPORT,
    v1_4_3_model_failure_review_path: Path = DEFAULT_MODEL_FAILURE_REVIEW_REPORT,
    v1_4_3_wrapper_failure_review_path: Path = DEFAULT_WRAPPER_FAILURE_REVIEW_REPORT,
    v1_4_4_json_report_path: Path = DEFAULT_V1_4_4_JSON_REPORT,
    v1_4_5_json_report_path: Path = DEFAULT_V1_4_5_JSON_REPORT,
    v1_4_6_decision_report_path: Path = DEFAULT_V1_4_6_DECISION_REPORT,
    v1_4_6_implementation_report_path: Path = DEFAULT_V1_4_6_IMPLEMENTATION_REPORT,
    suite_manifest_json_path: Path = DEFAULT_SUITE_MANIFEST_JSON,
    acceptance_report_path: Path = DEFAULT_V1_4_2_ACCEPTANCE_REPORT,
    chat_template_path: Path = CHAT_TEMPLATE_PATH,
    prompt_reference_path: Path = PROMPT_REFERENCE_PATH,
    scoring_reference_path: Path = SCORING_REFERENCE_PATH,
    exact_eval_results_path: Path = EXACT_RESULTS_PATH,
    fix_spec_report_path: Path = DEFAULT_FIX_SPEC_REPORT,
    matrix_report_path: Path = DEFAULT_MATRIX_REPORT,
    decision_report_path: Path = DEFAULT_DECISION_REPORT,
    json_report_path: Path = DEFAULT_JSON_REPORT,
) -> dict[str, Any]:
    source_artifacts = {
        "runtime_outputs_path": display_path(runtime_outputs_path),
        "runtime_results_report_path": display_path(runtime_results_report_path),
        "runtime_execution_manifest_path": display_path(runtime_execution_manifest_path),
        "v1_4_3_decision_report_path": display_path(v1_4_3_decision_report_path),
        "v1_4_3_model_failure_review_path": display_path(v1_4_3_model_failure_review_path),
        "v1_4_3_wrapper_failure_review_path": display_path(v1_4_3_wrapper_failure_review_path),
        "v1_4_4_json_report_path": display_path(v1_4_4_json_report_path),
        "v1_4_5_json_report_path": display_path(v1_4_5_json_report_path),
        "v1_4_6_decision_report_path": display_path(v1_4_6_decision_report_path),
        "v1_4_6_implementation_report_path": display_path(v1_4_6_implementation_report_path),
        "suite_manifest_json_path": display_path(suite_manifest_json_path),
        "acceptance_report_path": display_path(acceptance_report_path),
        "chat_template_path": display_path(chat_template_path),
        "prompt_reference_path": display_path(prompt_reference_path),
        "scoring_reference_path": display_path(scoring_reference_path),
        "exact_eval_results_path": display_path(exact_eval_results_path),
    }

    scenario_entries: list[dict[str, Any]] = []
    status = STATUS_READY
    supported_modes: list[str] = []

    try:
        require(
            last_nonempty_line(v1_4_6_decision_report_path) == STATUS_V1_4_6_READY,
            f"{display_path(v1_4_6_decision_report_path)} does not end with {STATUS_V1_4_6_READY}",
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
            v1_4_4_json_report_path,
            v1_4_5_json_report_path,
            v1_4_6_implementation_report_path,
            chat_template_path,
            prompt_reference_path,
            scoring_reference_path,
            exact_eval_results_path,
        ):
            require(required_path.exists(), f"missing required source artifact: {display_path(required_path)}")

        require(
            (PROJECT_ROOT / ACCEPTED_CHECKPOINT).exists(),
            f"accepted checkpoint is missing: {ACCEPTED_CHECKPOINT}",
        )

        results_sections = parse_results_report_sections(runtime_results_report_path)
        manifest, scenario_contracts = load_suite_contract(
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
        records_by_id = {record["scenario_id"]: record for record in records}
        contracts_by_id = {contract["scenario_id"]: contract for contract in scenario_contracts}
        model_review = parse_grouped_markdown_bullets(v1_4_3_model_failure_review_path)
        v1_4_4_payload = read_json(v1_4_4_json_report_path)
        v1_4_5_payload = read_json(v1_4_5_json_report_path)
        diagnoses_by_id = {entry["scenario_id"]: entry for entry in v1_4_4_payload["scenarios"]}
        exact_eval_map = load_exact_eval_map(exact_eval_results_path)

        template_text = chat_template_path.read_text(encoding="utf-8")
        prompt_text = prompt_reference_path.read_text(encoding="utf-8")
        scoring_text = scoring_reference_path.read_text(encoding="utf-8")
        supported_modes = parse_supported_modes(template_text, prompt_text)

        require(
            v1_4_5_payload.get("status") == "V1_4_5_FIX_SPEC_READY",
            f"{display_path(v1_4_5_json_report_path)} does not report V1_4_5_FIX_SPEC_READY",
        )
        require(
            all(
                entry["recommended_fix_surface"] == "PROMPT_TEMPLATE_FIX"
                for entry in v1_4_5_payload.get("scenarios", [])
            ),
            f"{display_path(v1_4_5_json_report_path)} no longer records a pure policy-rationale prompt/template lane",
        )

        for scenario_id in TARGET_SCENARIO_IDS:
            require(
                scenario_id in records_by_id,
                f"runtime package is missing pinned scenario `{scenario_id}`",
            )
            require(
                scenario_id in contracts_by_id,
                f"suite contract is missing pinned scenario `{scenario_id}`",
            )
            require(
                scenario_id in diagnoses_by_id,
                f"v1.4.4 diagnosis is missing `{scenario_id}`",
            )
            diagnosis = diagnoses_by_id[scenario_id]
            require(
                diagnosis.get("failure_category") == "WRONG_LV7_MODE_SELECTION",
                f"v1.4.4 no longer classifies `{scenario_id}` as WRONG_LV7_MODE_SELECTION",
            )
            require(
                diagnosis.get("recommended_next_lane") == "LV7_MODE_SELECTION_FIX",
                f"v1.4.4 no longer routes `{scenario_id}` to LV7_MODE_SELECTION_FIX",
            )

            record = records_by_id[scenario_id]
            contract = contracts_by_id[scenario_id]
            review_bullets = model_review.get(scenario_id, [])
            require(
                WRONG_MODE_REVIEW in review_bullets,
                f"{display_path(v1_4_3_model_failure_review_path)} no longer records wrong-mode evidence for `{scenario_id}`",
            )
            require(
                not record["wrapper_contract_failures"],
                f"runtime output `{scenario_id}` still carries wrapper failures and is not eligible for LV7-only mode-selection analysis",
            )
            require(
                record["model_adapter_path"] == ACCEPTED_CHECKPOINT,
                f"runtime output `{scenario_id}` has wrong model_adapter_path",
            )
            require(
                record["wrapper_artifact"] == EXPECTED_ARTIFACT,
                f"runtime output `{scenario_id}` has wrong wrapper_artifact",
            )
            require(
                record["release_tag"] == EXPECTED_RELEASE_TAG,
                f"runtime output `{scenario_id}` has wrong release_tag",
            )
            require(
                record["desktop_commit"] == EXPECTED_DESKTOP_COMMIT,
                f"runtime output `{scenario_id}` has wrong desktop_commit",
            )
            require(
                record["backend_tag"] == EXPECTED_BACKEND_TAG,
                f"runtime output `{scenario_id}` has wrong backend_tag",
            )

            expected_mode = contract["expected_mode"]
            required_behavior = list(contract["required_behavior"])
            missing_scoring_behaviors = [
                behavior
                for behavior in required_behavior
                if not scoring_supports_behavior(scoring_text, behavior)
            ]
            exact_reference_id = RUNTIME_TO_EXACT_REFERENCE_ID.get(scenario_id)
            exact_reference = (
                None if exact_reference_id is None else exact_eval_map.get(exact_reference_id)
            )
            fix_surface = determine_fix_surface(
                scenario_id=scenario_id,
                expected_mode=expected_mode,
                required_behavior=required_behavior,
                supported_modes=supported_modes,
                scoring_text=scoring_text,
                has_exact_reference=exact_reference is not None
                and bool(exact_reference.get("pass") is True),
            )

            if fix_surface == FIX_SURFACE_MODE_SET_ALIGNMENT:
                gap_parts: list[str] = []
                if expected_mode not in supported_modes:
                    gap_parts.append(
                        f"expected mode `{expected_mode}` is not in the current prompt/template mode set"
                    )
                if missing_scoring_behaviors:
                    gap_parts.append(
                        "current scoring helpers do not implement: "
                        + ", ".join(missing_scoring_behaviors)
                    )
                current_gap = "; ".join(gap_parts)
                reference_support = (
                    "No accepted exact-eval runtime reference exists for this fallback family, and the current LV7 prompt/scoring contract does not model fallback yet."
                )
            elif fix_surface == FIX_SURFACE_MODE_GUIDANCE_PROMPT:
                current_gap = (
                    "expected mode is already supported in the LV7 prompt/template and scoring contract, but the runtime evidence still defaulted to a generic information-seeking answer instead of the clarify contract."
                )
                reference_support = excerpt(
                    str(exact_reference["response_text"]),
                    limit=220,
                )
            else:
                current_gap = (
                    "current LV7 prompt/scoring surfaces do not explain the remaining wrong-mode failure cleanly."
                )
                reference_support = "No narrower non-model fix surface was supportable from current evidence."

            scenario_entries.append(
                {
                    "scenario_id": scenario_id,
                    "observed_raw_model_text_excerpt": excerpt(
                        str(record["raw_model_text"]),
                        limit=220,
                    ),
                    "observed_final_emitted_text_excerpt": excerpt(
                        str(record["final_emitted_text"]),
                        limit=220,
                    ),
                    "expected_mode": expected_mode,
                    "expected_required_behavior": ", ".join(required_behavior),
                    "current_prompt_supported_modes": list(supported_modes),
                    "current_scoring_supported_behaviors": [
                        behavior
                        for behavior in required_behavior
                        if behavior not in missing_scoring_behaviors
                    ],
                    "current_mode_contract_gap": current_gap,
                    "mode_contract_gap_details": {
                        "expected_mode_supported": expected_mode in supported_modes,
                        "missing_scoring_behaviors": missing_scoring_behaviors,
                    },
                    "reference_support": reference_support,
                    "recommended_fix_surface": fix_surface,
                    "recommended_next_lane": next_lane_for_surface(fix_surface),
                    "requires_wrapper_reentry": False,
                    "requires_model_repair_escalation": fix_surface == FIX_SURFACE_MODEL_SPILLOVER,
                    "observed_mode_selection_failure": diagnosis["evidence_summary"],
                    "evidence_summary": diagnosis["evidence_summary"],
                    "expected_contract_behavior": expected_contract_behavior(contract),
                }
            )

        require(
            len(scenario_entries) == len(TARGET_SCENARIO_IDS),
            "v1.4.7 did not build entries for the full wrong-mode target set",
        )

        if any(
            entry["recommended_fix_surface"] == FIX_SURFACE_MODEL_SPILLOVER
            for entry in scenario_entries
        ):
            status = STATUS_INSUFFICIENT
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as exc:
        status = STATUS_INSUFFICIENT
        scenario_entries = [
            {
                "scenario_id": "GLOBAL_PREREQUISITE_GATE",
                "observed_raw_model_text_excerpt": "Mode-selection fix spec did not run because prerequisite gating failed.",
                "observed_final_emitted_text_excerpt": "Mode-selection fix spec did not run because prerequisite gating failed.",
                "expected_mode": "",
                "expected_required_behavior": "",
                "current_prompt_supported_modes": [],
                "current_scoring_supported_behaviors": [],
                "current_mode_contract_gap": str(exc),
                "mode_contract_gap_details": {
                    "expected_mode_supported": False,
                    "missing_scoring_behaviors": [],
                },
                "reference_support": "No supporting reference was available.",
                "recommended_fix_surface": FIX_SURFACE_MODE_SET_ALIGNMENT,
                "recommended_next_lane": NEXT_LANE_MODE_SELECTION,
                "requires_wrapper_reentry": False,
                "requires_model_repair_escalation": False,
                "observed_mode_selection_failure": "Fix specification did not run.",
                "evidence_summary": str(exc),
                "expected_contract_behavior": "v1.4.7 requires the trusted v1.4.3-v1.4.6 artifact chain and the delivered runtime package.",
            }
        ]

    write_fix_spec_report(
        output_path=fix_spec_report_path,
        status=status,
        scenario_entries=scenario_entries,
        source_artifacts=source_artifacts,
        supported_modes=supported_modes,
    )
    write_matrix_report(matrix_report_path, scenario_entries)
    write_decision_report(
        output_path=decision_report_path,
        status=status,
        scenario_entries=scenario_entries,
    )

    json_report_path.parent.mkdir(parents=True, exist_ok=True)
    json_report_path.write_text(
        json.dumps(
            {
                "milestone": "LV7 v1.4.7",
                "status": status,
                "accepted_checkpoint": ACCEPTED_CHECKPOINT,
                "source_artifact_paths": source_artifacts,
                "targeted_scenarios": list(TARGET_SCENARIO_IDS),
                "current_supported_modes": list(supported_modes),
                "next_executable_milestone": NEXT_EXECUTABLE_MILESTONE,
                "scenarios": scenario_entries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "status": status,
        "targeted_scenario_count": len(
            [entry for entry in scenario_entries if entry["scenario_id"] != "GLOBAL_PREREQUISITE_GATE"]
        ),
        "current_supported_modes": list(supported_modes),
        "next_executable_milestone": NEXT_EXECUTABLE_MILESTONE,
        "accepted_checkpoint": ACCEPTED_CHECKPOINT,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the v1.4.7 mode-selection fix specification."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_4_7_mode_selection_fix_spec()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
