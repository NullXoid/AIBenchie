from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_5_12_promoted_runtime_release_readiness import (
    APPROVED_STATUSES,
    PREVIOUS_ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
    STATUS_BLOCKED,
    STATUS_READY,
    analyze_v1_5_12_promoted_runtime_release_readiness,
)
from training.lv7_accepted_runtime_identity import (
    ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
    ACCEPTED_RUNTIME_CHECKPOINT,
    PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT,
)


def last_nonempty_line(path: Path) -> str:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()][-1]


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def write_readiness_inputs(root: Path) -> dict[str, Path]:
    runtime_dir = root / "reports" / "runtime"
    handoff = root / "AiAssistant" / "reports" / "runtime" / "LV7_RUNTIME_OUTPUT_PACKAGE_HANDOFF.md"
    provider = root / "backend" / "providers" / "lv7_alias.py"
    registry = root / "system" / "model_registry.json"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    provider.parent.mkdir(parents=True, exist_ok=True)
    registry.parent.mkdir(parents=True, exist_ok=True)
    (root / ACCEPTED_RUNTIME_CHECKPOINT).mkdir(parents=True, exist_ok=True)
    (root / PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT).mkdir(parents=True, exist_ok=True)

    (runtime_dir / "V1_5_10_NEXT_STEP_DECISION.md").write_text(
        "# V1.5.10 Decision\n\nV1_5_10_PROMOTION_COMPLETE\n",
        encoding="utf-8",
    )
    (runtime_dir / "V1_5_11_NEXT_STEP_DECISION.md").write_text(
        "# V1.5.11 Decision\n\nV1_5_11_IDENTITY_SYNC_COMPLETE\n",
        encoding="utf-8",
    )
    write_json(
        runtime_dir / "v1_5_10_accepted_runtime_repair_promotion.json",
        {
            "status": "V1_5_10_PROMOTION_COMPLETE",
            "accepted_checkpoint": ACCEPTED_RUNTIME_CHECKPOINT,
            "accepted_alias_model_id": ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
        },
    )
    write_json(
        runtime_dir / "v1_5_11_post_promotion_identity_sync.json",
        {
            "status": "V1_5_11_IDENTITY_SYNC_COMPLETE",
            "current_accepted_runtime_checkpoint": ACCEPTED_RUNTIME_CHECKPOINT,
            "current_accepted_runtime_alias_model_id": ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
            "previous_accepted_runtime_checkpoint": PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT,
        },
    )
    write_json(
        runtime_dir / "v1_5_4_candidate_runtime_results_ingestion.json",
        {
            "status": "V1_5_4_CANDIDATE_RUNTIME_PASSED",
        },
    )
    scenario_ids = [f"scenario_{index:02d}" for index in range(10)]
    records = [
        {
            "scenario_id": scenario_id,
            "model_adapter_path": ACCEPTED_RUNTIME_CHECKPOINT,
            "wrapper_artifact": "NullXoid-1.0.0-rc2-windows-x64",
            "release_tag": "v1.0-nullxoid-cpp-l7-release-candidate-rc2",
            "desktop_commit": "2744dd1cf9ca9b1954182275b17cecdaa0639a56",
            "backend_tag": "v0.2-nullxoid-backend-l7-ready",
            "backend_commit": "1b990260e10eaaf34550f4c13abfb92f66073d68",
            "final_outcome": "pass",
            "wrapper_contract_failures": [],
            "model_contract_failures": [],
        }
        for scenario_id in scenario_ids
    ]
    write_jsonl(runtime_dir / "v1_5_runtime_outputs.jsonl", records)
    write_json(
        runtime_dir / "v1_5_runtime_execution_manifest.json",
        {
            "scenario_count": 10,
            "scenario_ids": scenario_ids,
            "model_adapter_path": ACCEPTED_RUNTIME_CHECKPOINT,
            "alias_model_id": ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
            "backend_commit": "1b990260e10eaaf34550f4c13abfb92f66073d68",
            "backend_commit_policy": "actual_execution_strictness",
            "backend_anchor_commit": "0da516f332fc9689798cdcba19053f3104c8199f",
        },
    )
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        f"- accepted runtime checkpoint: `{ACCEPTED_RUNTIME_CHECKPOINT}`\n",
        encoding="utf-8",
    )
    provider.write_text(
        "\n".join(
            [
                f'ACCEPTED_ALIAS_MODEL_ID = "{ACCEPTED_RUNTIME_ALIAS_MODEL_ID}"',
                "ALIAS_MODEL_ID = ACCEPTED_ALIAS_MODEL_ID",
                f'ACCEPTED_ADAPTER_PATH = "{ACCEPTED_RUNTIME_CHECKPOINT}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_json(
        registry,
        {
            "models": [
                {"name": ACCEPTED_RUNTIME_ALIAS_MODEL_ID},
                {"name": PREVIOUS_ACCEPTED_RUNTIME_ALIAS_MODEL_ID},
            ]
        },
    )
    return {
        "runtime_dir": runtime_dir,
        "handoff": handoff,
        "provider": provider,
        "registry": registry,
    }


def run_analysis(paths: dict[str, Path]) -> dict[str, object]:
    runtime_dir = paths["runtime_dir"]
    return analyze_v1_5_12_promoted_runtime_release_readiness(
        v1_5_10_decision_report_path=runtime_dir / "V1_5_10_NEXT_STEP_DECISION.md",
        v1_5_10_json_report_path=runtime_dir / "v1_5_10_accepted_runtime_repair_promotion.json",
        v1_5_11_decision_report_path=runtime_dir / "V1_5_11_NEXT_STEP_DECISION.md",
        v1_5_11_json_report_path=runtime_dir / "v1_5_11_post_promotion_identity_sync.json",
        v1_5_4_json_report_path=runtime_dir / "v1_5_4_candidate_runtime_results_ingestion.json",
        runtime_outputs_path=runtime_dir / "v1_5_runtime_outputs.jsonl",
        runtime_execution_manifest_path=runtime_dir / "v1_5_runtime_execution_manifest.json",
        handoff_report_path=paths["handoff"],
        backend_alias_provider_path=paths["provider"],
        backend_model_registry_path=paths["registry"],
        readiness_report_path=runtime_dir / "V1_5_12_PROMOTED_RUNTIME_RELEASE_READINESS.md",
        readiness_matrix_path=runtime_dir / "V1_5_12_RELEASE_READINESS_MATRIX.md",
        decision_report_path=runtime_dir / "V1_5_12_NEXT_STEP_DECISION.md",
        json_report_path=runtime_dir / "v1_5_12_promoted_runtime_release_readiness.json",
    )


def test_v1_5_12_marks_promoted_baseline_ready(tmp_path):
    paths = write_readiness_inputs(tmp_path)

    summary = run_analysis(paths)

    assert summary["status"] == STATUS_READY
    assert summary["release_baseline_ready"] is True
    assert summary["accepted_runtime_checkpoint"] == ACCEPTED_RUNTIME_CHECKPOINT
    assert summary["runtime_record_count"] == 10
    assert summary["runtime_pass_count"] == 10
    assert last_nonempty_line(paths["runtime_dir"] / "V1_5_12_NEXT_STEP_DECISION.md") == STATUS_READY


def test_v1_5_12_blocks_when_identity_sync_not_complete(tmp_path):
    paths = write_readiness_inputs(tmp_path)
    (paths["runtime_dir"] / "V1_5_11_NEXT_STEP_DECISION.md").write_text(
        "# V1.5.11 Decision\n\nV1_5_11_IDENTITY_SYNC_BLOCKED\n",
        encoding="utf-8",
    )

    summary = run_analysis(paths)

    assert summary["status"] == STATUS_BLOCKED


def test_v1_5_12_blocks_runtime_failure(tmp_path):
    paths = write_readiness_inputs(tmp_path)
    runtime_outputs = paths["runtime_dir"] / "v1_5_runtime_outputs.jsonl"
    records = [json.loads(line) for line in runtime_outputs.read_text(encoding="utf-8").splitlines() if line.strip()]
    records[0]["final_outcome"] = "fail"
    records[0]["model_contract_failures"] = ["regression"]
    write_jsonl(runtime_outputs, records)

    summary = run_analysis(paths)

    assert summary["status"] == STATUS_BLOCKED


def test_v1_5_12_source_discipline():
    source = (ROOT / "training" / "analyze_v1_5_12_promoted_runtime_release_readiness.py").read_text(
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


def test_v1_5_12_current_workspace_readiness_state():
    summary = analyze_v1_5_12_promoted_runtime_release_readiness()

    assert summary["status"] == STATUS_READY
    assert summary["accepted_runtime_checkpoint"] == ACCEPTED_RUNTIME_CHECKPOINT
    assert summary["runtime_record_count"] == 10
    assert summary["runtime_pass_count"] == 10
    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_5_12_NEXT_STEP_DECISION.md") in APPROVED_STATUSES
    payload = read_json(ROOT / "reports" / "runtime" / "v1_5_12_promoted_runtime_release_readiness.json")
    assert payload["status"] == STATUS_READY
