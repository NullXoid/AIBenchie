from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_4_1_external_m6_runtime_eval import (
    ACCEPTED_CHECKPOINT,
    EXPECTED_ARTIFACT,
    EXPECTED_BACKEND_TAG,
    EXPECTED_DESKTOP_COMMIT,
    EXPECTED_RELEASE_TAG,
)
from training.analyze_v1_4_6_policy_rationale_contract_fix_implementation import (
    APPROVED_STATUSES,
    DEFAULT_JSON_REPORT,
    GENERIC_QWEN_TEMPLATE_SHA256,
    IMPLEMENTATION_SURFACE,
    NEXT_EXECUTABLE_MILESTONE,
    STATUS_INSUFFICIENT,
    STATUS_READY,
    TARGET_SCENARIO_IDS,
    analyze_v1_4_6_policy_rationale_contract_fix_implementation,
)


REPORTS_RUNTIME_DIR = ROOT / "reports" / "runtime"
REPORTS_TRAINING_DIR = ROOT / "reports" / "training"
SUITE_MANIFEST_PATH = REPORTS_RUNTIME_DIR / "v1_4_2_runtime_suite_manifest.json"
ACCEPTANCE_REPORT_PATH = REPORTS_RUNTIME_DIR / "V1_4_2_SCENARIO_ACCEPTANCE_CRITERIA.md"


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def last_nonempty_line(path: Path) -> str:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][-1]


def build_base_records() -> list[dict[str, object]]:
    suite_manifest = read_json(SUITE_MANIFEST_PATH)
    records: list[dict[str, object]] = []
    for scenario_id in suite_manifest["scenario_ids"]:
        records.append(
            {
                "suite_id": suite_manifest["suite_id"],
                "scenario_id": scenario_id,
                "scenario_file": suite_manifest["scenario_files"][scenario_id],
                "scenario_sha256": suite_manifest["scenario_sha256"][scenario_id],
                "prompt_sha256": suite_manifest["prompt_sha256"][scenario_id],
                "model_adapter_path": ACCEPTED_CHECKPOINT,
                "wrapper_artifact": EXPECTED_ARTIFACT,
                "release_tag": EXPECTED_RELEASE_TAG,
                "desktop_commit": EXPECTED_DESKTOP_COMMIT,
                "backend_tag": EXPECTED_BACKEND_TAG,
                "backend_commit": "1b990260e10eaaf34550f4c13abfb92f66073d68",
                "raw_model_text": (
                    "policy_rationale:\n"
                    "  mode: challenge\n"
                    "  risk_assessment: Keep the action bounded.\n"
                    "  authority_boundary: Stay inside the declared scope.\n"
                    "  safe_next_move: Provide the safe next step.\n\n"
                    "response:\n"
                    "I will keep the action bounded and audit-ready."
                ),
                "final_emitted_text": (
                    "policy_rationale:\n"
                    "  mode: challenge\n"
                    "  risk_assessment: Keep the action bounded.\n"
                    "  authority_boundary: Stay inside the declared scope.\n"
                    "  safe_next_move: Provide the safe next step.\n\n"
                    "response:\n"
                    "I will keep the action bounded and audit-ready."
                ),
                "policy_rationale_visible": True,
                "fenced_nullxoid_signal_present": False,
                "nullxoid_signal_stripped": True,
                "policy_rationale_parsed_as_metadata": False,
                "pass1_state": "completed",
                "gate_decision": "not_required",
                "pass2_state": "not_run",
                "timeout_observed": False,
                "cancel_observed": False,
                "fallback_used": False,
                "final_outcome": "pass",
                "wrapper_contract_failures": [],
                "model_contract_failures": [],
                "executed_at": "2026-04-22T14:04:53.493Z",
            }
        )
    return records


def write_runtime_bundle(runtime_dir: Path, *, records: list[dict[str, object]]) -> None:
    write_jsonl(runtime_dir / "v1_4_runtime_outputs.jsonl", records)
    write_markdown(
        runtime_dir / "V1_4_RUNTIME_EVAL_RESULTS.md",
        [
            "# V1.4 Runtime Eval Results",
            "",
            "- suite_id: `lv7_runtime_v1_4`",
            "",
            *[
                "\n".join(
                    [
                        f"## {record['scenario_id']}",
                        "",
                        f"- final_outcome: `{record['final_outcome']}`",
                        "",
                        "```text",
                        str(record["final_emitted_text"]),
                        "```",
                        "",
                    ]
                )
                for record in records
            ],
        ],
    )
    write_json(
        runtime_dir / "v1_4_runtime_execution_manifest.json",
        {
            "suite_id": "lv7_runtime_v1_4",
            "scenario_count": 10,
            "scenario_ids": [record["scenario_id"] for record in records],
            "scenario_sha256": {record["scenario_id"]: record["scenario_sha256"] for record in records},
            "prompt_sha256": {record["scenario_id"]: record["prompt_sha256"] for record in records},
            "model_adapter_path": ACCEPTED_CHECKPOINT,
            "wrapper_artifact": EXPECTED_ARTIFACT,
            "release_tag": EXPECTED_RELEASE_TAG,
            "desktop_commit": EXPECTED_DESKTOP_COMMIT,
            "backend_tag": EXPECTED_BACKEND_TAG,
            "backend_commit": "1b990260e10eaaf34550f4c13abfb92f66073d68",
            "execution_started_at": "2026-04-22T14:04:53.103Z",
            "execution_finished_at": "2026-04-22T14:05:59.462Z",
        },
    )


def write_v1_4_3_gate_files(
    runtime_dir: Path,
    *,
    decision_status: str = "MODEL_RUNTIME_CONTRACT_REPAIR_NEEDED",
    wrapper_review_lines: list[str] | None = None,
) -> None:
    write_markdown(
        runtime_dir / "V1_4_3_NEXT_STEP_DECISION.md",
        [
            "# V1.4.3 Next Step Decision",
            "",
            decision_status,
        ],
    )
    write_markdown(
        runtime_dir / "V1_4_3_WRAPPER_FAILURE_REVIEW.md",
        [
            "# V1.4.3 Wrapper Failure Review",
            "",
            *(wrapper_review_lines or ["- No trusted wrapper/runtime failures were found."]),
        ],
    )


def write_v1_4_5_files(runtime_dir: Path, *, decision_status: str = "V1_4_5_FIX_SPEC_READY") -> None:
    write_markdown(
        runtime_dir / "V1_4_5_NEXT_STEP_DECISION.md",
        [
            "# V1.4.5 Next Step Decision",
            "",
            decision_status,
        ],
    )
    write_json(
        runtime_dir / "v1_4_5_policy_rationale_fix_spec.json",
        {
            "milestone": "LV7 v1.4.5",
            "status": "V1_4_5_FIX_SPEC_READY",
            "accepted_checkpoint": ACCEPTED_CHECKPOINT,
            "targeted_scenarios": list(TARGET_SCENARIO_IDS),
            "shared_fix_surface": "PROMPT_TEMPLATE_FIX",
            "scenarios": [
                {
                    "scenario_id": scenario_id,
                    "missing_or_invalid_elements": [
                        "policy_rationale block missing",
                        "mode missing",
                        "risk_assessment missing",
                        "authority_boundary missing",
                        "safe_next_move missing",
                        "response section missing",
                    ],
                }
                for scenario_id in TARGET_SCENARIO_IDS
            ],
        },
    )


def run_analysis(
    runtime_dir: Path,
    *,
    chat_template_path: Path | None = None,
    prompt_reference_path: Path | None = None,
) -> dict[str, object]:
    return analyze_v1_4_6_policy_rationale_contract_fix_implementation(
        runtime_outputs_path=runtime_dir / "v1_4_runtime_outputs.jsonl",
        runtime_results_report_path=runtime_dir / "V1_4_RUNTIME_EVAL_RESULTS.md",
        runtime_execution_manifest_path=runtime_dir / "v1_4_runtime_execution_manifest.json",
        v1_4_3_decision_report_path=runtime_dir / "V1_4_3_NEXT_STEP_DECISION.md",
        v1_4_3_wrapper_failure_review_path=runtime_dir / "V1_4_3_WRAPPER_FAILURE_REVIEW.md",
        v1_4_5_decision_report_path=runtime_dir / "V1_4_5_NEXT_STEP_DECISION.md",
        v1_4_5_json_report_path=runtime_dir / "v1_4_5_policy_rationale_fix_spec.json",
        suite_manifest_json_path=SUITE_MANIFEST_PATH,
        acceptance_report_path=ACCEPTANCE_REPORT_PATH,
        chat_template_path=chat_template_path or (ROOT / "models" / "adapters" / "lv7_sft_smoke_v1_0_5" / "chat_template.jinja"),
        prompt_reference_path=prompt_reference_path or (ROOT / "evals" / "collect_model_outputs.py"),
        freeze_manifest_path=ROOT / "reports" / "training" / "v1_0_5_artifact_manifest.json",
        freeze_markdown_path=ROOT / "reports" / "training" / "V1_0_5_FREEZE.md",
        exact_eval_results_path=ROOT / "reports" / "training" / "v1_0_5_exact_eval_results.jsonl",
        implementation_report_path=runtime_dir / "V1_4_6_POLICY_RATIONALE_IMPLEMENTATION.md",
        matrix_report_path=runtime_dir / "V1_4_6_POLICY_RATIONALE_VALIDATION_MATRIX.md",
        decision_report_path=runtime_dir / "V1_4_6_NEXT_STEP_DECISION.md",
        json_report_path=runtime_dir / "v1_4_6_policy_rationale_contract_fix_implementation.json",
    )


def test_v1_4_6_prerequisite_gate_requires_v1_4_5_ready(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    write_runtime_bundle(runtime_dir, records=build_base_records())
    write_v1_4_3_gate_files(runtime_dir)
    write_v1_4_5_files(runtime_dir, decision_status="V1_4_5_FIX_SPEC_INSUFFICIENT")

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_INSUFFICIENT
    assert last_nonempty_line(runtime_dir / "V1_4_6_NEXT_STEP_DECISION.md") == STATUS_INSUFFICIENT


def test_v1_4_6_prerequisite_gate_requires_v1_4_3_model_repair_status(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    write_runtime_bundle(runtime_dir, records=build_base_records())
    write_v1_4_3_gate_files(runtime_dir, decision_status="RUNTIME_EVAL_PASSED")
    write_v1_4_5_files(runtime_dir)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_INSUFFICIENT
    assert last_nonempty_line(runtime_dir / "V1_4_6_NEXT_STEP_DECISION.md") == STATUS_INSUFFICIENT


def test_v1_4_6_prerequisite_gate_requires_empty_wrapper_review(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    write_runtime_bundle(runtime_dir, records=build_base_records())
    write_v1_4_3_gate_files(
        runtime_dir,
        wrapper_review_lines=["## unsafe_shortcut_runtime_001", "", "- pass gating wrong"],
    )
    write_v1_4_5_files(runtime_dir)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_INSUFFICIENT
    assert last_nonempty_line(runtime_dir / "V1_4_6_NEXT_STEP_DECISION.md") == STATUS_INSUFFICIENT


def test_v1_4_6_missing_runtime_package_inputs_fail_closed(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    write_v1_4_3_gate_files(runtime_dir)
    write_v1_4_5_files(runtime_dir)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_INSUFFICIENT
    assert last_nonempty_line(runtime_dir / "V1_4_6_NEXT_STEP_DECISION.md") == STATUS_INSUFFICIENT


def test_v1_4_6_template_must_encode_lv7_contract(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    write_runtime_bundle(runtime_dir, records=build_base_records())
    write_v1_4_3_gate_files(runtime_dir)
    write_v1_4_5_files(runtime_dir)

    generic_template = tmp_path / "chat_template.jinja"
    generic_template.write_text(
        "{%- if messages[0]['role'] == 'system' %}{{ messages[0]['content'] }}{%- else %}You are Qwen, created by Alibaba Cloud. You are a helpful assistant.{%- endif %}\n",
        encoding="utf-8",
    )

    summary = run_analysis(runtime_dir, chat_template_path=generic_template)

    assert summary["status"] == STATUS_INSUFFICIENT
    assert last_nonempty_line(runtime_dir / "V1_4_6_NEXT_STEP_DECISION.md") == STATUS_INSUFFICIENT


def test_v1_4_6_analyzer_source_avoids_wrapper_invocation_subprocess_training_and_score_regeneration():
    source = (
        ROOT / "training" / "analyze_v1_4_6_policy_rationale_contract_fix_implementation.py"
    ).read_text(encoding="utf-8")

    banned_fragments = [
        "subprocess",
        "Popen(",
        "ControllerFacade",
        "NullXoidBackendBridge",
        "train_sft_qlora",
        "run_dpo_smoke",
        "score_response(",
    ]
    for fragment in banned_fragments:
        assert fragment not in source, f"Analyzer should not reference forbidden execution path: {fragment}"


def test_v1_4_6_current_workspace_artifacts_support_ready_implementation():
    required = [
        ROOT / "training" / "analyze_v1_4_6_policy_rationale_contract_fix_implementation.py",
        ROOT / "models" / "adapters" / "lv7_sft_smoke_v1_0_5" / "chat_template.jinja",
        ROOT / "evals" / "collect_model_outputs.py",
        ROOT / "reports" / "training" / "v1_0_5_artifact_manifest.json",
        ROOT / "reports" / "training" / "V1_0_5_FREEZE.md",
        ROOT / "reports" / "runtime" / "v1_4_runtime_outputs.jsonl",
        ROOT / "reports" / "runtime" / "V1_4_RUNTIME_EVAL_RESULTS.md",
        ROOT / "reports" / "runtime" / "v1_4_runtime_execution_manifest.json",
        ROOT / "reports" / "runtime" / "V1_4_3_NEXT_STEP_DECISION.md",
        ROOT / "reports" / "runtime" / "V1_4_3_WRAPPER_FAILURE_REVIEW.md",
        ROOT / "reports" / "runtime" / "V1_4_5_NEXT_STEP_DECISION.md",
        ROOT / "reports" / "runtime" / "v1_4_5_policy_rationale_fix_spec.json",
    ]
    for path in required:
        assert path.exists(), f"Missing v1.4.6 prerequisite artifact: {path}"

    summary = analyze_v1_4_6_policy_rationale_contract_fix_implementation()

    assert summary["status"] == STATUS_READY
    assert summary["targeted_scenario_count"] == 5
    assert summary["implementation_surface"] == IMPLEMENTATION_SURFACE
    assert summary["current_template_sha256"] != GENERIC_QWEN_TEMPLATE_SHA256
    assert summary["next_executable_milestone"] == NEXT_EXECUTABLE_MILESTONE
    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_4_6_NEXT_STEP_DECISION.md") in APPROVED_STATUSES
    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_4_6_NEXT_STEP_DECISION.md") == STATUS_READY

    payload = read_json(DEFAULT_JSON_REPORT)
    assert payload["status"] == STATUS_READY
    assert payload["accepted_checkpoint"] == ACCEPTED_CHECKPOINT
    assert payload["implementation_surface"] == IMPLEMENTATION_SURFACE
    assert payload["current_template_sha256"] == summary["current_template_sha256"]
    assert payload["generic_qwen_template_sha256"] == GENERIC_QWEN_TEMPLATE_SHA256
    assert payload["next_executable_milestone"] == NEXT_EXECUTABLE_MILESTONE
    assert len(payload["scenarios"]) == 5
    assert sorted(entry["scenario_id"] for entry in payload["scenarios"]) == sorted(TARGET_SCENARIO_IDS)

    freeze_manifest = read_json(REPORTS_TRAINING_DIR / "v1_0_5_artifact_manifest.json")
    assert (
        freeze_manifest["adapter_files"]["chat_template.jinja"]["sha256"]
        == payload["current_template_sha256"]
    )
    assert (
        freeze_manifest["adapter_files"]["adapter_model.safetensors"]["sha256"]
        == "50b479faffb7cef1f069d71badee944cc07b4be25d834b054aeec309a3a267fb"
    )
