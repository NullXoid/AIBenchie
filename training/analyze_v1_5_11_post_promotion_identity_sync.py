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
    EXPECTED_ARTIFACT,
    EXPECTED_BACKEND_TAG,
    EXPECTED_DESKTOP_COMMIT,
    EXPECTED_RELEASE_TAG,
)
from training.analyze_v1_4_runtime_eval_readiness import (  # noqa: E402
    PROJECT_ROOT,
    last_nonempty_line,
    render_markdown_table,
    write_report,
)
from training.lv7_accepted_runtime_identity import (  # noqa: E402
    ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
    ACCEPTED_RUNTIME_BASE_MODEL,
    ACCEPTED_RUNTIME_CHECKPOINT,
    EVIDENCE_ONLY_SFT_ADAPTERS,
    PARKED_DPO_ADAPTERS,
    PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT,
    PROMOTION_STATUS,
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"
SIBLING_AIASSISTANT_ROOT = PROJECT_ROOT.parent / "AiAssistant"
SIBLING_BACKEND_ROOT = PROJECT_ROOT.parent / "Felnx" / "NullXoid" / ".NullXoid"

DEFAULT_V1_5_10_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_10_NEXT_STEP_DECISION.md"
DEFAULT_V1_5_10_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_10_accepted_runtime_repair_promotion.json"
DEFAULT_HANDOFF_REPORT = SIBLING_AIASSISTANT_ROOT / "reports" / "runtime" / "LV7_RUNTIME_OUTPUT_PACKAGE_HANDOFF.md"
DEFAULT_BACKEND_ALIAS_PROVIDER = SIBLING_BACKEND_ROOT / "backend" / "providers" / "lv7_alias.py"
DEFAULT_BACKEND_MODEL_REGISTRY = SIBLING_BACKEND_ROOT / "system" / "model_registry.json"

DEFAULT_SYNC_REPORT = REPORTS_RUNTIME_DIR / "V1_5_11_POST_PROMOTION_IDENTITY_SYNC.md"
DEFAULT_AUDIT_REPORT = REPORTS_RUNTIME_DIR / "V1_5_11_IDENTITY_REFERENCE_AUDIT.md"
DEFAULT_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_11_NEXT_STEP_DECISION.md"
DEFAULT_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_11_post_promotion_identity_sync.json"

STATUS_COMPLETE = "V1_5_11_IDENTITY_SYNC_COMPLETE"
STATUS_BLOCKED = "V1_5_11_IDENTITY_SYNC_BLOCKED"
APPROVED_STATUSES = {STATUS_COMPLETE, STATUS_BLOCKED}

PREVIOUS_ACCEPTED_RUNTIME_ALIAS_MODEL_ID = "lv7_sft_smoke_v1_0_5:qwen2.5-1.5b-instruct"
PREVIOUS_ACCEPTED_RUNTIME_BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
EXPECTED_BACKEND_COMMIT = "1b990260e10eaaf34550f4c13abfb92f66073d68"
EXPECTED_BACKEND_COMMIT_POLICY = "actual_execution_strictness"
EXPECTED_BACKEND_ANCHOR_COMMIT = "0da516f332fc9689798cdcba19053f3104c8199f"


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check(rows: list[list[str]], item: str, expected: str, observed: Any) -> None:
    observed_str = str(observed)
    result = "pass" if observed_str == expected else "fail"
    rows.append([item, expected, observed_str, result])
    require(result == "pass", f"{item} expected {expected}, observed {observed_str}")


def check_contains(rows: list[list[str]], item: str, expected_fragment: str, text: str) -> None:
    result = "pass" if expected_fragment in text else "fail"
    rows.append([item, expected_fragment, "present" if result == "pass" else "missing", result])
    require(result == "pass", f"{item} missing expected fragment: {expected_fragment}")


def validate_identity_sync(
    *,
    v1_5_10_decision_report_path: Path,
    v1_5_10_json_report_path: Path,
    handoff_report_path: Path,
    backend_alias_provider_path: Path,
    backend_model_registry_path: Path,
) -> dict[str, Any]:
    rows: list[list[str]] = []
    required_paths = [
        v1_5_10_decision_report_path,
        v1_5_10_json_report_path,
        handoff_report_path,
        backend_alias_provider_path,
        backend_model_registry_path,
        PROJECT_ROOT / ACCEPTED_RUNTIME_CHECKPOINT,
        PROJECT_ROOT / PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT,
    ]
    missing = [display_path(path) for path in required_paths if not path.exists()]
    require(not missing, "missing required identity-sync input: " + ", ".join(missing))

    promotion_payload = read_json(v1_5_10_json_report_path)
    backend_provider_text = backend_alias_provider_path.read_text(encoding="utf-8")
    handoff_text = handoff_report_path.read_text(encoding="utf-8")
    registry_payload = read_json(backend_model_registry_path)
    registry_models = [str(item.get("name", "")) for item in registry_payload.get("models", []) if isinstance(item, dict)]

    check(rows, "v1.5.10 decision", PROMOTION_STATUS, last_nonempty_line(v1_5_10_decision_report_path))
    check(rows, "v1.5.10 JSON status", PROMOTION_STATUS, promotion_payload.get("status"))
    check(rows, "promotion complete", "True", promotion_payload.get("promotion_complete"))
    check(rows, "promoted checkpoint", ACCEPTED_RUNTIME_CHECKPOINT, promotion_payload.get("accepted_checkpoint"))
    check(rows, "promoted alias", ACCEPTED_RUNTIME_ALIAS_MODEL_ID, promotion_payload.get("accepted_alias_model_id"))
    check(rows, "promoted base model", ACCEPTED_RUNTIME_BASE_MODEL, promotion_payload.get("accepted_base_model"))
    check(rows, "previous accepted checkpoint preserved", PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT, promotion_payload.get("previous_accepted_checkpoint"))

    check_contains(
        rows,
        "backend accepted alias constant",
        f'ACCEPTED_ALIAS_MODEL_ID = "{ACCEPTED_RUNTIME_ALIAS_MODEL_ID}"',
        backend_provider_text,
    )
    check_contains(
        rows,
        "backend previous alias constant",
        f'PREVIOUS_ACCEPTED_ALIAS_MODEL_ID = "{PREVIOUS_ACCEPTED_RUNTIME_ALIAS_MODEL_ID}"',
        backend_provider_text,
    )
    check_contains(
        rows,
        "backend accepted adapter constant",
        f'ACCEPTED_ADAPTER_PATH = "{ACCEPTED_RUNTIME_CHECKPOINT}"',
        backend_provider_text,
    )
    check_contains(
        rows,
        "backend previous adapter constant",
        f'PREVIOUS_ACCEPTED_ADAPTER_PATH = "{PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT}"',
        backend_provider_text,
    )
    check_contains(rows, "backend default alias points to accepted", "ALIAS_MODEL_ID = ACCEPTED_ALIAS_MODEL_ID", backend_provider_text)

    check(rows, "model registry contains promoted alias", "True", ACCEPTED_RUNTIME_ALIAS_MODEL_ID in registry_models)
    check(rows, "model registry retains previous alias", "True", PREVIOUS_ACCEPTED_RUNTIME_ALIAS_MODEL_ID in registry_models)

    check_contains(
        rows,
        "handoff active accepted checkpoint",
        f"accepted runtime checkpoint: `{ACCEPTED_RUNTIME_CHECKPOINT}`",
        handoff_text,
    )
    check_contains(
        rows,
        "handoff previous checkpoint historical",
        f"previous accepted checkpoint retained as historical evidence: `{PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT}`",
        handoff_text,
    )
    check_contains(
        rows,
        "handoff promoted alias",
        f"alias model id: `{ACCEPTED_RUNTIME_ALIAS_MODEL_ID}`",
        handoff_text,
    )
    check_contains(rows, "handoff v1.5.10 status", "v1.5.10 promotion is complete", handoff_text)

    return {
        "audit_rows": rows,
        "registry_models": registry_models,
    }


def write_sync_report(
    *,
    output_path: Path,
    status: str,
    audit_rows: list[list[str]],
    notes: list[str],
) -> None:
    lines = [
        "# V1.5.11 Post-Promotion Identity Sync",
        "",
        f"- Status: `{status}`",
        f"- Current accepted runtime checkpoint: `{ACCEPTED_RUNTIME_CHECKPOINT}`.",
        f"- Current accepted runtime alias: `{ACCEPTED_RUNTIME_ALIAS_MODEL_ID}`.",
        f"- Previous accepted checkpoint retained as historical evidence: `{PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT}`.",
        f"- Previous backend-visible alias retained for historical compatibility: `{PREVIOUS_ACCEPTED_RUNTIME_ALIAS_MODEL_ID}`.",
        f"- Base model: `{ACCEPTED_RUNTIME_BASE_MODEL}`.",
        f"- Wrapper artifact identity remains `{EXPECTED_ARTIFACT}`.",
        f"- Release tag remains `{EXPECTED_RELEASE_TAG}`.",
        f"- Desktop commit remains `{EXPECTED_DESKTOP_COMMIT}`.",
        f"- Backend tag remains `{EXPECTED_BACKEND_TAG}`.",
        f"- Executing backend commit remains `{EXPECTED_BACKEND_COMMIT}` under `{EXPECTED_BACKEND_COMMIT_POLICY}`.",
        f"- Frozen backend anchor remains `{EXPECTED_BACKEND_ANCHOR_COMMIT}`.",
        "",
        "## Scope",
        "",
        "- This milestone synchronizes forward-looking identity references only.",
        "- It does not reopen SFT, DPO, adapter promotion, scorers, blind suites, or scenario definitions.",
        "- It does not rewrite historical v1.4 or v1.5 evidence that correctly referenced the old accepted checkpoint at the time.",
        "",
        "## Audit",
        "",
        render_markdown_table(["check", "expected", "observed", "result"], audit_rows),
        "",
        "## Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in notes)
    write_report(output_path, lines)


def write_audit_report(*, output_path: Path, audit_rows: list[list[str]]) -> None:
    write_report(
        output_path,
        [
            "# V1.5.11 Identity Reference Audit",
            "",
            render_markdown_table(["check", "expected", "observed", "result"], audit_rows),
        ],
    )


def write_decision_report(*, output_path: Path, status: str) -> None:
    write_report(
        output_path,
        [
            "# V1.5.11 Next Step Decision",
            "",
            f"- Current accepted runtime checkpoint: `{ACCEPTED_RUNTIME_CHECKPOINT}`.",
            f"- Current accepted runtime alias: `{ACCEPTED_RUNTIME_ALIAS_MODEL_ID}`.",
            f"- Previous accepted checkpoint retained as historical evidence: `{PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT}`.",
            "- Forward-looking LV7 and wrapper handoff identity references are synchronized.",
            "- No training, DPO, scorer, blind-suite, or runtime package regeneration is performed by this milestone.",
            "",
            status,
        ],
    )


def analyze_v1_5_11_post_promotion_identity_sync(
    *,
    v1_5_10_decision_report_path: Path = DEFAULT_V1_5_10_DECISION_REPORT,
    v1_5_10_json_report_path: Path = DEFAULT_V1_5_10_JSON_REPORT,
    handoff_report_path: Path = DEFAULT_HANDOFF_REPORT,
    backend_alias_provider_path: Path = DEFAULT_BACKEND_ALIAS_PROVIDER,
    backend_model_registry_path: Path = DEFAULT_BACKEND_MODEL_REGISTRY,
    sync_report_path: Path = DEFAULT_SYNC_REPORT,
    audit_report_path: Path = DEFAULT_AUDIT_REPORT,
    decision_report_path: Path = DEFAULT_DECISION_REPORT,
    json_report_path: Path = DEFAULT_JSON_REPORT,
) -> dict[str, Any]:
    source_artifacts = {
        "v1_5_10_decision_report": display_path(v1_5_10_decision_report_path),
        "v1_5_10_json_report": display_path(v1_5_10_json_report_path),
        "handoff_report": display_path(handoff_report_path),
        "backend_alias_provider": display_path(backend_alias_provider_path),
        "backend_model_registry": display_path(backend_model_registry_path),
    }
    status = STATUS_COMPLETE
    audit_rows: list[list[str]] = []
    notes: list[str] = []
    try:
        summary = validate_identity_sync(
            v1_5_10_decision_report_path=v1_5_10_decision_report_path,
            v1_5_10_json_report_path=v1_5_10_json_report_path,
            handoff_report_path=handoff_report_path,
            backend_alias_provider_path=backend_alias_provider_path,
            backend_model_registry_path=backend_model_registry_path,
        )
        audit_rows = summary["audit_rows"]
        notes.append("forward-looking accepted runtime identity now points to the promoted repair adapter")
        notes.append("previous v1.0.5 identity remains available only as historical compatibility evidence")
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as exc:
        status = STATUS_BLOCKED
        notes.append(str(exc))

    write_sync_report(output_path=sync_report_path, status=status, audit_rows=audit_rows, notes=notes)
    write_audit_report(output_path=audit_report_path, audit_rows=audit_rows)
    write_decision_report(output_path=decision_report_path, status=status)

    payload = {
        "milestone": "LV7 v1.5.11",
        "status": status,
        "current_accepted_runtime_checkpoint": ACCEPTED_RUNTIME_CHECKPOINT if status == STATUS_COMPLETE else None,
        "current_accepted_runtime_alias_model_id": ACCEPTED_RUNTIME_ALIAS_MODEL_ID if status == STATUS_COMPLETE else None,
        "previous_accepted_runtime_checkpoint": PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT,
        "previous_accepted_runtime_alias_model_id": PREVIOUS_ACCEPTED_RUNTIME_ALIAS_MODEL_ID,
        "accepted_base_model": ACCEPTED_RUNTIME_BASE_MODEL,
        "wrapper_artifact": EXPECTED_ARTIFACT,
        "release_tag": EXPECTED_RELEASE_TAG,
        "desktop_commit": EXPECTED_DESKTOP_COMMIT,
        "backend_tag": EXPECTED_BACKEND_TAG,
        "backend_commit": EXPECTED_BACKEND_COMMIT,
        "backend_commit_policy": EXPECTED_BACKEND_COMMIT_POLICY,
        "backend_anchor_commit": EXPECTED_BACKEND_ANCHOR_COMMIT,
        "evidence_only_sft_adapters": list(EVIDENCE_ONLY_SFT_ADAPTERS),
        "parked_dpo_adapters": list(PARKED_DPO_ADAPTERS),
        "source_artifact_paths": source_artifacts,
        "audit_rows": audit_rows,
        "next_recommended_action": (
            "Use the promoted runtime repair checkpoint for future LV7 runtime hardening and release-readiness work."
            if status == STATUS_COMPLETE
            else "Resolve blocked identity sync evidence."
        ),
        "notes": notes,
    }
    json_report_path.parent.mkdir(parents=True, exist_ok=True)
    json_report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synchronize LV7 accepted runtime identity after v1.5.10 promotion.")
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_5_11_post_promotion_identity_sync()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
