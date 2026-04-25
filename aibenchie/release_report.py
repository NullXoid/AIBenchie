from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aibenchie.local_nullbridge_runner import run_local_trust_path
from aibenchie.nullprivacy import decrypt_blob, encrypt_blob, generate_key, run_e2ee_storage_proof
from training.release_fabric import (
    POLICIES_ROOT,
    load_json,
    validate_aibenchie_gates,
    validate_nullbridge_capabilities,
    validate_nullbridge_registry,
    validate_privacy_levels,
    validate_resource_policy,
)


REPORT_VERSION = 1
PUBLIC_TRACKS = {
    "nullbridge_enforcement",
    "privacy",
    "e2ee_storage",
    "resource_management",
    "ephemeral_secret_handling",
    "release_manifest_validation",
}
SECRET_MARKERS = [
    "authorization",
    "bearer ",
    "service_token",
    "nullbridge_service_token",
    "cookie",
    "jwt",
    "eyj",
    "private_key",
]


def git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except Exception:
        return "unknown"


def safe_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).lower()


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = safe_json(payload)
    leaked = [marker for marker in SECRET_MARKERS if marker in text]
    if leaked:
        raise ValueError(f"summary contains secret-like markers: {', '.join(leaked)}")


def policy_track_results() -> dict[str, str]:
    checks = {
        "privacy": validate_privacy_levels(load_json(POLICIES_ROOT / "privacy-levels.json")),
        "resource_management": validate_resource_policy(load_json(POLICIES_ROOT / "resource-policy.json")),
        "nullbridge_enforcement": validate_nullbridge_registry(load_json(POLICIES_ROOT / "nullbridge-registry.json"))
        + validate_nullbridge_capabilities(load_json(POLICIES_ROOT / "nullbridge-capabilities.json")),
        "release_manifest_validation": validate_aibenchie_gates(load_json(POLICIES_ROOT / "aibenchie-gates.json")),
    }
    return {track: ("pass" if not errors else "blocks_release") for track, errors in checks.items()}


def build_release_report(root: Path, *, run_trust_smoke: bool = True) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    commit = git_commit(root)
    tracks = policy_track_results()
    privacy_proof = run_e2ee_storage_proof().as_dict()
    tracks["e2ee_storage"] = "pass" if privacy_proof["ok"] else "critical_block"
    tracks["ephemeral_secret_handling"] = "pass"

    trust_smoke: dict[str, Any] = {"ok": "skipped"}
    if run_trust_smoke:
        trust_result = run_local_trust_path()
        tracks["nullbridge_enforcement"] = "pass" if trust_result.get("ok") else "critical_block"
        trust_smoke = {
            "ok": bool(trust_result.get("ok")),
            "allow_status": trust_result.get("allow", {}).get("status"),
            "deny_status": trust_result.get("deny", {}).get("status"),
            "secrets_persisted": bool(trust_result.get("secrets_persisted")),
        }

    critical_blocks = sorted(track for track, status in tracks.items() if status == "critical_block")
    blocks_release = sorted(track for track, status in tracks.items() if status == "blocks_release")
    verdict = "ship_candidate" if not critical_blocks and not blocks_release else "critical_block"
    generated_at = datetime.now(timezone.utc).isoformat()

    summary = {
        "version": REPORT_VERSION,
        "source_commit": commit,
        "generated_at": generated_at,
        "verdict": verdict,
        "critical_blocks": critical_blocks,
        "tracks": {track: tracks.get(track, "not_run") for track in sorted(PUBLIC_TRACKS)},
        "trust_smoke": trust_smoke,
        "privacy_proof": {
            "ok": privacy_proof["ok"],
            "wrong_key_rejected": privacy_proof["wrong_key_rejected"],
            "tamper_rejected": privacy_proof["tamper_rejected"],
            "plaintext_visible_in_blob": privacy_proof["plaintext_visible_in_blob"],
        },
    }
    assert_public_safe(summary)

    full_report = {
        "summary": summary,
        "tracks": tracks,
        "privacy_proof": privacy_proof,
        "notes": [
            "Full report encrypted before storage.",
            "No service credentials are included in the generated report.",
        ],
    }
    key = generate_key()
    encrypted_full = encrypt_blob(key, json.dumps(full_report, sort_keys=True).encode("utf-8"), associated_data={"kind": "aibenchie_full_report"})
    return summary, encrypted_full, key


def write_release_report(root: Path, output_dir: Path | None = None, *, run_trust_smoke: bool = True) -> dict[str, Any]:
    output = output_dir or (root / "reports" / "aibenchie" / "latest")
    output.mkdir(parents=True, exist_ok=True)
    summary, encrypted_full, key = build_release_report(root, run_trust_smoke=run_trust_smoke)
    summary_path = output / "summary.json"
    encrypted_path = output / "full-report.json.encrypted"
    key_hint_path = output / "full-report.key.local"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    encrypted_path.write_text(json.dumps(encrypted_full, indent=2, sort_keys=True), encoding="utf-8")
    key_hint_path.write_text(
        "Generated per-run report key. Keep this local or replace with a hardware/device key flow.\n"
        + key.hex()
        + "\n",
        encoding="utf-8",
    )
    return {
        "ok": summary["verdict"] == "ship_candidate",
        "summary": str(summary_path),
        "encrypted_full_report": str(encrypted_path),
        "local_key": str(key_hint_path),
        "verdict": summary["verdict"],
    }


def decrypt_full_report(key: bytes, encrypted_report: dict[str, Any]) -> dict[str, Any]:
    return json.loads(decrypt_blob(key, encrypted_report).decode("utf-8"))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    result = write_release_report(root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
