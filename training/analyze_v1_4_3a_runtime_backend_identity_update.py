from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_PROJECT_ROOT))

from training.analyze_v1_4_1_external_m6_runtime_eval import (  # noqa: E402
    ACCEPTED_CHECKPOINT,
    EXPECTED_ARTIFACT,
    EXPECTED_BACKEND_COMMIT,
    EXPECTED_BACKEND_TAG,
    EXPECTED_DESKTOP_COMMIT,
    EXPECTED_RELEASE_TAG,
    PROJECT_ROOT,
    STATUS_READY as STATUS_RUNTIME_READY,
    last_nonempty_line,
    write_report,
)
from training.analyze_v1_4_2_runtime_scenario_eval_plan import (  # noqa: E402
    DEFAULT_DECISION_REPORT as DEFAULT_V1_4_2_DECISION_REPORT,
    STATUS_PLAN_READY,
)
from training.analyze_v1_4_3_runtime_scenario_results import (  # noqa: E402
    DEFAULT_DECISION_REPORT as DEFAULT_V1_4_3_DECISION_REPORT,
    STATUS_INCOMPLETE as STATUS_RUNTIME_RESULTS_INCOMPLETE,
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"
SIBLING_CPP_PROJECT_ROOT = PROJECT_ROOT.parent / "AiAssistant"

DEFAULT_V1_4_1_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_4_1_NEXT_STEP_DECISION.md"
DEFAULT_V1_4_3A_REPORT = REPORTS_RUNTIME_DIR / "V1_4_3A_BACKEND_IDENTITY_TRUST_UPDATE.md"
DEFAULT_V1_4_3A_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_4_3A_NEXT_STEP_DECISION.md"
DEFAULT_V1_4_3A_POLICY_JSON = REPORTS_RUNTIME_DIR / "v1_4_3a_backend_identity_policy.json"

DEFAULT_M21_MANIFEST_JSON = SIBLING_CPP_PROJECT_ROOT / "reports" / "runtime" / "m21_lv7_model_alias_manifest.json"
DEFAULT_M21_DECISION_REPORT = SIBLING_CPP_PROJECT_ROOT / "docs" / "M21_NEXT_STEP_DECISION.md"
DEFAULT_M22_DECISION_JSON = SIBLING_CPP_PROJECT_ROOT / "reports" / "runtime" / "m22_backend_commit_identity_decision.json"
DEFAULT_M22_DECISION_REPORT = SIBLING_CPP_PROJECT_ROOT / "docs" / "M22_NEXT_STEP_DECISION.md"

STATUS_POLICY_READY = "RUNTIME_BACKEND_IDENTITY_POLICY_READY"
STATUS_POLICY_INCOMPLETE = "RUNTIME_BACKEND_IDENTITY_POLICY_INCOMPLETE"
STATUS_POLICY_INVALID = "RUNTIME_BACKEND_IDENTITY_POLICY_INVALID"

APPROVED_STATUSES = {
    STATUS_POLICY_READY,
    STATUS_POLICY_INCOMPLETE,
    STATUS_POLICY_INVALID,
}

EXPECTED_M21_STATUS = "M21_READY_FOR_RUNTIME_OUTPUT_PACKAGE"
EXPECTED_M22_STATUS = "M22_USE_ACTUAL_BACKEND_COMMIT_POLICY"
EXPECTED_POLICY_NAME = "actual_execution_strictness"
EXPECTED_ALIAS_MODEL_ID = "lv7_sft_smoke_v1_0_5:qwen2.5-1.5b-instruct"
EXPECTED_ACCEPTED_BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat()


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_lv7_prerequisites(
    *,
    v1_4_1_decision_report_path: Path,
    v1_4_2_decision_report_path: Path,
    v1_4_3_decision_report_path: Path,
) -> None:
    required = [
        v1_4_1_decision_report_path,
        v1_4_2_decision_report_path,
        v1_4_3_decision_report_path,
    ]
    missing = [display_path(path) for path in required if not path.exists()]
    require(not missing, f"missing LV7 runtime reports: {', '.join(missing)}")
    require(
        last_nonempty_line(v1_4_1_decision_report_path) == STATUS_RUNTIME_READY,
        f"{display_path(v1_4_1_decision_report_path)} does not end with {STATUS_RUNTIME_READY}",
    )
    require(
        last_nonempty_line(v1_4_2_decision_report_path) == STATUS_PLAN_READY,
        f"{display_path(v1_4_2_decision_report_path)} does not end with {STATUS_PLAN_READY}",
    )
    require(
        last_nonempty_line(v1_4_3_decision_report_path) == STATUS_RUNTIME_RESULTS_INCOMPLETE,
        f"{display_path(v1_4_3_decision_report_path)} does not end with {STATUS_RUNTIME_RESULTS_INCOMPLETE}",
    )
    require(
        (PROJECT_ROOT / ACCEPTED_CHECKPOINT).exists(),
        f"accepted checkpoint is missing: {ACCEPTED_CHECKPOINT}",
    )


def validate_m21_manifest(payload: dict[str, Any], *, source_path: Path) -> None:
    require(payload.get("status") == EXPECTED_M21_STATUS, f"{display_path(source_path)} has wrong M21 status")
    require(payload.get("alias_model_id") == EXPECTED_ALIAS_MODEL_ID, f"{display_path(source_path)} has wrong alias_model_id")
    require(payload.get("accepted_adapter_path") == ACCEPTED_CHECKPOINT, f"{display_path(source_path)} has wrong accepted_adapter_path")
    require(payload.get("accepted_base_model") == EXPECTED_ACCEPTED_BASE_MODEL, f"{display_path(source_path)} has wrong accepted_base_model")
    require(payload.get("wrapper_artifact") == EXPECTED_ARTIFACT, f"{display_path(source_path)} has wrong wrapper_artifact")
    require(payload.get("release_tag") == EXPECTED_RELEASE_TAG, f"{display_path(source_path)} has wrong release_tag")
    require(payload.get("desktop_commit") == EXPECTED_DESKTOP_COMMIT, f"{display_path(source_path)} has wrong desktop_commit")
    require(payload.get("backend_tag") == EXPECTED_BACKEND_TAG, f"{display_path(source_path)} has wrong backend_tag")
    actual_backend_commit = payload.get("backend_commit")
    require(isinstance(actual_backend_commit, str) and actual_backend_commit.strip(), f"{display_path(source_path)} is missing backend_commit")
    require(
        payload.get("backend_anchor_commit") == EXPECTED_BACKEND_COMMIT,
        f"{display_path(source_path)} has wrong backend_anchor_commit",
    )
    require(payload.get("models_endpoint_exposes_alias") is True, f"{display_path(source_path)} does not prove alias visibility")
    require(payload.get("chat_stream_accepts_alias") is True, f"{display_path(source_path)} does not prove chat_stream alias execution")
    require(
        payload.get("request_shape_changed") is False,
        f"{display_path(source_path)} indicates request-shape drift",
    )
    require(payload.get("lv7_runtime_outputs_written") is False, f"{display_path(source_path)} indicates premature LV7 runtime outputs")


def validate_m22_decision(payload: dict[str, Any], *, source_path: Path) -> None:
    require(payload.get("status") == EXPECTED_M22_STATUS, f"{display_path(source_path)} has wrong M22 status")
    require(
        payload.get("wrapper_artifact") == EXPECTED_ARTIFACT,
        f"{display_path(source_path)} has wrong wrapper_artifact",
    )
    require(payload.get("release_tag") == EXPECTED_RELEASE_TAG, f"{display_path(source_path)} has wrong release_tag")
    require(
        payload.get("desktop_commit") == EXPECTED_DESKTOP_COMMIT,
        f"{display_path(source_path)} has wrong desktop_commit",
    )
    require(payload.get("backend_tag") == EXPECTED_BACKEND_TAG, f"{display_path(source_path)} has wrong backend_tag")
    require(
        payload.get("frozen_anchor_backend_commit") == EXPECTED_BACKEND_COMMIT,
        f"{display_path(source_path)} has wrong frozen_anchor_backend_commit",
    )
    require(
        payload.get("accepted_adapter_path") == ACCEPTED_CHECKPOINT,
        f"{display_path(source_path)} has wrong accepted_adapter_path",
    )
    require(payload.get("accepted_base_model") == EXPECTED_ACCEPTED_BASE_MODEL, f"{display_path(source_path)} has wrong accepted_base_model")
    require(payload.get("alias_model_id") == EXPECTED_ALIAS_MODEL_ID, f"{display_path(source_path)} has wrong alias_model_id")
    require(
        payload.get("selected_policy", {}).get("name") == EXPECTED_POLICY_NAME,
        f"{display_path(source_path)} has wrong selected policy",
    )
    require(
        payload.get("current_lv7_v143_requires_anchor_commit") is True,
        f"{display_path(source_path)} does not confirm current anchor-strict LV7 state",
    )
    require(
        payload.get("runtime_outputs_allowed_now") is False,
        f"{display_path(source_path)} incorrectly allows runtime outputs before LV7 trust update",
    )


def analyze_v1_4_3a_runtime_backend_identity_update(
    *,
    v1_4_1_decision_report_path: Path = DEFAULT_V1_4_1_DECISION_REPORT,
    v1_4_2_decision_report_path: Path = DEFAULT_V1_4_2_DECISION_REPORT,
    v1_4_3_decision_report_path: Path = DEFAULT_V1_4_3_DECISION_REPORT,
    m21_manifest_json_path: Path = DEFAULT_M21_MANIFEST_JSON,
    m21_decision_report_path: Path = DEFAULT_M21_DECISION_REPORT,
    m22_decision_json_path: Path = DEFAULT_M22_DECISION_JSON,
    m22_decision_report_path: Path = DEFAULT_M22_DECISION_REPORT,
    trust_update_report_path: Path = DEFAULT_V1_4_3A_REPORT,
    decision_report_path: Path = DEFAULT_V1_4_3A_DECISION_REPORT,
    backend_identity_policy_json_path: Path = DEFAULT_V1_4_3A_POLICY_JSON,
) -> dict[str, Any]:
    try:
        load_lv7_prerequisites(
            v1_4_1_decision_report_path=v1_4_1_decision_report_path,
            v1_4_2_decision_report_path=v1_4_2_decision_report_path,
            v1_4_3_decision_report_path=v1_4_3_decision_report_path,
        )
    except ValueError as exc:
        status = STATUS_POLICY_INVALID
        notes = [str(exc)]
        write_report(
            trust_update_report_path,
            [
                "# V1.4.3a Backend Identity Trust Update",
                "",
                "## Review Notes",
                "",
                *[f"- {note}" for note in notes],
                "",
                f"- current status: `{status}`",
            ],
        )
        write_report(
            decision_report_path,
            ["# V1.4.3a Next Step Decision", "", *[f"- {note}" for note in notes], "", status],
        )
        return {"status": status, "policy_written": False}

    required_external = [
        m21_manifest_json_path,
        m21_decision_report_path,
        m22_decision_json_path,
        m22_decision_report_path,
    ]
    missing = [display_path(path) for path in required_external if not path.exists()]
    if missing:
        status = STATUS_POLICY_INCOMPLETE
        notes = [f"missing external backend-identity evidence: {', '.join(missing)}"]
        write_report(
            trust_update_report_path,
            [
                "# V1.4.3a Backend Identity Trust Update",
                "",
                "- This bridge pins external M21/M22 backend identity evidence into the LV7 repo.",
                "",
                "## Review Notes",
                "",
                *[f"- {note}" for note in notes],
                "",
                f"- current status: `{status}`",
            ],
        )
        write_report(
            decision_report_path,
            ["# V1.4.3a Next Step Decision", "", *[f"- {note}" for note in notes], "", status],
        )
        return {"status": status, "policy_written": False}

    try:
        require(
            last_nonempty_line(m21_decision_report_path) == EXPECTED_M21_STATUS,
            f"{display_path(m21_decision_report_path)} does not end with {EXPECTED_M21_STATUS}",
        )
        require(
            last_nonempty_line(m22_decision_report_path) == EXPECTED_M22_STATUS,
            f"{display_path(m22_decision_report_path)} does not end with {EXPECTED_M22_STATUS}",
        )

        m21_manifest = read_json(m21_manifest_json_path)
        m22_decision = read_json(m22_decision_json_path)
        validate_m21_manifest(m21_manifest, source_path=m21_manifest_json_path)
        validate_m22_decision(m22_decision, source_path=m22_decision_json_path)

        actual_backend_commit = m22_decision.get("actual_execution_backend_commit")
        require(
            isinstance(actual_backend_commit, str) and actual_backend_commit.strip(),
            f"{display_path(m22_decision_json_path)} is missing actual_execution_backend_commit",
        )
        require(
            actual_backend_commit == m21_manifest.get("backend_commit"),
            "M21 and M22 disagree about the actual executing backend commit",
        )
        require(
            m22_decision.get("frozen_anchor_backend_commit") == m21_manifest.get("backend_anchor_commit"),
            "M21 and M22 disagree about the frozen anchor backend commit",
        )

    except (json.JSONDecodeError, ValueError) as exc:
        status = STATUS_POLICY_INVALID
        notes = [str(exc)]
        write_report(
            trust_update_report_path,
            [
                "# V1.4.3a Backend Identity Trust Update",
                "",
                "## Review Notes",
                "",
                *[f"- {note}" for note in notes],
                "",
                f"- current status: `{status}`",
            ],
        )
        write_report(
            decision_report_path,
            ["# V1.4.3a Next Step Decision", "", *[f"- {note}" for note in notes], "", status],
        )
        return {"status": status, "policy_written": False}

    policy_payload = {
        "milestone": "LV7 v1.4.3a",
        "status": STATUS_POLICY_READY,
        "selected_policy": EXPECTED_POLICY_NAME,
        "alias_model_id": EXPECTED_ALIAS_MODEL_ID,
        "accepted_adapter_path": ACCEPTED_CHECKPOINT,
        "accepted_base_model": EXPECTED_ACCEPTED_BASE_MODEL,
        "wrapper_artifact": EXPECTED_ARTIFACT,
        "release_tag": EXPECTED_RELEASE_TAG,
        "desktop_commit": EXPECTED_DESKTOP_COMMIT,
        "backend_tag": EXPECTED_BACKEND_TAG,
        "actual_execution_backend_commit": actual_backend_commit,
        "frozen_anchor_backend_commit": EXPECTED_BACKEND_COMMIT,
        "requires_execution_manifest": True,
        "execution_manifest_requirements": {
            "backend_commit_policy": EXPECTED_POLICY_NAME,
            "backend_anchor_commit": EXPECTED_BACKEND_COMMIT,
        },
        "source_m21_manifest": display_path(m21_manifest_json_path),
        "source_m22_decision": display_path(m22_decision_json_path),
        "generated_at": now_iso8601(),
    }
    write_json(backend_identity_policy_json_path, policy_payload)

    notes = [
        f"external M21 alias manifest is present and ends `{EXPECTED_M21_STATUS}`",
        f"external M22 commit identity review is present and ends `{EXPECTED_M22_STATUS}`",
        f"actual executing backend commit is pinned as `{actual_backend_commit}`",
        f"frozen anchor backend commit is preserved as sidecar traceability `{EXPECTED_BACKEND_COMMIT}`",
        "future runtime execution manifests must carry backend_commit_policy=actual_execution_strictness and backend_anchor_commit sidecar evidence",
    ]

    write_report(
        trust_update_report_path,
        [
            "# V1.4.3a Backend Identity Trust Update",
            "",
            f"- Accepted checkpoint remains `{ACCEPTED_CHECKPOINT}`.",
            f"- `v1.4.1` remains `{STATUS_RUNTIME_READY}`.",
            f"- `v1.4.2` remains `{STATUS_PLAN_READY}`.",
            f"- `v1.4.3` remains `{STATUS_RUNTIME_RESULTS_INCOMPLETE}` until truthful runtime outputs are delivered.",
            "- This bridge updates LV7 trust logic so runtime result records can report the actual executing backend commit while preserving the frozen anchor separately as sidecar evidence.",
            "",
            "## Review Notes",
            "",
            *[f"- {note}" for note in notes],
            "",
            "## Local Policy Output",
            "",
            f"- wrote `{display_path(backend_identity_policy_json_path)}`",
            "",
            f"- current status: `{STATUS_POLICY_READY}`",
        ],
    )
    write_report(
        decision_report_path,
        [
            "# V1.4.3a Next Step Decision",
            "",
            *[f"- {note}" for note in notes],
            "",
            STATUS_POLICY_READY,
        ],
    )
    return {
        "status": STATUS_POLICY_READY,
        "policy_written": True,
        "actual_execution_backend_commit": actual_backend_commit,
        "frozen_anchor_backend_commit": EXPECTED_BACKEND_COMMIT,
        "backend_identity_policy_path": display_path(backend_identity_policy_json_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pin external backend identity evidence into the LV7 runtime trust contract."
    )
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_4_3a_runtime_backend_identity_update()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
