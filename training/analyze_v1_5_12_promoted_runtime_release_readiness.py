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
)


REPORTS_RUNTIME_DIR = PROJECT_ROOT / "reports" / "runtime"
SIBLING_AIASSISTANT_ROOT = PROJECT_ROOT.parent / "AiAssistant"
SIBLING_BACKEND_ROOT = PROJECT_ROOT.parent / "Felnx" / "NullXoid" / ".NullXoid"

DEFAULT_V1_5_10_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_10_NEXT_STEP_DECISION.md"
DEFAULT_V1_5_10_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_10_accepted_runtime_repair_promotion.json"
DEFAULT_V1_5_11_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_11_NEXT_STEP_DECISION.md"
DEFAULT_V1_5_11_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_11_post_promotion_identity_sync.json"
DEFAULT_V1_5_4_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_4_candidate_runtime_results_ingestion.json"
DEFAULT_RUNTIME_OUTPUTS = REPORTS_RUNTIME_DIR / "v1_5_runtime_outputs.jsonl"
DEFAULT_RUNTIME_EXECUTION_MANIFEST = REPORTS_RUNTIME_DIR / "v1_5_runtime_execution_manifest.json"
DEFAULT_HANDOFF_REPORT = SIBLING_AIASSISTANT_ROOT / "reports" / "runtime" / "LV7_RUNTIME_OUTPUT_PACKAGE_HANDOFF.md"
DEFAULT_BACKEND_ALIAS_PROVIDER = SIBLING_BACKEND_ROOT / "backend" / "providers" / "lv7_alias.py"
DEFAULT_BACKEND_MODEL_REGISTRY = SIBLING_BACKEND_ROOT / "system" / "model_registry.json"

DEFAULT_READINESS_REPORT = REPORTS_RUNTIME_DIR / "V1_5_12_PROMOTED_RUNTIME_RELEASE_READINESS.md"
DEFAULT_READINESS_MATRIX = REPORTS_RUNTIME_DIR / "V1_5_12_RELEASE_READINESS_MATRIX.md"
DEFAULT_DECISION_REPORT = REPORTS_RUNTIME_DIR / "V1_5_12_NEXT_STEP_DECISION.md"
DEFAULT_JSON_REPORT = REPORTS_RUNTIME_DIR / "v1_5_12_promoted_runtime_release_readiness.json"

STATUS_READY = "V1_5_12_RELEASE_BASELINE_READY"
STATUS_BLOCKED = "V1_5_12_RELEASE_BASELINE_BLOCKED"
APPROVED_STATUSES = {STATUS_READY, STATUS_BLOCKED}

EXPECTED_V1_5_10_STATUS = "V1_5_10_PROMOTION_COMPLETE"
EXPECTED_V1_5_11_STATUS = "V1_5_11_IDENTITY_SYNC_COMPLETE"
EXPECTED_V1_5_4_STATUS = "V1_5_4_CANDIDATE_RUNTIME_PASSED"
EXPECTED_BACKEND_COMMIT = "1b990260e10eaaf34550f4c13abfb92f66073d68"
EXPECTED_BACKEND_COMMIT_POLICY = "actual_execution_strictness"
EXPECTED_BACKEND_ANCHOR_COMMIT = "0da516f332fc9689798cdcba19053f3104c8199f"
PREVIOUS_ACCEPTED_RUNTIME_ALIAS_MODEL_ID = "lv7_sft_smoke_v1_0_5:qwen2.5-1.5b-instruct"


def display_path(path: Path) -> str:
    try:
        return "<aiassistant-root>/" + str(path.relative_to(SIBLING_AIASSISTANT_ROOT)).replace("\\", "/")
    except ValueError:
        pass
    try:
        return "<wrapper-root>/" + str(path.relative_to(SIBLING_BACKEND_ROOT)).replace("\\", "/")
    except ValueError:
        pass
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check(rows: list[list[str]], item: str, expected: str, observed: Any) -> None:
    observed_str = str(observed)
    result = "pass" if observed_str == expected else "fail"
    rows.append([item, expected, observed_str, result])
    require(result == "pass", f"{item} expected {expected}, observed {observed_str}")


def check_contains(rows: list[list[str]], item: str, expected_fragment: str, text: str) -> None:
    result = "pass" if expected_fragment in text else "fail"
    rows.append([item, expected_fragment, "present" if result == "pass" else "missing", result])
    require(result == "pass", f"{item} missing expected fragment: {expected_fragment}")


def validate_runtime_records(records: list[dict[str, Any]], manifest: dict[str, Any], rows: list[list[str]]) -> None:
    scenario_ids = manifest.get("scenario_ids", [])
    require(isinstance(scenario_ids, list), "execution manifest scenario_ids must be a list")
    check(rows, "runtime record count", "10", len(records))
    check(rows, "manifest scenario count", "10", manifest.get("scenario_count"))
    check(rows, "all records pass", "10", sum(1 for record in records if record.get("final_outcome") == "pass"))
    check(rows, "wrapper failure records", "0", sum(1 for record in records if record.get("wrapper_contract_failures")))
    check(rows, "model failure records", "0", sum(1 for record in records if record.get("model_contract_failures")))
    check(rows, "unique scenario records", "10", len({record.get("scenario_id") for record in records}))
    check(rows, "scenario ids match manifest", "True", sorted(record.get("scenario_id") for record in records) == sorted(scenario_ids))
    for record in records:
        scenario_id = str(record.get("scenario_id"))
        check(rows, f"{scenario_id} adapter identity", ACCEPTED_RUNTIME_CHECKPOINT, record.get("model_adapter_path"))
        check(rows, f"{scenario_id} wrapper artifact", EXPECTED_ARTIFACT, record.get("wrapper_artifact"))
        check(rows, f"{scenario_id} release tag", EXPECTED_RELEASE_TAG, record.get("release_tag"))
        check(rows, f"{scenario_id} desktop commit", EXPECTED_DESKTOP_COMMIT, record.get("desktop_commit"))
        check(rows, f"{scenario_id} backend tag", EXPECTED_BACKEND_TAG, record.get("backend_tag"))
        check(rows, f"{scenario_id} backend commit", EXPECTED_BACKEND_COMMIT, record.get("backend_commit"))


def validate_release_readiness(
    *,
    v1_5_10_decision_report_path: Path,
    v1_5_10_json_report_path: Path,
    v1_5_11_decision_report_path: Path,
    v1_5_11_json_report_path: Path,
    v1_5_4_json_report_path: Path,
    runtime_outputs_path: Path,
    runtime_execution_manifest_path: Path,
    handoff_report_path: Path,
    backend_alias_provider_path: Path,
    backend_model_registry_path: Path,
) -> dict[str, Any]:
    rows: list[list[str]] = []
    required_paths = [
        v1_5_10_decision_report_path,
        v1_5_10_json_report_path,
        v1_5_11_decision_report_path,
        v1_5_11_json_report_path,
        v1_5_4_json_report_path,
        runtime_outputs_path,
        runtime_execution_manifest_path,
        handoff_report_path,
        backend_alias_provider_path,
        backend_model_registry_path,
        PROJECT_ROOT / ACCEPTED_RUNTIME_CHECKPOINT,
        PROJECT_ROOT / PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT,
    ]
    missing = [display_path(path) for path in required_paths if not path.exists()]
    require(not missing, "missing required release-readiness input: " + ", ".join(missing))

    v1_5_10 = read_json(v1_5_10_json_report_path)
    v1_5_11 = read_json(v1_5_11_json_report_path)
    v1_5_4 = read_json(v1_5_4_json_report_path)
    manifest = read_json(runtime_execution_manifest_path)
    records = read_jsonl(runtime_outputs_path)
    backend_provider_text = backend_alias_provider_path.read_text(encoding="utf-8")
    handoff_text = handoff_report_path.read_text(encoding="utf-8")
    registry_payload = read_json(backend_model_registry_path)
    registry_models = [str(item.get("name", "")) for item in registry_payload.get("models", []) if isinstance(item, dict)]

    check(rows, "v1.5.10 decision", EXPECTED_V1_5_10_STATUS, last_nonempty_line(v1_5_10_decision_report_path))
    check(rows, "v1.5.10 JSON status", EXPECTED_V1_5_10_STATUS, v1_5_10.get("status"))
    check(rows, "v1.5.11 decision", EXPECTED_V1_5_11_STATUS, last_nonempty_line(v1_5_11_decision_report_path))
    check(rows, "v1.5.11 JSON status", EXPECTED_V1_5_11_STATUS, v1_5_11.get("status"))
    check(rows, "v1.5.4 runtime status", EXPECTED_V1_5_4_STATUS, v1_5_4.get("status"))

    check(rows, "promoted checkpoint", ACCEPTED_RUNTIME_CHECKPOINT, v1_5_10.get("accepted_checkpoint"))
    check(rows, "synced checkpoint", ACCEPTED_RUNTIME_CHECKPOINT, v1_5_11.get("current_accepted_runtime_checkpoint"))
    check(rows, "promoted alias", ACCEPTED_RUNTIME_ALIAS_MODEL_ID, v1_5_10.get("accepted_alias_model_id"))
    check(rows, "synced alias", ACCEPTED_RUNTIME_ALIAS_MODEL_ID, v1_5_11.get("current_accepted_runtime_alias_model_id"))
    check(rows, "previous checkpoint historical", PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT, v1_5_11.get("previous_accepted_runtime_checkpoint"))

    check(rows, "manifest adapter", ACCEPTED_RUNTIME_CHECKPOINT, manifest.get("model_adapter_path"))
    check(rows, "manifest alias", ACCEPTED_RUNTIME_ALIAS_MODEL_ID, manifest.get("alias_model_id"))
    check(rows, "manifest backend commit", EXPECTED_BACKEND_COMMIT, manifest.get("backend_commit"))
    check(rows, "manifest backend policy", EXPECTED_BACKEND_COMMIT_POLICY, manifest.get("backend_commit_policy"))
    check(rows, "manifest backend anchor", EXPECTED_BACKEND_ANCHOR_COMMIT, manifest.get("backend_anchor_commit"))

    validate_runtime_records(records, manifest, rows)

    check_contains(
        rows,
        "backend accepted alias constant",
        f'ACCEPTED_ALIAS_MODEL_ID = "{ACCEPTED_RUNTIME_ALIAS_MODEL_ID}"',
        backend_provider_text,
    )
    check_contains(
        rows,
        "backend accepted adapter constant",
        f'ACCEPTED_ADAPTER_PATH = "{ACCEPTED_RUNTIME_CHECKPOINT}"',
        backend_provider_text,
    )
    check_contains(rows, "backend default alias points to accepted", "ALIAS_MODEL_ID = ACCEPTED_ALIAS_MODEL_ID", backend_provider_text)
    check(rows, "model registry contains promoted alias", "True", ACCEPTED_RUNTIME_ALIAS_MODEL_ID in registry_models)
    check(rows, "model registry retains previous alias", "True", PREVIOUS_ACCEPTED_RUNTIME_ALIAS_MODEL_ID in registry_models)
    check_contains(rows, "handoff accepted checkpoint", f"accepted runtime checkpoint: `{ACCEPTED_RUNTIME_CHECKPOINT}`", handoff_text)

    return {
        "readiness_rows": rows,
        "runtime_record_count": len(records),
        "runtime_pass_count": sum(1 for record in records if record.get("final_outcome") == "pass"),
    }


def write_readiness_report(
    *,
    output_path: Path,
    status: str,
    readiness_rows: list[list[str]],
    notes: list[str],
) -> None:
    lines = [
        "# V1.5.12 Promoted Runtime Release Readiness",
        "",
        f"- Status: `{status}`",
        f"- Release baseline checkpoint: `{ACCEPTED_RUNTIME_CHECKPOINT}`.",
        f"- Release baseline alias: `{ACCEPTED_RUNTIME_ALIAS_MODEL_ID}`.",
        f"- Previous accepted checkpoint remains historical only: `{PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT}`.",
        f"- Base model: `{ACCEPTED_RUNTIME_BASE_MODEL}`.",
        f"- Wrapper artifact identity: `{EXPECTED_ARTIFACT}`.",
        f"- Release tag: `{EXPECTED_RELEASE_TAG}`.",
        f"- Desktop commit: `{EXPECTED_DESKTOP_COMMIT}`.",
        f"- Backend tag: `{EXPECTED_BACKEND_TAG}`.",
        f"- Executing backend commit: `{EXPECTED_BACKEND_COMMIT}`.",
        f"- Backend anchor: `{EXPECTED_BACKEND_ANCHOR_COMMIT}`.",
        "",
        "## Scope",
        "",
        "- This milestone is release-readiness review only.",
        "- It does not run training, DPO, scorer updates, blind-suite mutation, or adapter promotion.",
        "- It does not regenerate runtime packages or change wrapper/backend interfaces.",
        "",
        "## Readiness Matrix",
        "",
        render_markdown_table(["check", "expected", "observed", "result"], readiness_rows),
        "",
        "## Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in notes)
    if status == STATUS_READY:
        lines.extend(
            [
                "",
                "## Result",
                "",
                "The promoted runtime repair checkpoint is ready to serve as the stable LV7 runtime baseline.",
            ]
        )
    write_report(output_path, lines)


def write_matrix_report(*, output_path: Path, readiness_rows: list[list[str]]) -> None:
    write_report(
        output_path,
        [
            "# V1.5.12 Release Readiness Matrix",
            "",
            render_markdown_table(["check", "expected", "observed", "result"], readiness_rows),
        ],
    )


def write_decision_report(*, output_path: Path, status: str) -> None:
    write_report(
        output_path,
        [
            "# V1.5.12 Next Step Decision",
            "",
            f"- Stable LV7 runtime baseline: `{ACCEPTED_RUNTIME_CHECKPOINT}`.",
            f"- Stable LV7 runtime alias: `{ACCEPTED_RUNTIME_ALIAS_MODEL_ID}`.",
            f"- Previous accepted checkpoint retained as historical evidence: `{PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT}`.",
            "- v1.5.10 promotion and v1.5.11 identity sync are complete.",
            "- Runtime evidence remains 10/10 pass with no wrapper or model failures.",
            "- No SFT, DPO, scorer, blind-suite, wrapper, backend, or adapter-promotion work is pending for this baseline.",
            "",
            status,
        ],
    )


def analyze_v1_5_12_promoted_runtime_release_readiness(
    *,
    v1_5_10_decision_report_path: Path = DEFAULT_V1_5_10_DECISION_REPORT,
    v1_5_10_json_report_path: Path = DEFAULT_V1_5_10_JSON_REPORT,
    v1_5_11_decision_report_path: Path = DEFAULT_V1_5_11_DECISION_REPORT,
    v1_5_11_json_report_path: Path = DEFAULT_V1_5_11_JSON_REPORT,
    v1_5_4_json_report_path: Path = DEFAULT_V1_5_4_JSON_REPORT,
    runtime_outputs_path: Path = DEFAULT_RUNTIME_OUTPUTS,
    runtime_execution_manifest_path: Path = DEFAULT_RUNTIME_EXECUTION_MANIFEST,
    handoff_report_path: Path = DEFAULT_HANDOFF_REPORT,
    backend_alias_provider_path: Path = DEFAULT_BACKEND_ALIAS_PROVIDER,
    backend_model_registry_path: Path = DEFAULT_BACKEND_MODEL_REGISTRY,
    readiness_report_path: Path = DEFAULT_READINESS_REPORT,
    readiness_matrix_path: Path = DEFAULT_READINESS_MATRIX,
    decision_report_path: Path = DEFAULT_DECISION_REPORT,
    json_report_path: Path = DEFAULT_JSON_REPORT,
) -> dict[str, Any]:
    source_artifacts = {
        "v1_5_10_decision_report": display_path(v1_5_10_decision_report_path),
        "v1_5_10_json_report": display_path(v1_5_10_json_report_path),
        "v1_5_11_decision_report": display_path(v1_5_11_decision_report_path),
        "v1_5_11_json_report": display_path(v1_5_11_json_report_path),
        "v1_5_4_json_report": display_path(v1_5_4_json_report_path),
        "runtime_outputs": display_path(runtime_outputs_path),
        "runtime_execution_manifest": display_path(runtime_execution_manifest_path),
        "handoff_report": display_path(handoff_report_path),
        "backend_alias_provider": display_path(backend_alias_provider_path),
        "backend_model_registry": display_path(backend_model_registry_path),
    }
    status = STATUS_READY
    readiness_rows: list[list[str]] = []
    notes: list[str] = []
    runtime_record_count = 0
    runtime_pass_count = 0
    try:
        summary = validate_release_readiness(
            v1_5_10_decision_report_path=v1_5_10_decision_report_path,
            v1_5_10_json_report_path=v1_5_10_json_report_path,
            v1_5_11_decision_report_path=v1_5_11_decision_report_path,
            v1_5_11_json_report_path=v1_5_11_json_report_path,
            v1_5_4_json_report_path=v1_5_4_json_report_path,
            runtime_outputs_path=runtime_outputs_path,
            runtime_execution_manifest_path=runtime_execution_manifest_path,
            handoff_report_path=handoff_report_path,
            backend_alias_provider_path=backend_alias_provider_path,
            backend_model_registry_path=backend_model_registry_path,
        )
        readiness_rows = summary["readiness_rows"]
        runtime_record_count = int(summary["runtime_record_count"])
        runtime_pass_count = int(summary["runtime_pass_count"])
        notes.append("v1.5.10 promotion and v1.5.11 identity sync are complete")
        notes.append("promoted runtime package remains 10/10 pass with no wrapper or model failures")
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError, TypeError) as exc:
        status = STATUS_BLOCKED
        notes.append(str(exc))

    write_readiness_report(output_path=readiness_report_path, status=status, readiness_rows=readiness_rows, notes=notes)
    write_matrix_report(output_path=readiness_matrix_path, readiness_rows=readiness_rows)
    write_decision_report(output_path=decision_report_path, status=status)

    payload = {
        "milestone": "LV7 v1.5.12",
        "status": status,
        "release_baseline_ready": status == STATUS_READY,
        "accepted_runtime_checkpoint": ACCEPTED_RUNTIME_CHECKPOINT if status == STATUS_READY else None,
        "accepted_runtime_alias_model_id": ACCEPTED_RUNTIME_ALIAS_MODEL_ID if status == STATUS_READY else None,
        "previous_accepted_runtime_checkpoint": PREVIOUS_ACCEPTED_RUNTIME_CHECKPOINT,
        "accepted_base_model": ACCEPTED_RUNTIME_BASE_MODEL,
        "wrapper_artifact": EXPECTED_ARTIFACT,
        "release_tag": EXPECTED_RELEASE_TAG,
        "desktop_commit": EXPECTED_DESKTOP_COMMIT,
        "backend_tag": EXPECTED_BACKEND_TAG,
        "backend_commit": EXPECTED_BACKEND_COMMIT,
        "backend_commit_policy": EXPECTED_BACKEND_COMMIT_POLICY,
        "backend_anchor_commit": EXPECTED_BACKEND_ANCHOR_COMMIT,
        "runtime_record_count": runtime_record_count,
        "runtime_pass_count": runtime_pass_count,
        "evidence_only_sft_adapters": list(EVIDENCE_ONLY_SFT_ADAPTERS),
        "parked_dpo_adapters": list(PARKED_DPO_ADAPTERS),
        "source_artifact_paths": source_artifacts,
        "readiness_rows": readiness_rows,
        "next_recommended_action": (
            "Treat the promoted adapter as the stable LV7 runtime baseline for downstream wrapper/release work."
            if status == STATUS_READY
            else "Resolve blocked release-readiness evidence."
        ),
        "notes": notes,
    }
    json_report_path.parent.mkdir(parents=True, exist_ok=True)
    json_report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review promoted LV7 runtime checkpoint release readiness.")
    return parser.parse_args()


def main() -> None:
    parse_args()
    summary = analyze_v1_5_12_promoted_runtime_release_readiness()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
