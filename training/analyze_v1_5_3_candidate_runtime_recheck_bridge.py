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
from training.analyze_v1_5_2_narrow_runtime_sft_training_run import (  # noqa: E402
    CURRENT_EXACT_RESULTS_PATH,
    BASELINE_EXACT_RESULTS_PATH,
    DEFAULT_DECISION_REPORT as DEFAULT_V1_5_2_DECISION_REPORT,
    DEFAULT_JSON_REPORT as DEFAULT_V1_5_2_JSON_REPORT,
    STATUS_READY as STATUS_V1_5_2_READY,
    collect_scenario_rows,
    current_runtime_gate_is_accepted_only,
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"
SIBLING_BACKEND_ROOT = PROJECT_ROOT.parent / "Felnx" / "NullXoid" / ".NullXoid"

DEFAULT_V1_4_3A_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_4_3A_NEXT_STEP_DECISION.md"
DEFAULT_V1_4_3A_POLICY_JSON = REPORTS_RUNTIME_DIR / "v1_4_3a_backend_identity_policy.json"
DEFAULT_IMPLEMENTATION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_3_CANDIDATE_RUNTIME_RECHECK_BRIDGE.md"
DEFAULT_MATRIX_REPORT = REPORTS_RUNTIME_DIR / "V1_5_3_RUNTIME_BRIDGE_MATRIX.md"
DEFAULT_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_3_NEXT_STEP_DECISION.md"
DEFAULT_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_3_candidate_runtime_recheck_bridge.json"

V1_4_3_ANALYZER_PATH = PROJECT_ROOT / "training" / "analyze_v1_4_3_runtime_scenario_results.py"
CANDIDATE_CHECKPOINT = "models/adapters/lv7_sft_runtime_repair_v1_5_1/"
CANDIDATE_ALIAS_MODEL_ID = "lv7_sft_runtime_repair_v1_5_1:qwen2.5-1.5b-instruct"
EXPECTED_BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"

BACKEND_ALIAS_PROVIDER_PATH = SIBLING_BACKEND_ROOT / "backend" / "providers" / "lv7_alias.py"
BACKEND_OLLAMA_PROVIDER_PATH = SIBLING_BACKEND_ROOT / "backend" / "providers" / "ollama.py"
BACKEND_ALIAS_TEST_PATH = SIBLING_BACKEND_ROOT / "backend" / "tests" / "test_lv7_model_alias.py"

STATUS_READY = "V1_5_3_RUNTIME_BRIDGE_READY"
STATUS_INCOMPLETE = "V1_5_3_RUNTIME_BRIDGE_INCOMPLETE"
STATUS_INVALID = "V1_5_3_RUNTIME_BRIDGE_INVALID"
APPROVED_STATUSES = {STATUS_READY, STATUS_INCOMPLETE, STATUS_INVALID}
NEXT_EXECUTABLE_MILESTONE = (
    "Wrapper candidate runtime output package rerun for models/adapters/lv7_sft_runtime_repair_v1_5_1/"
)


def load_results_by_id(path: Path) -> dict[str, dict[str, Any]]:
    return {str(record["id"]): record for record in read_jsonl(path)}


def validate_candidate_runtime_bridge(
    *,
    v1_5_2_decision_report_path: Path,
    v1_5_2_json_report_path: Path,
    v1_4_3a_decision_report_path: Path,
    v1_4_3a_policy_json_path: Path,
    current_exact_results_path: Path,
    baseline_exact_results_path: Path,
    v1_4_3_analyzer_path: Path,
    backend_alias_provider_path: Path,
    backend_ollama_provider_path: Path,
    backend_alias_test_path: Path,
) -> dict[str, Any]:
    required_paths = [
        v1_5_2_decision_report_path,
        v1_5_2_json_report_path,
        v1_4_3a_decision_report_path,
        v1_4_3a_policy_json_path,
        current_exact_results_path,
        baseline_exact_results_path,
        v1_4_3_analyzer_path,
        backend_alias_provider_path,
        backend_ollama_provider_path,
        backend_alias_test_path,
        PROJECT_ROOT / ACCEPTED_CHECKPOINT,
        PROJECT_ROOT / CANDIDATE_CHECKPOINT,
    ]
    missing = [display_path(path) for path in required_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing required v1.5.3 artifact: {', '.join(missing)}")

    require(
        last_nonempty_line(v1_5_2_decision_report_path) == STATUS_V1_5_2_READY,
        f"{display_path(v1_5_2_decision_report_path)} does not end with {STATUS_V1_5_2_READY}",
    )
    require(
        last_nonempty_line(v1_4_3a_decision_report_path) == "RUNTIME_BACKEND_IDENTITY_POLICY_READY",
        f"{display_path(v1_4_3a_decision_report_path)} does not end with RUNTIME_BACKEND_IDENTITY_POLICY_READY",
    )

    v1_5_2_payload = read_json(v1_5_2_json_report_path)
    require(
        v1_5_2_payload.get("status") == STATUS_V1_5_2_READY,
        f"{display_path(v1_5_2_json_report_path)} has wrong status",
    )
    require(
        v1_5_2_payload.get("candidate_checkpoint") == CANDIDATE_CHECKPOINT,
        f"{display_path(v1_5_2_json_report_path)} has wrong candidate_checkpoint",
    )
    require(
        v1_5_2_payload.get("candidate_runtime_bridge_required") is True,
        f"{display_path(v1_5_2_json_report_path)} must keep candidate_runtime_bridge_required=true",
    )

    backend_policy = read_json(v1_4_3a_policy_json_path)
    require(
        backend_policy.get("status") == "RUNTIME_BACKEND_IDENTITY_POLICY_READY",
        f"{display_path(v1_4_3a_policy_json_path)} has wrong status",
    )
    require(
        backend_policy.get("alias_model_id") == "lv7_sft_smoke_v1_0_5:qwen2.5-1.5b-instruct",
        f"{display_path(v1_4_3a_policy_json_path)} has wrong accepted alias_model_id",
    )
    require(
        backend_policy.get("accepted_adapter_path") == ACCEPTED_CHECKPOINT,
        f"{display_path(v1_4_3a_policy_json_path)} has wrong accepted_adapter_path",
    )
    require(
        backend_policy.get("wrapper_artifact") == EXPECTED_ARTIFACT,
        f"{display_path(v1_4_3a_policy_json_path)} has wrong wrapper_artifact",
    )
    require(
        backend_policy.get("release_tag") == EXPECTED_RELEASE_TAG,
        f"{display_path(v1_4_3a_policy_json_path)} has wrong release_tag",
    )
    require(
        backend_policy.get("desktop_commit") == EXPECTED_DESKTOP_COMMIT,
        f"{display_path(v1_4_3a_policy_json_path)} has wrong desktop_commit",
    )
    require(
        backend_policy.get("backend_tag") == EXPECTED_BACKEND_TAG,
        f"{display_path(v1_4_3a_policy_json_path)} has wrong backend_tag",
    )

    current_results = load_results_by_id(current_exact_results_path)
    baseline_results = load_results_by_id(baseline_exact_results_path)
    scenario_rows, regression_ids, current_pass_count, baseline_pass_count = collect_scenario_rows(
        current_results=current_results,
        baseline_results=baseline_results,
    )
    require(len(scenario_rows) == 11, "v1.5.3 exact-eval suite must still contain 11 scenarios")
    require(current_pass_count == 11, "candidate exact-eval suite must still clear all 11 scenarios")
    require(not regression_ids, "candidate exact-eval suite must still show no regressions vs accepted v1.0.5")
    require(
        current_runtime_gate_is_accepted_only(v1_4_3_analyzer_path),
        "v1.4.3 runtime ingestion is no longer accepted-checkpoint-only; bridge no longer matches the pinned assumption",
    )

    backend_alias_source = backend_alias_provider_path.read_text(encoding="utf-8")
    backend_ollama_source = backend_ollama_provider_path.read_text(encoding="utf-8")
    backend_alias_tests = backend_alias_test_path.read_text(encoding="utf-8")

    for required_fragment in (
        CANDIDATE_ALIAS_MODEL_ID,
        CANDIDATE_CHECKPOINT,
        EXPECTED_BASE_MODEL,
        "ALIAS_SPECS",
        "available_bindings",
        "def binding_info(model: Optional[str] = None)",
        "def warm_model(model: Optional[str] = None)",
    ):
        require(
            required_fragment in backend_alias_source,
            f"{display_path(backend_alias_provider_path)} is missing required candidate alias fragment: {required_fragment}",
        )

    for required_fragment in (
        "if lv7_alias.is_alias_model(model):",
        "return await lv7_alias.warm_model(model)",
        "if lv7_alias.is_alias_model(req.model):",
    ):
        require(
            required_fragment in backend_ollama_source,
            f"{display_path(backend_ollama_provider_path)} is missing required model-only alias contract fragment: {required_fragment}",
        )

    for required_fragment in (
        "test_binding_info_supports_candidate_alias_and_candidate_identity",
        "test_chat_stream_accepts_candidate_alias_via_existing_model_field",
        "CANDIDATE_ALIAS_MODEL_ID",
        CANDIDATE_CHECKPOINT,
    ):
        require(
            required_fragment in backend_alias_tests,
            f"{display_path(backend_alias_test_path)} is missing required candidate alias coverage fragment: {required_fragment}",
        )

    return {
        "accepted_checkpoint": ACCEPTED_CHECKPOINT,
        "candidate_checkpoint": CANDIDATE_CHECKPOINT,
        "candidate_alias_model_id": CANDIDATE_ALIAS_MODEL_ID,
        "candidate_base_model": EXPECTED_BASE_MODEL,
        "current_exact_eval_passed": current_pass_count,
        "baseline_exact_eval_passed": baseline_pass_count,
        "exact_eval_total": len(scenario_rows),
        "regression_ids": regression_ids,
        "current_runtime_gate_accepts_only_accepted_checkpoint": True,
        "backend_candidate_alias_present": True,
        "backend_request_shape_unchanged": True,
    }


def write_bridge_report(
    *,
    output_path: Path,
    status: str,
    summary: dict[str, Any],
    source_artifacts: dict[str, str],
) -> None:
    lines = [
        "# V1.5.3 Candidate Runtime Recheck Bridge",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- Candidate checkpoint remains `{CANDIDATE_CHECKPOINT}` and is not silently promoted by this milestone.",
        f"- Candidate alias model id is `{CANDIDATE_ALIAS_MODEL_ID}`.",
        f"- Base model remains `{EXPECTED_BASE_MODEL}`.",
        f"- Evidence-only adapters remain `{EVIDENCE_ONLY_SFT_ADAPTERS[0]}` and `{EVIDENCE_ONLY_SFT_ADAPTERS[1]}`.",
        f"- Parked DPO adapters remain `{PARKED_DPO_ADAPTERS[0]}` and `{PARKED_DPO_ADAPTERS[1]}`.",
        "- This milestone is a narrow runtime-trust bridge only. It does not rerun wrapper packaging, regenerate runtime outputs, reopen DPO, or replace the accepted checkpoint.",
        "",
        "## Source Artifacts",
        "",
        *[f"- {label}: `{path}`" for label, path in source_artifacts.items()],
        "",
        "## Bridge Summary",
        "",
        f"- v1.5.2 candidate training status remains `{STATUS_V1_5_2_READY}`.",
        "- Current `v1.4.3` runtime ingestion still hard-gates to the accepted `v1.0.5` checkpoint, so a narrow bridge is still required for the repaired candidate.",
        f"- Candidate exact eval remains `{summary['current_exact_eval_passed']}/{summary['exact_eval_total']}` with no regressions vs accepted `v1.0.5`.",
        f"- Sibling backend alias support now exposes the candidate under `{CANDIDATE_ALIAS_MODEL_ID}` without changing the visible `model`-only request contract.",
        f"- Wrapper/runtime identity remains pinned to artifact `{EXPECTED_ARTIFACT}`, release tag `{EXPECTED_RELEASE_TAG}`, desktop commit `{EXPECTED_DESKTOP_COMMIT}`, backend tag `{EXPECTED_BACKEND_TAG}`.",
        "",
        "## Next Lane",
        "",
        f"- Current milestone status: `{status}`.",
        f"- Next executable milestone: `{NEXT_EXECUTABLE_MILESTONE}`.",
        "- The next step is a truthful runtime rerun for the candidate adapter through the existing wrapper path, using the candidate alias rather than pretending the repaired adapter is the accepted `v1.0.5` checkpoint.",
    ]
    write_report(output_path, lines)


def write_matrix_report(output_path: Path, *, status: str, summary: dict[str, Any]) -> None:
    rows = [
        [
            "candidate_exact_eval",
            "pass" if summary.get("current_exact_eval_passed") == summary.get("exact_eval_total") else "fail",
            f"{summary.get('current_exact_eval_passed')}/{summary.get('exact_eval_total')}",
            "candidate still clears exact eval with no regressions",
        ],
        [
            "runtime_gate_scope",
            "pass" if summary.get("current_runtime_gate_accepts_only_accepted_checkpoint") else "fail",
            "accepted-only",
            "current v1.4.3 analyzer still trusts only the accepted checkpoint identity",
        ],
        [
            "candidate_backend_alias",
            "pass" if summary.get("backend_candidate_alias_present") else "fail",
            CANDIDATE_ALIAS_MODEL_ID,
            "backend alias provider exposes the repaired candidate under the existing model field",
        ],
        [
            "request_shape_contract",
            "pass" if summary.get("backend_request_shape_unchanged") else "fail",
            "model-only",
            "candidate alias path preserves the existing visible chat request contract",
        ],
        [
            "bridge_status",
            "pass" if status == STATUS_READY else "fail",
            status,
            "candidate runtime rerun can proceed only after this bridge is ready",
        ],
    ]
    write_report(
        output_path,
        [
            "# V1.5.3 Runtime Bridge Matrix",
            "",
            render_markdown_table(
                ["check", "status", "observed_value", "notes"],
                rows,
            ),
        ],
    )


def write_decision_report(*, output_path: Path, status: str) -> None:
    lines = [
        "# V1.5.3 Next Step Decision",
        "",
        f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
        f"- Candidate checkpoint remains `{CANDIDATE_CHECKPOINT}` and runtime recheck still requires an explicit bridge rather than a silent promotion.",
    ]
    if status == STATUS_READY:
        lines.extend(
            [
                "- The repaired candidate still clears exact eval with no regressions vs accepted `v1.0.5`.",
                f"- The sibling backend now exposes `{CANDIDATE_ALIAS_MODEL_ID}` under the unchanged `model` field.",
                f"- The next executable milestone is `{NEXT_EXECUTABLE_MILESTONE}`.",
            ]
        )
    else:
        lines.extend(
            [
                "- The candidate runtime recheck bridge is not yet supportable from the checked-in artifacts.",
                "- Resolve the missing trust or backend alias evidence before attempting a candidate runtime rerun.",
            ]
        )
    lines.extend(["", status])
    write_report(output_path, lines)


def analyze_v1_5_3_candidate_runtime_recheck_bridge(
    *,
    v1_5_2_decision_report_path: Path = DEFAULT_V1_5_2_DECISION_REPORT,
    v1_5_2_json_report_path: Path = DEFAULT_V1_5_2_JSON_REPORT,
    v1_4_3a_decision_report_path: Path = DEFAULT_V1_4_3A_DECISION_REPORT,
    v1_4_3a_policy_json_path: Path = DEFAULT_V1_4_3A_POLICY_JSON,
    current_exact_results_path: Path = CURRENT_EXACT_RESULTS_PATH,
    baseline_exact_results_path: Path = BASELINE_EXACT_RESULTS_PATH,
    v1_4_3_analyzer_path: Path = V1_4_3_ANALYZER_PATH,
    backend_alias_provider_path: Path = BACKEND_ALIAS_PROVIDER_PATH,
    backend_ollama_provider_path: Path = BACKEND_OLLAMA_PROVIDER_PATH,
    backend_alias_test_path: Path = BACKEND_ALIAS_TEST_PATH,
    implementation_report_path: Path = DEFAULT_IMPLEMENTATION_REPORT,
    matrix_report_path: Path = DEFAULT_MATRIX_REPORT,
    decision_report_path: Path = DEFAULT_DECISION_REPORT,
    json_report_path: Path = DEFAULT_JSON_REPORT,
) -> dict[str, Any]:
    source_artifacts = {
        "v1_5_2_decision_report_path": display_path(v1_5_2_decision_report_path),
        "v1_5_2_json_report_path": display_path(v1_5_2_json_report_path),
        "v1_4_3a_decision_report_path": display_path(v1_4_3a_decision_report_path),
        "v1_4_3a_policy_json_path": display_path(v1_4_3a_policy_json_path),
        "current_exact_results_path": display_path(current_exact_results_path),
        "baseline_exact_results_path": display_path(baseline_exact_results_path),
        "v1_4_3_analyzer_path": display_path(v1_4_3_analyzer_path),
        "backend_alias_provider_path": display_path(backend_alias_provider_path),
        "backend_ollama_provider_path": display_path(backend_ollama_provider_path),
        "backend_alias_test_path": display_path(backend_alias_test_path),
    }

    status = STATUS_READY
    summary: dict[str, Any] = {}

    try:
        summary = validate_candidate_runtime_bridge(
            v1_5_2_decision_report_path=v1_5_2_decision_report_path,
            v1_5_2_json_report_path=v1_5_2_json_report_path,
            v1_4_3a_decision_report_path=v1_4_3a_decision_report_path,
            v1_4_3a_policy_json_path=v1_4_3a_policy_json_path,
            current_exact_results_path=current_exact_results_path,
            baseline_exact_results_path=baseline_exact_results_path,
            v1_4_3_analyzer_path=v1_4_3_analyzer_path,
            backend_alias_provider_path=backend_alias_provider_path,
            backend_ollama_provider_path=backend_ollama_provider_path,
            backend_alias_test_path=backend_alias_test_path,
        )
    except FileNotFoundError as exc:
        status = STATUS_INCOMPLETE
        summary = {
            "accepted_checkpoint": ACCEPTED_CHECKPOINT,
            "candidate_checkpoint": CANDIDATE_CHECKPOINT,
            "candidate_alias_model_id": CANDIDATE_ALIAS_MODEL_ID,
            "candidate_base_model": EXPECTED_BASE_MODEL,
            "current_exact_eval_passed": 0,
            "baseline_exact_eval_passed": 0,
            "exact_eval_total": 0,
            "regression_ids": [],
            "current_runtime_gate_accepts_only_accepted_checkpoint": False,
            "backend_candidate_alias_present": False,
            "backend_request_shape_unchanged": False,
            "error": str(exc),
        }
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        status = STATUS_INVALID
        summary = {
            "accepted_checkpoint": ACCEPTED_CHECKPOINT,
            "candidate_checkpoint": CANDIDATE_CHECKPOINT,
            "candidate_alias_model_id": CANDIDATE_ALIAS_MODEL_ID,
            "candidate_base_model": EXPECTED_BASE_MODEL,
            "current_exact_eval_passed": 0,
            "baseline_exact_eval_passed": 0,
            "exact_eval_total": 0,
            "regression_ids": [],
            "current_runtime_gate_accepts_only_accepted_checkpoint": False,
            "backend_candidate_alias_present": False,
            "backend_request_shape_unchanged": False,
            "error": str(exc),
        }

    write_bridge_report(
        output_path=implementation_report_path,
        status=status,
        summary=summary,
        source_artifacts=source_artifacts,
    )
    write_matrix_report(matrix_report_path, status=status, summary=summary)
    write_decision_report(output_path=decision_report_path, status=status)

    payload = {
        "milestone": "LV7 v1.5.3",
        "status": status,
        "accepted_checkpoint": ACCEPTED_CHECKPOINT,
        "candidate_checkpoint": CANDIDATE_CHECKPOINT,
        "candidate_alias_model_id": CANDIDATE_ALIAS_MODEL_ID,
        "candidate_base_model": EXPECTED_BASE_MODEL,
        "wrapper_artifact": EXPECTED_ARTIFACT,
        "release_tag": EXPECTED_RELEASE_TAG,
        "desktop_commit": EXPECTED_DESKTOP_COMMIT,
        "backend_tag": EXPECTED_BACKEND_TAG,
        "source_artifact_paths": source_artifacts,
        "current_runtime_gate_accepts_only_accepted_checkpoint": summary.get(
            "current_runtime_gate_accepts_only_accepted_checkpoint", False
        ),
        "candidate_exact_eval_passed": summary.get("current_exact_eval_passed", 0),
        "baseline_exact_eval_passed": summary.get("baseline_exact_eval_passed", 0),
        "exact_eval_total": summary.get("exact_eval_total", 0),
        "regression_ids": summary.get("regression_ids", []),
        "backend_candidate_alias_present": summary.get("backend_candidate_alias_present", False),
        "backend_request_shape_unchanged": summary.get("backend_request_shape_unchanged", False),
        "next_executable_milestone": NEXT_EXECUTABLE_MILESTONE,
    }
    if "error" in summary:
        payload["error"] = summary["error"]
    json_report_path.parent.mkdir(parents=True, exist_ok=True)
    json_report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the candidate runtime recheck bridge for the repaired LV7 adapter."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_5_3_candidate_runtime_recheck_bridge()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
