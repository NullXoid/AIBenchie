from __future__ import annotations

import argparse
import hashlib
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
from training.analyze_v1_4_2_runtime_scenario_eval_plan import (  # noqa: E402
    DEFAULT_SUITE_MANIFEST_JSON,
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
    DEFAULT_V1_4_2_ACCEPTANCE_REPORT,
    NO_WRAPPER_FAILURES_LINE,
    display_path,
    load_suite_contract,
    parse_results_report_sections,
    read_json,
    require,
    validate_runtime_package,
)
from training.analyze_v1_4_7_mode_selection_fix_spec import (  # noqa: E402
    DEFAULT_DECISION_REPORT as DEFAULT_V1_4_7_DECISION_REPORT,
    DEFAULT_JSON_REPORT as DEFAULT_V1_4_7_JSON_REPORT,
    FIX_SURFACE_MODE_GUIDANCE_PROMPT,
    FIX_SURFACE_MODE_SET_ALIGNMENT,
    STATUS_READY as STATUS_V1_4_7_READY,
    TARGET_SCENARIO_IDS,
    parse_supported_modes,
)
from training.analyze_v1_4_runtime_eval_readiness import (  # noqa: E402
    PROJECT_ROOT,
    last_nonempty_line,
    render_markdown_table,
    write_report,
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"
REPORTS_TRAINING_DIR = PROJECT_ROOT / "reports" / "training"
CHAT_TEMPLATE_PATH = PROJECT_ROOT / ACCEPTED_CHECKPOINT / "chat_template.jinja"
PROMPT_REFERENCE_PATH = PROJECT_ROOT / "evals" / "collect_model_outputs.py"
SCORING_REFERENCE_PATH = PROJECT_ROOT / "evals" / "scoring.py"
FREEZE_MANIFEST_PATH = REPORTS_TRAINING_DIR / "v1_0_5_artifact_manifest.json"
FREEZE_MARKDOWN_PATH = REPORTS_TRAINING_DIR / "V1_0_5_FREEZE.md"

DEFAULT_IMPLEMENTATION_REPORT = (
    REPORTS_RUNTIME_DIR / "V1_4_8_MODE_SELECTION_IMPLEMENTATION.md"
)
DEFAULT_MATRIX_REPORT = (
    REPORTS_RUNTIME_DIR / "V1_4_8_MODE_SELECTION_VALIDATION_MATRIX.md"
)
DEFAULT_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_4_8_NEXT_STEP_DECISION.md"
DEFAULT_JSON_REPORT = (
    REPORTS_RUNTIME_DIR / "v1_4_8_mode_selection_contract_implementation.json"
)

STATUS_READY = "V1_4_8_IMPLEMENTATION_READY"
STATUS_INSUFFICIENT = "V1_4_8_IMPLEMENTATION_INSUFFICIENT"

APPROVED_STATUSES = {
    STATUS_READY,
    STATUS_INSUFFICIENT,
}

NEXT_EXECUTABLE_MILESTONE = "Wrapper runtime output package rerun for accepted checkpoint"

IMPLEMENTATION_SURFACES = [
    "models/adapters/lv7_sft_smoke_v1_0_5/chat_template.jinja",
    "evals/collect_model_outputs.py",
    "evals/scoring.py",
]

PREVIOUS_TEMPLATE_SHA256 = "dedf89c5cdef193fa2d2dcfc30519268176cbcef072d9969573e61bbe8938a0c"
EXPECTED_ADAPTER_CONFIG_SHA256 = (
    "8b78760abf18a374c975bf4a91cd224c9625a986aae308b6d33d9650b92964b6"
)
EXPECTED_ADAPTER_MODEL_SHA256 = (
    "50b479faffb7cef1f069d71badee944cc07b4be25d834b054aeec309a3a267fb"
)

REQUIRED_MODE_ENUM = "mode: <execute|challenge|clarify|fallback|halt|escalate>"
REQUIRED_CLARIFY_GUIDANCE_FRAGMENTS = [
    "If the request is underspecified or the user has not chosen between speed, cost, reliability, or safety",
    "use mode=clarify",
    "keep the next step read-only until they choose",
]
REQUIRED_FALLBACK_GUIDANCE_FRAGMENTS = [
    "If second-pass execution stalls, is canceled, or would expose partial execution output",
    "use mode=fallback",
    "emit only sanitized fallback text",
    "Do not expose partial tool output or unfinished execution stream.",
]
REQUIRED_SCORING_FRAGMENTS = [
    "def emit_sanitized_fallback",
    "def suppress_partial_output",
    '"emit_sanitized_fallback": emit_sanitized_fallback',
    '"suppress_partial_output": suppress_partial_output',
    '"partial_output_leak":',
    '"unsafe_timeout_behavior":',
    'parsed["mode"] == "fallback"',
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def require_fragments(text: str, *, fragments: list[str], source_path: Path) -> None:
    missing = [fragment for fragment in fragments if fragment not in text]
    require(
        not missing,
        f"{display_path(source_path)} is missing required contract fragments: {', '.join(missing)}",
    )


def stringify_list(values: list[str]) -> str:
    return ", ".join(values) if values else "NONE"


def implementation_validation_summary(
    *,
    scenario_id: str,
    supported_modes: list[str],
    scoring_behaviors: list[str],
) -> str:
    if scenario_id == "ambiguous_goal_runtime_001":
        return (
            "clarify guidance now names speed/cost/reliability/safety tradeoffs, "
            "requires mode=clarify, and requires a read-only next step while waiting for direction"
        )
    return (
        "fallback added to the mode set and scorer now models "
        + ", ".join(scoring_behaviors)
    )


def write_implementation_report(
    *,
    output_path: Path,
    status: str,
    scenario_entries: list[dict[str, Any]],
    template_sha256: str,
    supported_modes: list[str],
    source_artifacts: dict[str, str],
) -> None:
    lines = [
        "# V1.4.8 Mode Selection Contract Implementation",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- Evidence-only adapters remain `{EVIDENCE_ONLY_SFT_ADAPTERS[0]}` and `{EVIDENCE_ONLY_SFT_ADAPTERS[1]}`.",
        f"- Parked DPO adapters remain `{PARKED_DPO_ADAPTERS[0]}` and `{PARKED_DPO_ADAPTERS[1]}`.",
        "- Wrapper-side runtime packaging remains complete and wrapper stays closed as a fault lane unless LV7 later proves a wrapper-side fault.",
        "- This milestone is LV7-only and does not rerun wrapper code, regenerate runtime outputs, reopen SFT/DPO, or change backend identity policy.",
        "",
        "## Implementation Surfaces",
        "",
        *[f"- `{surface}`" for surface in IMPLEMENTATION_SURFACES],
        f"- current chat-template sha256: `{template_sha256}`",
        f"- previous v1.4.6 chat-template sha256: `{PREVIOUS_TEMPLATE_SHA256}`",
        f"- current supported modes: `{', '.join(supported_modes)}`",
        "",
        "## Source Artifacts",
        "",
        f"- runtime outputs: `{source_artifacts['runtime_outputs_path']}`",
        f"- runtime results report: `{source_artifacts['runtime_results_report_path']}`",
        f"- runtime execution manifest: `{source_artifacts['runtime_execution_manifest_path']}`",
        f"- v1.4.3 decision: `{source_artifacts['v1_4_3_decision_report_path']}`",
        f"- v1.4.3 wrapper review: `{source_artifacts['v1_4_3_wrapper_failure_review_path']}`",
        f"- v1.4.7 decision: `{source_artifacts['v1_4_7_decision_report_path']}`",
        f"- v1.4.7 JSON report: `{source_artifacts['v1_4_7_json_report_path']}`",
        f"- current adapter template: `{source_artifacts['chat_template_path']}`",
        f"- current prompt reference: `{source_artifacts['prompt_reference_path']}`",
        f"- current scoring reference: `{source_artifacts['scoring_reference_path']}`",
        f"- freeze manifest: `{source_artifacts['freeze_manifest_path']}`",
        f"- freeze markdown: `{source_artifacts['freeze_markdown_path']}`",
        "",
        "## Implementation Summary",
        "",
        "- The accepted adapter contract now exposes `fallback` alongside the existing Level 7 modes without changing the wrapper/backend runtime contract.",
        "- The prompt/template layer now makes the ambiguous-goal clarify path explicit by naming the speed/cost/reliability/safety tradeoff family and requiring a read-only next step until the user chooses a target.",
        "- The scorer now recognizes the fallback-specific behaviors `emit_sanitized_fallback` and `suppress_partial_output`, which closes the repo-level contract gap identified in `v1.4.7`.",
        "- Adapter weights remain unchanged; this milestone updates LV7-owned prompt/template and scoring surfaces only.",
        "",
        "## Targeted Scenario Validation",
        "",
        render_markdown_table(
            [
                "scenario_id",
                "v1_4_7_fix_surface",
                "implementation_surface",
                "implementation_validation",
            ],
            [
                [
                    entry["scenario_id"],
                    entry["v1_4_7_fix_surface"],
                    stringify_list(entry["implementation_surface"]),
                    entry["implementation_validation"],
                ]
                for entry in scenario_entries
            ],
        ),
        "",
        "## Next Lane",
        "",
        f"- Current milestone status: `{status}`.",
        f"- Next executable milestone: `{NEXT_EXECUTABLE_MILESTONE}`.",
        "- The next step is a fresh runtime evidence pass through the existing truthful wrapper path so LV7 can classify the updated accepted checkpoint on new runtime outputs.",
        "",
        "## Wrapper Re-entry Rule",
        "",
        "- wrapper/backend only re-enters if LV7 provides:",
        "  - exact `scenario_id`",
        "  - observed wrapper/runtime behavior",
        "  - expected wrapper/runtime behavior",
        "  - evidence proving wrapper-side fault",
        "",
        "- absent that, wrapper stays closed as a fault lane, but a normal runtime output rerun remains the required next execution step after this LV7-only implementation.",
    ]
    write_report(output_path, lines)


def write_matrix_report(output_path: Path, scenario_entries: list[dict[str, Any]]) -> None:
    lines = [
        "# V1.4.8 Mode Selection Validation Matrix",
        "",
        render_markdown_table(
            [
                "scenario_id",
                "expected_mode",
                "v1_4_7_fix_surface",
                "validated_supported_modes",
                "validated_scoring_behaviors",
                "implementation_validation",
            ],
            [
                [
                    entry["scenario_id"],
                    entry["expected_mode"],
                    entry["v1_4_7_fix_surface"],
                    stringify_list(entry["validated_supported_modes"]),
                    stringify_list(entry["validated_scoring_behaviors"]),
                    entry["implementation_validation"],
                ]
                for entry in scenario_entries
            ],
        ),
    ]
    write_report(output_path, lines)


def write_decision_report(*, output_path: Path, status: str) -> None:
    lines = [
        "# V1.4.8 Next Step Decision",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        "- This milestone is LV7-only and does not authorize wrapper reruns as a fault lane, backend changes, runtime package regeneration inside LV7, SFT, DPO, or adapter promotion.",
    ]
    if status == STATUS_READY:
        lines.extend(
            [
                "- The wrong-mode contract surfaces identified in v1.4.7 are now implemented on the accepted LV7 checkpoint.",
                f"- The next executable milestone is `{NEXT_EXECUTABLE_MILESTONE}`.",
            ]
        )
    else:
        lines.extend(
            [
                "- The mode-selection contract implementation is not yet fully supportable from the checked-in artifact chain.",
                "- Resolve the missing implementation evidence before requesting a fresh runtime output package.",
            ]
        )
    lines.extend(["", status])
    write_report(output_path, lines)


def analyze_v1_4_8_mode_selection_contract_implementation(
    *,
    runtime_outputs_path: Path = DEFAULT_RUNTIME_OUTPUTS,
    runtime_results_report_path: Path = DEFAULT_RUNTIME_RESULTS_REPORT,
    runtime_execution_manifest_path: Path = DEFAULT_RUNTIME_EXECUTION_MANIFEST,
    v1_4_3_decision_report_path: Path = DEFAULT_V1_4_3_DECISION_REPORT,
    v1_4_3_wrapper_failure_review_path: Path = DEFAULT_WRAPPER_FAILURE_REVIEW_REPORT,
    v1_4_7_decision_report_path: Path = DEFAULT_V1_4_7_DECISION_REPORT,
    v1_4_7_json_report_path: Path = DEFAULT_V1_4_7_JSON_REPORT,
    suite_manifest_json_path: Path = DEFAULT_SUITE_MANIFEST_JSON,
    acceptance_report_path: Path = DEFAULT_V1_4_2_ACCEPTANCE_REPORT,
    chat_template_path: Path = CHAT_TEMPLATE_PATH,
    prompt_reference_path: Path = PROMPT_REFERENCE_PATH,
    scoring_reference_path: Path = SCORING_REFERENCE_PATH,
    freeze_manifest_path: Path = FREEZE_MANIFEST_PATH,
    freeze_markdown_path: Path = FREEZE_MARKDOWN_PATH,
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
        "v1_4_7_decision_report_path": display_path(v1_4_7_decision_report_path),
        "v1_4_7_json_report_path": display_path(v1_4_7_json_report_path),
        "suite_manifest_json_path": display_path(suite_manifest_json_path),
        "acceptance_report_path": display_path(acceptance_report_path),
        "chat_template_path": display_path(chat_template_path),
        "prompt_reference_path": display_path(prompt_reference_path),
        "scoring_reference_path": display_path(scoring_reference_path),
        "freeze_manifest_path": display_path(freeze_manifest_path),
        "freeze_markdown_path": display_path(freeze_markdown_path),
    }

    status = STATUS_READY
    scenario_entries: list[dict[str, Any]] = []
    template_sha256 = ""
    supported_modes: list[str] = []

    try:
        require(
            last_nonempty_line(v1_4_7_decision_report_path) == STATUS_V1_4_7_READY,
            f"{display_path(v1_4_7_decision_report_path)} does not end with {STATUS_V1_4_7_READY}",
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
            chat_template_path,
            prompt_reference_path,
            scoring_reference_path,
            freeze_manifest_path,
            freeze_markdown_path,
            v1_4_7_json_report_path,
        ):
            require(required_path.exists(), f"missing required source artifact: {display_path(required_path)}")

        require(
            (PROJECT_ROOT / ACCEPTED_CHECKPOINT).exists(),
            f"accepted checkpoint is missing: {ACCEPTED_CHECKPOINT}",
        )
        for adapter_path in (*EVIDENCE_ONLY_SFT_ADAPTERS, *PARKED_DPO_ADAPTERS):
            require((PROJECT_ROOT / adapter_path).exists(), f"expected adapter path is missing: {adapter_path}")

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

        v1_4_7_payload = read_json(v1_4_7_json_report_path)
        require(
            v1_4_7_payload.get("status") == STATUS_V1_4_7_READY,
            f"{display_path(v1_4_7_json_report_path)} does not report {STATUS_V1_4_7_READY}",
        )
        require(
            v1_4_7_payload.get("targeted_scenarios") == TARGET_SCENARIO_IDS,
            f"{display_path(v1_4_7_json_report_path)} no longer targets the pinned wrong-mode scenarios",
        )
        v1_4_7_entries = {
            entry["scenario_id"]: entry for entry in v1_4_7_payload.get("scenarios", [])
        }

        template_text = chat_template_path.read_text(encoding="utf-8")
        prompt_reference_text = prompt_reference_path.read_text(encoding="utf-8")
        scoring_text = scoring_reference_path.read_text(encoding="utf-8")

        require_fragments(
            template_text,
            fragments=[
                REQUIRED_MODE_ENUM,
                *REQUIRED_CLARIFY_GUIDANCE_FRAGMENTS,
                *REQUIRED_FALLBACK_GUIDANCE_FRAGMENTS,
            ],
            source_path=chat_template_path,
        )
        require_fragments(
            prompt_reference_text,
            fragments=[
                REQUIRED_MODE_ENUM,
                *REQUIRED_CLARIFY_GUIDANCE_FRAGMENTS,
                *REQUIRED_FALLBACK_GUIDANCE_FRAGMENTS,
            ],
            source_path=prompt_reference_path,
        )
        require_fragments(
            scoring_text,
            fragments=REQUIRED_SCORING_FRAGMENTS,
            source_path=scoring_reference_path,
        )

        supported_modes = parse_supported_modes(template_text, prompt_reference_text)
        require("clarify" in supported_modes, "current supported modes no longer include clarify")
        require("fallback" in supported_modes, "current supported modes do not include fallback")

        template_sha256 = sha256_file(chat_template_path)
        require(
            template_sha256 != PREVIOUS_TEMPLATE_SHA256,
            "accepted adapter chat template still matches the previous v1.4.6 mode set and guidance surface",
        )

        freeze_manifest = read_json(freeze_manifest_path)
        require(
            freeze_manifest.get("adapter_path") == ACCEPTED_CHECKPOINT,
            f"{display_path(freeze_manifest_path)} has wrong adapter_path",
        )
        adapter_files = freeze_manifest.get("adapter_files", {})
        require(
            adapter_files.get("chat_template.jinja", {}).get("sha256") == template_sha256,
            f"{display_path(freeze_manifest_path)} does not match the current chat template hash",
        )
        require(
            adapter_files.get("adapter_model.safetensors", {}).get("sha256")
            == EXPECTED_ADAPTER_MODEL_SHA256,
            f"{display_path(freeze_manifest_path)} no longer records the accepted adapter weights sha256",
        )
        require(
            adapter_files.get("adapter_config.json", {}).get("sha256")
            == EXPECTED_ADAPTER_CONFIG_SHA256,
            f"{display_path(freeze_manifest_path)} no longer records the accepted adapter config sha256",
        )
        freeze_markdown_text = freeze_markdown_path.read_text(encoding="utf-8")
        require(
            template_sha256 in freeze_markdown_text,
            f"{display_path(freeze_markdown_path)} does not mention the updated chat template hash",
        )
        require(
            ACCEPTED_CHECKPOINT in freeze_markdown_text,
            f"{display_path(freeze_markdown_path)} does not mention the accepted checkpoint path",
        )

        for scenario_id in TARGET_SCENARIO_IDS:
            require(scenario_id in records_by_id, f"runtime package is missing pinned scenario `{scenario_id}`")
            require(scenario_id in contracts_by_id, f"suite contract is missing pinned scenario `{scenario_id}`")
            require(scenario_id in v1_4_7_entries, f"v1.4.7 JSON report is missing `{scenario_id}`")

            record = records_by_id[scenario_id]
            contract = contracts_by_id[scenario_id]
            v1_4_7_entry = v1_4_7_entries[scenario_id]

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

            if scenario_id == "ambiguous_goal_runtime_001":
                require(
                    v1_4_7_entry.get("recommended_fix_surface") == FIX_SURFACE_MODE_GUIDANCE_PROMPT,
                    f"v1.4.7 no longer records {FIX_SURFACE_MODE_GUIDANCE_PROMPT} for `{scenario_id}`",
                )
                validated_scoring_behaviors = [
                    "ask_clarifying_question",
                    "avoid_unapproved_changes",
                ]
            else:
                require(
                    v1_4_7_entry.get("recommended_fix_surface") == FIX_SURFACE_MODE_SET_ALIGNMENT,
                    f"v1.4.7 no longer records {FIX_SURFACE_MODE_SET_ALIGNMENT} for `{scenario_id}`",
                )
                validated_scoring_behaviors = [
                    "emit_sanitized_fallback",
                    "suppress_partial_output",
                ]
                for behavior_name in validated_scoring_behaviors:
                    require(
                        f'"{behavior_name}"' in scoring_text or f"'{behavior_name}'" in scoring_text,
                        f"{display_path(scoring_reference_path)} does not expose `{behavior_name}`",
                    )

            scenario_entries.append(
                {
                    "scenario_id": scenario_id,
                    "expected_mode": contract["expected_mode"],
                    "v1_4_7_fix_surface": v1_4_7_entry["recommended_fix_surface"],
                    "implementation_surface": list(IMPLEMENTATION_SURFACES),
                    "validated_supported_modes": list(supported_modes),
                    "validated_scoring_behaviors": validated_scoring_behaviors,
                    "implementation_validation": implementation_validation_summary(
                        scenario_id=scenario_id,
                        supported_modes=supported_modes,
                        scoring_behaviors=validated_scoring_behaviors,
                    ),
                    "requires_wrapper_reentry": False,
                }
            )

        require(
            len(scenario_entries) == len(TARGET_SCENARIO_IDS),
            "v1.4.8 did not validate the full wrong-mode target set",
        )
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as exc:
        status = STATUS_INSUFFICIENT
        scenario_entries = [
            {
                "scenario_id": "GLOBAL_PREREQUISITE_GATE",
                "expected_mode": "",
                "v1_4_7_fix_surface": "NONE",
                "implementation_surface": list(IMPLEMENTATION_SURFACES),
                "validated_supported_modes": [],
                "validated_scoring_behaviors": [],
                "implementation_validation": str(exc),
                "requires_wrapper_reentry": False,
            }
        ]

    write_implementation_report(
        output_path=implementation_report_path,
        status=status,
        scenario_entries=scenario_entries,
        template_sha256=template_sha256,
        supported_modes=supported_modes,
        source_artifacts=source_artifacts,
    )
    write_matrix_report(matrix_report_path, scenario_entries)
    write_decision_report(output_path=decision_report_path, status=status)

    json_report_path.parent.mkdir(parents=True, exist_ok=True)
    json_report_path.write_text(
        json.dumps(
            {
                "milestone": "LV7 v1.4.8",
                "status": status,
                "accepted_checkpoint": ACCEPTED_CHECKPOINT,
                "implementation_surfaces": list(IMPLEMENTATION_SURFACES),
                "current_template_sha256": template_sha256,
                "previous_template_sha256": PREVIOUS_TEMPLATE_SHA256,
                "current_supported_modes": list(supported_modes),
                "source_artifact_paths": source_artifacts,
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
        "current_template_sha256": template_sha256,
        "next_executable_milestone": NEXT_EXECUTABLE_MILESTONE,
        "accepted_checkpoint": ACCEPTED_CHECKPOINT,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the v1.4.8 LV7 mode-selection contract implementation."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_4_8_mode_selection_contract_implementation()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
