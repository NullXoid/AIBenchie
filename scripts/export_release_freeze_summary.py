from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "aibenchie.release-artifact-freeze-summary.v1"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve(root: Path, reference: str) -> Path:
    path = Path(reference).expanduser()
    if path.is_absolute():
        return path
    return (root / path).resolve()


def _safe_reference(path: Path, base: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(base.resolve()).as_posix()
    except ValueError:
        try:
            return resolved.relative_to(base.resolve().parent).as_posix()
        except ValueError:
            return resolved.name


def _source_reference(value: str, base: Path) -> str:
    if not value:
        return ""
    path = Path(value).expanduser()
    if not path.is_absolute():
        return path.as_posix()
    return _safe_reference(path, base)


def _artifact_summary(artifact: dict[str, Any], *, manifest_root: Path) -> dict[str, Any]:
    package_path = _resolve(manifest_root, str(artifact.get("path") or ""))
    sidecars = {}
    for key in ("sbom", "manifest", "signature"):
        value = artifact.get(key) if isinstance(artifact.get(key), dict) else {}
        sidecars[key] = {
            "path": str(value.get("path") or ""),
            "sha256": str(value.get("sha256") or ""),
        }
        if key == "signature":
            sidecars[key]["algorithm"] = str(value.get("algorithm") or "")
            sidecars[key]["key_id"] = str(value.get("key_id") or "")

    return {
        "kind": str(artifact.get("kind") or ""),
        "name": str(artifact.get("name") or ""),
        "package_path": str(artifact.get("path") or ""),
        "package_name": package_path.name,
        "byte_size": package_path.stat().st_size if package_path.exists() else None,
        "sha256": str(artifact.get("sha256") or artifact.get("digest", {}).get("value") or ""),
        "digest": {
            "algorithm": str(artifact.get("digest", {}).get("algorithm") or "sha256"),
            "value": str(artifact.get("digest", {}).get("value") or artifact.get("sha256") or ""),
        },
        "sidecars": sidecars,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a public-safe release artifact freeze summary.")
    parser.add_argument("--manifest", required=True, type=Path, help="release-artifacts.json from a local freeze run.")
    parser.add_argument("--suite-status", required=True, type=Path, help="Public-safe suite status JSON.")
    parser.add_argument("--release-spine", type=Path, help="Optional release-spine verdict/evidence JSON.")
    parser.add_argument("--verification", type=Path, help="Optional release artifact verification JSON.")
    parser.add_argument("--output", required=True, type=Path, help="Output public-safe summary JSON.")
    parser.add_argument("--wrapper-source", default="", help="Public-safe wrapper source reference used for packaging.")
    parser.add_argument("--android-source", default="", help="Public-safe Android source reference used for packaging.")
    parser.add_argument("--public-source", default="", help="Public-safe public-site source reference used for packaging.")
    parser.add_argument("--notes", action="append", default=[], help="Additional public-safe notes.")
    args = parser.parse_args()

    repo_root = Path.cwd().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    manifest_root = manifest_path.parent
    manifest = _load_json(manifest_path)
    suite_status = _load_json(args.suite_status)
    release_spine = _load_json(args.release_spine) if args.release_spine and args.release_spine.exists() else {}
    verification = _load_json(args.verification) if args.verification and args.verification.exists() else {}

    artifacts = [
        _artifact_summary(artifact, manifest_root=manifest_root)
        for artifact in manifest.get("artifacts", [])
        if isinstance(artifact, dict)
    ]
    source_inputs = {
        "wrapper": _source_reference(args.wrapper_source, repo_root),
        "android": _source_reference(args.android_source, repo_root),
        "public": _source_reference(args.public_source, repo_root),
    }
    for artifact in artifacts:
        artifact["source_reference"] = source_inputs.get(artifact["kind"], "")

    boundaries = {
        "apk_publish_occurred": bool(release_spine.get("apk_publish_occurred", False)),
        "latest_debug_moved": bool(release_spine.get("latest_debug_moved", False)),
        "full_manifest_committed": False,
        "package_bytes_committed": False,
        "hmac_key_material_committed": False,
    }

    payload = {
        "schema": SCHEMA,
        "schema_version": "1.0",
        "generated_at": _now(),
        "build_id": suite_status.get("build_id") or release_spine.get("build_id") or "",
        "suite_version": suite_status.get("suite_version") or release_spine.get("suite_version") or "",
        "status": suite_status.get("status") or release_spine.get("status") or "",
        "aibenchie_verdict": suite_status.get("aibenchie_verdict") or release_spine.get("aibenchie_verdict") or "",
        "release_candidate_ok": bool(suite_status.get("release_candidate_ok", release_spine.get("ok", False))),
        "public_safe": True,
        "source_commits": suite_status.get("source_commits") or release_spine.get("source_commits") or {},
        "manifest": {
            "path": _safe_reference(manifest_path, repo_root),
            "sha256": str(manifest.get("manifest_sha256") or ""),
            "required_artifact_kinds": manifest.get("required_artifact_kinds") or [],
            "artifact_count": len(artifacts),
            "local_full_attestation": True,
        },
        "verification": {
            "ok": bool(verification.get("ok", False)),
            "artifact_count": verification.get("artifact_count", len(artifacts)),
            "failures": verification.get("failures", []),
            "signature_policy": "full HMAC-SHA256 sidecars verified locally with runtime signing key material; key material and package bytes are not committed",
        },
        "publication_boundaries": boundaries,
        "artifacts": artifacts,
        "notes": args.notes,
    }
    _write_json(args.output, payload)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
