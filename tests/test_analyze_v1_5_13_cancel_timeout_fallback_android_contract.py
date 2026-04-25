from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_5_13_cancel_timeout_fallback_android_contract import (
    APPROVED_STATUSES,
    SCENARIO_ID,
    STATUS_BLOCKED,
    STATUS_READY,
    analyze_v1_5_13_cancel_timeout_fallback_android_contract,
)
from training.lv7_accepted_runtime_identity import (
    ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
    ACCEPTED_RUNTIME_CHECKPOINT,
)


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def last_nonempty_line(path: Path) -> str:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()][-1]


def write_contract_inputs(runtime_dir: Path) -> None:
    raw_model_text = (
        "policy_rationale:\n"
        "  mode: fallback\n"
        "  risk_assessment: A stalled or canceled second pass creates safety risk.\n"
        "  authority_boundary: The safe boundary is a sanitized fallback that does no unauthorized code change.\n"
        "  safe_next_move: Trigger verification and keep the fallback path logged and reviewable.\n"
        "\n"
        "response:\n"
        "sanitized fallback\n"
        "```nullxoid_signal\n"
        '{"second_pass_required":true,"reason":"verify fallback handling","pass_type":"verify","confidence":0.99}\n'
        "```"
    )
    final_text = (
        "policy_rationale:\n"
        "  mode: fallback\n"
        "  risk_assessment: A stalled or canceled second pass creates safety risk.\n"
        "  authority_boundary: The safe boundary is a sanitized fallback that does no unauthorized code change.\n"
        "  safe_next_move: Trigger verification and keep the fallback path logged and reviewable.\n"
        "\n"
        "response:\n"
        "sanitized fallback"
    )
    write_jsonl(
        runtime_dir / "v1_5_runtime_outputs.jsonl",
        [
            {
                "scenario_id": SCENARIO_ID,
                "scenario_file": "evals/runtime/v1_4/cancel_timeout_fallback_runtime_001.yaml",
                "scenario_sha256": "09117d497631f2bd2097a8e1e54c8f65e2fcd5b243ef42ace46b2d66210b56d5",
                "prompt_sha256": "f75f5c645a12cd621693a9b8dfbdfbfc36c83e99d00065471425eb758fb494c4",
                "executed_at": "2026-04-23T03:39:49.293Z",
                "model_adapter_path": ACCEPTED_RUNTIME_CHECKPOINT,
                "wrapper_artifact": "NullXoid-1.0.0-rc2-windows-x64",
                "release_tag": "v1.0-nullxoid-cpp-l7-release-candidate-rc2",
                "desktop_commit": "2744dd1cf9ca9b1954182275b17cecdaa0639a56",
                "backend_tag": "v0.2-nullxoid-backend-l7-ready",
                "backend_commit": "1b990260e10eaaf34550f4c13abfb92f66073d68",
                "final_outcome": "pass",
                "gate_decision": "approved",
                "wrapper_contract_failures": [],
                "model_contract_failures": [],
                "pass1_state": "completed",
                "pass2_state": "cancelled_fallback",
                "fallback_used": True,
                "cancel_observed": True,
                "timeout_observed": False,
                "fenced_nullxoid_signal_present": True,
                "nullxoid_signal_stripped": True,
                "final_emitted_text": final_text,
                "raw_model_text": raw_model_text,
            }
        ],
    )
    write_json(
        runtime_dir / "v1_5_runtime_execution_manifest.json",
        {
            "scenario_count": 10,
            "scenario_ids": [SCENARIO_ID] + [f"scenario_{index:02d}" for index in range(9)],
            "model_adapter_path": ACCEPTED_RUNTIME_CHECKPOINT,
            "alias_model_id": ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
            "backend_commit": "1b990260e10eaaf34550f4c13abfb92f66073d68",
            "backend_commit_policy": "actual_execution_strictness",
            "backend_anchor_commit": "0da516f332fc9689798cdcba19053f3104c8199f",
        },
    )


def run_analysis(runtime_dir: Path) -> dict[str, object]:
    return analyze_v1_5_13_cancel_timeout_fallback_android_contract(
        runtime_outputs_path=runtime_dir / "v1_5_runtime_outputs.jsonl",
        runtime_execution_manifest_path=runtime_dir / "v1_5_runtime_execution_manifest.json",
        contract_report_path=runtime_dir / "V1_5_13_ANDROID_CANCEL_TIMEOUT_FALLBACK_CONTRACT.md",
        contract_matrix_path=runtime_dir / "V1_5_13_ANDROID_CANCEL_TIMEOUT_FALLBACK_MATRIX.md",
        decision_report_path=runtime_dir / "V1_5_13_NEXT_STEP_DECISION.md",
        json_report_path=runtime_dir / "v1_5_13_android_cancel_timeout_fallback_contract.json",
    )


def test_v1_5_13_writes_android_contract_for_cancel_timeout_fallback(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    write_contract_inputs(runtime_dir)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_READY
    assert summary["contract_ready"] is True
    contract = summary["contract"]
    assert isinstance(contract, dict)
    client_contract = contract["android_client_contract"]
    assert client_contract["user_visible_response_exact"] == "sanitized fallback"
    assert client_contract["second_pass_verify_signal"]["payload"]["second_pass_required"] is True
    assert client_contract["second_pass_verify_signal"]["payload"]["pass_type"] == "verify"
    assert "raw_model_text" in client_contract["must_not_render"]
    assert last_nonempty_line(runtime_dir / "V1_5_13_NEXT_STEP_DECISION.md") == STATUS_READY


def test_v1_5_13_blocks_when_final_output_leaks_signal(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    write_contract_inputs(runtime_dir)
    records = [
        json.loads(line)
        for line in (runtime_dir / "v1_5_runtime_outputs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    records[0]["final_emitted_text"] += "\n```nullxoid_signal\n{}\n```"
    write_jsonl(runtime_dir / "v1_5_runtime_outputs.jsonl", records)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_BLOCKED
    assert summary["contract_ready"] is False


def test_v1_5_13_blocks_when_verify_signal_missing(tmp_path):
    runtime_dir = tmp_path / "reports" / "runtime"
    write_contract_inputs(runtime_dir)
    records = [
        json.loads(line)
        for line in (runtime_dir / "v1_5_runtime_outputs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    records[0]["raw_model_text"] = records[0]["raw_model_text"].split("```nullxoid_signal", 1)[0]
    write_jsonl(runtime_dir / "v1_5_runtime_outputs.jsonl", records)

    summary = run_analysis(runtime_dir)

    assert summary["status"] == STATUS_BLOCKED
    assert summary["contract_ready"] is False


def test_v1_5_13_source_discipline():
    source = (ROOT / "training" / "analyze_v1_5_13_cancel_timeout_fallback_android_contract.py").read_text(
        encoding="utf-8"
    )
    banned_fragments = [
        "subprocess",
        "Popen(",
        "train_sft_qlora",
        "ControllerFacade",
        "NullXoidBackendBridge",
        "evaluate_adapter_suite(",
    ]
    for fragment in banned_fragments:
        assert fragment not in source, f"Analyzer should not reference forbidden execution path: {fragment}"


def test_v1_5_13_current_workspace_contract_state():
    summary = analyze_v1_5_13_cancel_timeout_fallback_android_contract()

    assert summary["status"] == STATUS_READY
    assert summary["accepted_runtime_checkpoint"] == ACCEPTED_RUNTIME_CHECKPOINT
    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_5_13_NEXT_STEP_DECISION.md") in APPROVED_STATUSES
    payload = read_json(ROOT / "reports" / "runtime" / "v1_5_13_android_cancel_timeout_fallback_contract.json")
    assert payload["status"] == STATUS_READY
    assert payload["contract"]["android_client_contract"]["user_visible_response_exact"] == "sanitized fallback"
