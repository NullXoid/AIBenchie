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
from training.analyze_v1_4_4_runtime_model_failure_diagnosis import (  # noqa: E402
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
from training.analyze_v1_5_1_narrow_runtime_sft_repair_implementation import (  # noqa: E402
    DEFAULT_DECISION_REPORT as DEFAULT_V1_5_1_DECISION_REPORT,
    STATUS_READY as STATUS_V1_5_1_READY,
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"
REPORTS_TRAINING_DIR = PROJECT_ROOT / "reports" / "training"
TRAINING_CONFIG_PATH = PROJECT_ROOT / "training" / "qlora_runtime_repair_v1_5_1.yaml"
TRAINING_RUN_CONFIG_PATH = REPORTS_TRAINING_DIR / "v1_5_1_sft_run_config.json"
TRAINING_LOG_PATH = REPORTS_TRAINING_DIR / "v1_5_1_sft_train_log.jsonl"
TRAINING_ANALYSIS_REPORT_PATH = REPORTS_TRAINING_DIR / "V1_5_1_NARROW_RUNTIME_SFT_ANALYSIS.md"
CURRENT_EXACT_RESULTS_PATH = REPORTS_TRAINING_DIR / "v1_5_1_exact_eval_results.jsonl"
BASELINE_EXACT_RESULTS_PATH = REPORTS_TRAINING_DIR / "v1_0_5_exact_eval_results.jsonl"
FREEZE_MARKDOWN_PATH = REPORTS_TRAINING_DIR / "V1_0_5_FREEZE.md"
FREEZE_MANIFEST_PATH = REPORTS_TRAINING_DIR / "v1_0_5_artifact_manifest.json"
V1_4_3_ANALYZER_PATH = PROJECT_ROOT / "training" / "analyze_v1_4_3_runtime_scenario_results.py"
CANDIDATE_ADAPTER_PATH = PROJECT_ROOT / "models" / "adapters" / "lv7_sft_runtime_repair_v1_5_1"
EXPECTED_CANDIDATE_OUTPUT_DIR = "models/adapters/lv7_sft_runtime_repair_v1_5_1/"

DEFAULT_IMPLEMENTATION_REPORT = (
    REPORTS_RUNTIME_DIR / "V1_5_2_NARROW_RUNTIME_SFT_TRAINING_RUN.md"
)
DEFAULT_MATRIX_REPORT = REPORTS_RUNTIME_DIR / "V1_5_2_RUNTIME_SFT_RESULT_MATRIX.md"
DEFAULT_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_2_NEXT_STEP_DECISION.md"
DEFAULT_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_2_narrow_runtime_sft_training_run.json"

STATUS_READY = "V1_5_2_CANDIDATE_READY_FOR_RUNTIME_BRIDGE"
STATUS_INSUFFICIENT = "V1_5_2_TRAINING_RUN_INSUFFICIENT"
NEXT_EXECUTABLE_MILESTONE = "LV7 v1.5.3 - Candidate Runtime Recheck Bridge"


def validate_training_config(path: Path) -> dict[str, Any]:
    payload = read_yaml_as_dict(path)
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
        payload.get("output_dir") == EXPECTED_CANDIDATE_OUTPUT_DIR,
        f"{display_path(path)} has wrong output_dir",
    )
    require(
        payload.get("output_dir") != ACCEPTED_CHECKPOINT,
        f"{display_path(path)} must not overwrite the accepted checkpoint",
    )
    return payload


def read_yaml_as_dict(path: Path) -> dict[str, Any]:
    import yaml

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    require(isinstance(payload, dict), f"{display_path(path)} must contain a mapping")
    return payload


def validate_training_run_config(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    require(
        payload.get("base_model") == "Qwen/Qwen2.5-1.5B-Instruct",
        f"{display_path(path)} has wrong base_model",
    )
    require(
        payload.get("dataset") == "data/pilot_v1_9/sft_messages.jsonl",
        f"{display_path(path)} has wrong dataset path",
    )
    require(
        payload.get("prepared_dataset") == "data/pilot_v1_9/sft_train_ready.jsonl",
        f"{display_path(path)} has wrong prepared_dataset path",
    )
    require(
        payload.get("output_dir") == EXPECTED_CANDIDATE_OUTPUT_DIR,
        f"{display_path(path)} has wrong output_dir",
    )
    require(
        payload.get("starting_adapter") in {"", None},
        f"{display_path(path)} must not start from a non-empty adapter path",
    )
    return payload


def validate_candidate_adapter(path: Path) -> list[str]:
    required_files = [
        "adapter_config.json",
        "adapter_model.safetensors",
        "chat_template.jinja",
        "tokenizer.json",
        "tokenizer_config.json",
        "training_args.bin",
    ]
    for relative in required_files:
        require((path / relative).exists(), f"candidate adapter is missing {relative}")
    require(path != PROJECT_ROOT / ACCEPTED_CHECKPOINT, "candidate adapter path must differ from accepted checkpoint")
    return required_files


def load_results_by_id(path: Path) -> dict[str, dict[str, Any]]:
    return {str(record["id"]): record for record in read_jsonl(path)}


def parse_mode(record: dict[str, Any]) -> str:
    parsed = record.get("parsed_policy_rationale", {})
    if isinstance(parsed, dict):
        return str(parsed.get("mode", ""))
    return ""


def collect_scenario_rows(
    *,
    current_results: dict[str, dict[str, Any]],
    baseline_results: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], int, int]:
    current_ids = set(current_results)
    baseline_ids = set(baseline_results)
    require(current_ids == baseline_ids, "current and baseline exact-eval scenario sets do not match")

    scenario_rows: list[dict[str, Any]] = []
    regression_ids: list[str] = []
    current_pass_count = 0
    baseline_pass_count = 0

    for scenario_id in sorted(current_ids):
        current = current_results[scenario_id]
        baseline = baseline_results[scenario_id]
        current_pass = bool(current.get("pass"))
        baseline_pass = bool(baseline.get("pass"))
        if current_pass:
            current_pass_count += 1
        if baseline_pass:
            baseline_pass_count += 1
        regression = baseline_pass and not current_pass
        if regression:
            regression_ids.append(scenario_id)
        scenario_rows.append(
            {
                "scenario_id": scenario_id,
                "current_pass": current_pass,
                "baseline_pass": baseline_pass,
                "regression_guard": not regression,
                "current_mode": parse_mode(current),
                "baseline_mode": parse_mode(baseline),
                "current_notes": str(current.get("score", {}).get("notes", "")),
                "baseline_notes": str(baseline.get("score", {}).get("notes", "")),
            }
        )

    return scenario_rows, regression_ids, current_pass_count, baseline_pass_count


def current_runtime_gate_is_accepted_only(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    return "model_adapter_path_is_accepted(" in source and "ACCEPTED_CHECKPOINT" in source


def write_training_run_report(
    *,
    output_path: Path,
    status: str,
    source_artifacts: dict[str, str],
    current_pass_count: int,
    total: int,
    baseline_pass_count: int,
    regression_ids: list[str],
    runtime_bridge_required: bool,
) -> None:
    lines = [
        "# V1.5.2 Narrow Runtime SFT Training Run",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- Candidate repair adapter path is `{EXPECTED_CANDIDATE_OUTPUT_DIR}`.",
        f"- Evidence-only adapters remain `{EVIDENCE_ONLY_SFT_ADAPTERS[0]}` and `{EVIDENCE_ONLY_SFT_ADAPTERS[1]}`.",
        f"- Parked DPO adapters remain `{PARKED_DPO_ADAPTERS[0]}` and `{PARKED_DPO_ADAPTERS[1]}`.",
        "- This milestone is LV7-only and records the narrow SFT repair training run. It does not rerun wrapper code, regenerate runtime outputs, reopen DPO, or silently promote the candidate over the accepted checkpoint.",
        "",
        "## Source Artifacts",
        "",
        f"- v1.5.1 decision: `{source_artifacts['v1_5_1_decision_report_path']}`",
        f"- training config: `{source_artifacts['training_config_path']}`",
        f"- training run config: `{source_artifacts['training_run_config_path']}`",
        f"- training log: `{source_artifacts['training_log_path']}`",
        f"- current exact eval results: `{source_artifacts['current_exact_results_path']}`",
        f"- baseline exact eval results: `{source_artifacts['baseline_exact_results_path']}`",
        f"- current training analysis: `{source_artifacts['training_analysis_report_path']}`",
        f"- accepted freeze markdown: `{source_artifacts['freeze_markdown_path']}`",
        f"- accepted freeze manifest: `{source_artifacts['freeze_manifest_path']}`",
        "",
        "## Training Outcome",
        "",
        f"- candidate exact-eval pass count: `{current_pass_count}/{total}`",
        f"- accepted v1.0.5 exact-eval pass count: `{baseline_pass_count}/{total}`",
        f"- regression guard failures vs accepted v1.0.5: `{', '.join(regression_ids) if regression_ids else 'none'}`",
        f"- wrapper/runtime contract remains unchanged: wrapper artifact `{EXPECTED_ARTIFACT}`, release tag `{EXPECTED_RELEASE_TAG}`, desktop commit `{EXPECTED_DESKTOP_COMMIT}`, backend tag `{EXPECTED_BACKEND_TAG}`",
        "",
        "## Candidate Boundary",
        "",
        f"- The accepted checkpoint stays `{ACCEPTED_CHECKPOINT}` until a later milestone explicitly replaces it.",
        f"- The current candidate is `models/adapters/lv7_sft_runtime_repair_v1_5_1/` and is not yet trusted by the pinned `v1.4.3` runtime-ingestion contract.",
        "- The training run therefore clears the model-repair candidate lane, but it does not by itself authorize runtime-result ingestion under the existing accepted-checkpoint gate.",
        "",
        "## Next Lane",
        "",
        f"- Current milestone status: `{status}`.",
        f"- Runtime candidate bridge required before wrapper rerun: `{runtime_bridge_required}`.",
        f"- Next executable milestone: `{NEXT_EXECUTABLE_MILESTONE}`.",
        "- The next step is to define or apply the narrow runtime-trust bridge that allows the new candidate adapter identity to be rerun through the truthful wrapper path without pretending it is the accepted `v1.0.5` checkpoint.",
    ]
    write_report(output_path, lines)


def write_matrix_report(output_path: Path, scenario_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# V1.5.2 Runtime SFT Result Matrix",
        "",
        render_markdown_table(
            [
                "scenario_id",
                "current_pass",
                "baseline_pass",
                "regression_guard",
                "current_mode",
                "baseline_mode",
                "current_notes",
            ],
            [
                [
                    row["scenario_id"],
                    "pass" if row["current_pass"] else "fail",
                    "pass" if row["baseline_pass"] else "fail",
                    "ok" if row["regression_guard"] else "regressed",
                    row["current_mode"] or "NONE",
                    row["baseline_mode"] or "NONE",
                    row["current_notes"] or "ok",
                ]
                for row in scenario_rows
            ],
        ),
    ]
    write_report(output_path, lines)


def write_decision_report(
    *,
    output_path: Path,
    status: str,
    current_pass_count: int,
    total: int,
    regression_ids: list[str],
    runtime_bridge_required: bool,
) -> None:
    lines = [
        "# V1.5.2 Next Step Decision",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        "- This milestone records the narrow runtime SFT repair training run only; it does not promote the candidate, rerun wrapper packaging, or reopen DPO.",
    ]
    if status == STATUS_READY:
        lines.extend(
            [
                f"- The candidate repair adapter cleared exact eval at `{current_pass_count}/{total}` with no regressions vs accepted `v1.0.5`.",
                f"- Runtime candidate bridge still required: `{runtime_bridge_required}` because `v1.4.3` ingests only the accepted checkpoint identity.",
                f"- The next executable milestone is `{NEXT_EXECUTABLE_MILESTONE}`.",
            ]
        )
    else:
        lines.extend(
            [
                "- The narrow repair training run is not yet supportable from the checked-in artifacts.",
                "- Resolve the missing training or exact-eval evidence before opening a candidate runtime recheck lane.",
            ]
        )
    lines.extend(["", status])
    write_report(output_path, lines)


def analyze_v1_5_2_narrow_runtime_sft_training_run(
    *,
    v1_5_1_decision_report_path: Path = DEFAULT_V1_5_1_DECISION_REPORT,
    training_config_path: Path = TRAINING_CONFIG_PATH,
    training_run_config_path: Path = TRAINING_RUN_CONFIG_PATH,
    training_log_path: Path = TRAINING_LOG_PATH,
    current_exact_results_path: Path = CURRENT_EXACT_RESULTS_PATH,
    baseline_exact_results_path: Path = BASELINE_EXACT_RESULTS_PATH,
    training_analysis_report_path: Path = TRAINING_ANALYSIS_REPORT_PATH,
    freeze_markdown_path: Path = FREEZE_MARKDOWN_PATH,
    freeze_manifest_path: Path = FREEZE_MANIFEST_PATH,
    v1_4_3_analyzer_path: Path = V1_4_3_ANALYZER_PATH,
    candidate_adapter_path: Path = CANDIDATE_ADAPTER_PATH,
    implementation_report_path: Path = DEFAULT_IMPLEMENTATION_REPORT,
    matrix_report_path: Path = DEFAULT_MATRIX_REPORT,
    decision_report_path: Path = DEFAULT_DECISION_REPORT,
    json_report_path: Path = DEFAULT_JSON_REPORT,
) -> dict[str, Any]:
    source_artifacts = {
        "v1_5_1_decision_report_path": display_path(v1_5_1_decision_report_path),
        "training_config_path": display_path(training_config_path),
        "training_run_config_path": display_path(training_run_config_path),
        "training_log_path": display_path(training_log_path),
        "current_exact_results_path": display_path(current_exact_results_path),
        "baseline_exact_results_path": display_path(baseline_exact_results_path),
        "training_analysis_report_path": display_path(training_analysis_report_path),
        "freeze_markdown_path": display_path(freeze_markdown_path),
        "freeze_manifest_path": display_path(freeze_manifest_path),
        "v1_4_3_analyzer_path": display_path(v1_4_3_analyzer_path),
        "candidate_adapter_path": display_path(candidate_adapter_path),
    }

    status = STATUS_READY
    scenario_rows: list[dict[str, Any]] = []
    current_pass_count = 0
    baseline_pass_count = 0
    total = 0
    regression_ids: list[str] = []
    runtime_bridge_required = True

    try:
        require(
            last_nonempty_line(v1_5_1_decision_report_path) == STATUS_V1_5_1_READY,
            f"{display_path(v1_5_1_decision_report_path)} does not end with {STATUS_V1_5_1_READY}",
        )
        for required_path in (
            training_config_path,
            training_run_config_path,
            training_log_path,
            current_exact_results_path,
            baseline_exact_results_path,
            training_analysis_report_path,
            freeze_markdown_path,
            freeze_manifest_path,
            v1_4_3_analyzer_path,
            candidate_adapter_path,
        ):
            require(required_path.exists(), f"missing required v1.5.2 artifact: {display_path(required_path)}")

        validate_training_config(training_config_path)
        validate_training_run_config(training_run_config_path)
        validate_candidate_adapter(candidate_adapter_path)

        training_log_records = read_jsonl(training_log_path)
        require(training_log_records, f"{display_path(training_log_path)} must contain training log records")

        freeze_manifest = read_json(freeze_manifest_path)
        require(
            freeze_manifest.get("adapter_path") == ACCEPTED_CHECKPOINT,
            f"{display_path(freeze_manifest_path)} has wrong accepted adapter path",
        )

        current_results = load_results_by_id(current_exact_results_path)
        baseline_results = load_results_by_id(baseline_exact_results_path)
        scenario_rows, regression_ids, current_pass_count, baseline_pass_count = collect_scenario_rows(
            current_results=current_results,
            baseline_results=baseline_results,
        )
        total = len(scenario_rows)
        require(total == 11, "v1.5.2 exact-eval suite must contain exactly 11 scenarios")
        require(current_pass_count == total, "candidate exact-eval suite must clear all 11 scenarios")
        require(not regression_ids, "candidate exact-eval suite must not regress any accepted v1.0.5 exact pass")

        runtime_bridge_required = current_runtime_gate_is_accepted_only(v1_4_3_analyzer_path)
        require(runtime_bridge_required, "current runtime ingestion gate no longer appears to be accepted-checkpoint-only")
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as exc:
        status = STATUS_INSUFFICIENT
        scenario_rows = [
            {
                "scenario_id": "GLOBAL_PREREQUISITE_GATE",
                "current_pass": False,
                "baseline_pass": False,
                "regression_guard": False,
                "current_mode": "",
                "baseline_mode": "",
                "current_notes": str(exc),
            }
        ]
        regression_ids = []
        current_pass_count = 0
        baseline_pass_count = 0
        total = 0
        runtime_bridge_required = True

    write_training_run_report(
        output_path=implementation_report_path,
        status=status,
        source_artifacts=source_artifacts,
        current_pass_count=current_pass_count,
        total=total,
        baseline_pass_count=baseline_pass_count,
        regression_ids=regression_ids,
        runtime_bridge_required=runtime_bridge_required,
    )
    write_matrix_report(matrix_report_path, scenario_rows)
    write_decision_report(
        output_path=decision_report_path,
        status=status,
        current_pass_count=current_pass_count,
        total=total,
        regression_ids=regression_ids,
        runtime_bridge_required=runtime_bridge_required,
    )

    json_report_path.parent.mkdir(parents=True, exist_ok=True)
    json_report_path.write_text(
        json.dumps(
            {
                "milestone": "LV7 v1.5.2",
                "status": status,
                "accepted_checkpoint": ACCEPTED_CHECKPOINT,
                "candidate_checkpoint": "models/adapters/lv7_sft_runtime_repair_v1_5_1/",
                "candidate_runtime_bridge_required": runtime_bridge_required,
                "source_artifact_paths": source_artifacts,
                "current_exact_eval_passed": current_pass_count,
                "baseline_exact_eval_passed": baseline_pass_count,
                "exact_eval_total": total,
                "regression_ids": regression_ids,
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
        "candidate_checkpoint": "models/adapters/lv7_sft_runtime_repair_v1_5_1/",
        "current_exact_eval_passed": current_pass_count,
        "baseline_exact_eval_passed": baseline_pass_count,
        "exact_eval_total": total,
        "regression_ids": regression_ids,
        "candidate_runtime_bridge_required": runtime_bridge_required,
        "next_executable_milestone": NEXT_EXECUTABLE_MILESTONE,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the v1.5.2 narrow runtime SFT training run."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_5_2_narrow_runtime_sft_training_run()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
