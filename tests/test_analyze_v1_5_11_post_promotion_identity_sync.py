from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import ROOT
from training.analyze_v1_5_11_post_promotion_identity_sync import (
    APPROVED_STATUSES,
    PREVIOUS_ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
    STATUS_BLOCKED,
    STATUS_COMPLETE,
    analyze_v1_5_11_post_promotion_identity_sync,
)
from training.lv7_accepted_runtime_identity import (
    ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
    ACCEPTED_RUNTIME_BASE_MODEL,
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


def write_sync_inputs(root: Path) -> dict[str, Path]:
    runtime_dir = root / "reports" / "runtime"
    backend_dir = root / "backend"
    handoff = root / "AiAssistant" / "reports" / "runtime" / "LV7_RUNTIME_OUTPUT_PACKAGE_HANDOFF.md"
    provider = backend_dir / "providers" / "lv7_alias.py"
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
    write_json(
        runtime_dir / "v1_5_10_accepted_runtime_repair_promotion.json",
        {
            "status": "V1_5_10_PROMOTION_COMPLETE",
            "promotion_complete": True,
            "accepted_checkpoint": ACCEPTED_RUNTIME_CHECKPOINT,
            "accepted_alias_model_id": ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
            "accepted_base_model": ACCEPTED_RUNTIME_BASE_MODEL,
            "previous_accepted_checkpoint": PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT,
        },
    )
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "\n".join(
            [
                "# Handoff",
                f"- accepted runtime checkpoint: `{ACCEPTED_RUNTIME_CHECKPOINT}`",
                f"- previous accepted checkpoint retained as historical evidence: `{PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT}`",
                f"- alias model id: `{ACCEPTED_RUNTIME_ALIAS_MODEL_ID}`",
                "- handoff note: the v1.5.10 promotion is complete",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    provider.write_text(
        "\n".join(
            [
                f'PREVIOUS_ACCEPTED_ALIAS_MODEL_ID = "{PREVIOUS_ACCEPTED_RUNTIME_ALIAS_MODEL_ID}"',
                f'ACCEPTED_ALIAS_MODEL_ID = "{ACCEPTED_RUNTIME_ALIAS_MODEL_ID}"',
                "ALIAS_MODEL_ID = ACCEPTED_ALIAS_MODEL_ID",
                f'PREVIOUS_ACCEPTED_ADAPTER_PATH = "{PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT}"',
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
    return analyze_v1_5_11_post_promotion_identity_sync(
        v1_5_10_decision_report_path=runtime_dir / "V1_5_10_NEXT_STEP_DECISION.md",
        v1_5_10_json_report_path=runtime_dir / "v1_5_10_accepted_runtime_repair_promotion.json",
        handoff_report_path=paths["handoff"],
        backend_alias_provider_path=paths["provider"],
        backend_model_registry_path=paths["registry"],
        sync_report_path=runtime_dir / "V1_5_11_POST_PROMOTION_IDENTITY_SYNC.md",
        audit_report_path=runtime_dir / "V1_5_11_IDENTITY_REFERENCE_AUDIT.md",
        decision_report_path=runtime_dir / "V1_5_11_NEXT_STEP_DECISION.md",
        json_report_path=runtime_dir / "v1_5_11_post_promotion_identity_sync.json",
    )


def test_v1_5_11_syncs_forward_identity(tmp_path):
    paths = write_sync_inputs(tmp_path)

    summary = run_analysis(paths)

    assert summary["status"] == STATUS_COMPLETE
    assert summary["current_accepted_runtime_checkpoint"] == ACCEPTED_RUNTIME_CHECKPOINT
    assert summary["current_accepted_runtime_alias_model_id"] == ACCEPTED_RUNTIME_ALIAS_MODEL_ID
    assert summary["previous_accepted_runtime_checkpoint"] == PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT
    assert last_nonempty_line(paths["runtime_dir"] / "V1_5_11_NEXT_STEP_DECISION.md") == STATUS_COMPLETE


def test_v1_5_11_blocks_when_v1_5_10_not_promoted(tmp_path):
    paths = write_sync_inputs(tmp_path)
    (paths["runtime_dir"] / "V1_5_10_NEXT_STEP_DECISION.md").write_text(
        "# V1.5.10 Decision\n\nV1_5_10_PROMOTION_BLOCKED\n",
        encoding="utf-8",
    )

    summary = run_analysis(paths)

    assert summary["status"] == STATUS_BLOCKED


def test_v1_5_11_blocks_stale_backend_accepted_alias(tmp_path):
    paths = write_sync_inputs(tmp_path)
    paths["provider"].write_text(
        "\n".join(
            [
                f'PREVIOUS_ACCEPTED_ALIAS_MODEL_ID = "{PREVIOUS_ACCEPTED_RUNTIME_ALIAS_MODEL_ID}"',
                f'ACCEPTED_ALIAS_MODEL_ID = "{PREVIOUS_ACCEPTED_RUNTIME_ALIAS_MODEL_ID}"',
                "ALIAS_MODEL_ID = ACCEPTED_ALIAS_MODEL_ID",
                f'PREVIOUS_ACCEPTED_ADAPTER_PATH = "{PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT}"',
                f'ACCEPTED_ADAPTER_PATH = "{PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = run_analysis(paths)

    assert summary["status"] == STATUS_BLOCKED


def test_v1_5_11_source_discipline():
    source = (ROOT / "training" / "analyze_v1_5_11_post_promotion_identity_sync.py").read_text(encoding="utf-8")
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


def test_v1_5_11_current_workspace_sync_state():
    summary = analyze_v1_5_11_post_promotion_identity_sync()

    assert summary["status"] == STATUS_COMPLETE
    assert summary["current_accepted_runtime_checkpoint"] == ACCEPTED_RUNTIME_CHECKPOINT
    assert summary["current_accepted_runtime_alias_model_id"] == ACCEPTED_RUNTIME_ALIAS_MODEL_ID
    assert last_nonempty_line(ROOT / "reports" / "runtime" / "V1_5_11_NEXT_STEP_DECISION.md") in APPROVED_STATUSES
    payload = read_json(ROOT / "reports" / "runtime" / "v1_5_11_post_promotion_identity_sync.json")
    assert payload["status"] == STATUS_COMPLETE
