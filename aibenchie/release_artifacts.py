from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


RELEASE_ARTIFACT_SCHEMA_VERSION = 1
REQUIRED_RELEASE_ARTIFACT_KINDS = ("wrapper", "android", "public")
DEFAULT_SIGNATURE_ALGORITHM = "hmac-sha256-v1"
DEFAULT_SIGNING_KEY_ID = "release-attestation-key"
SIGNING_SECRET_ENV = "AIBENCHIE_RELEASE_ATTESTATION_SECRET"
SHA256_HEX_LENGTH = 64

IGNORED_PACKAGE_PARTS = {
    ".git",
    ".gradle",
    ".pytest_cache",
    ".suite",
    ".venv",
    "__pycache__",
    "node_modules",
}


@dataclass(frozen=True)
class ReleaseArtifactVerification:
    ok: bool
    root: str
    manifest: str
    required_kinds: list[str]
    artifact_count: int
    failures: list[str] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "root": self.root,
            "manifest": self.manifest,
            "required_kinds": self.required_kinds,
            "artifact_count": self.artifact_count,
            "failures": self.failures,
            "artifacts": self.artifacts,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == SHA256_HEX_LENGTH and all(char in "0123456789abcdefABCDEF" for char in text)


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _json_sha256(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve(root: Path, reference: str) -> Path:
    path = Path(reference).expanduser()
    if path.is_absolute():
        return path
    return (root / path).resolve()


def _relative_or_absolute(root: Path, path: Path) -> str:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return str(resolved_path)


def _iter_package_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for child in sorted(path.rglob("*")):
        if not child.is_file():
            continue
        if set(child.relative_to(path).parts) & IGNORED_PACKAGE_PARTS:
            continue
        yield child


def _path_sha256(path: Path) -> str:
    if path.is_file():
        return sha256_file(path)
    if not path.is_dir():
        raise FileNotFoundError(path)
    tree_digest = hashlib.sha256()
    for child in _iter_package_files(path):
        rel = child.relative_to(path).as_posix()
        file_digest = sha256_file(child)
        tree_digest.update(rel.encode("utf-8"))
        tree_digest.update(b"\0")
        tree_digest.update(file_digest.encode("ascii"))
        tree_digest.update(b"\0")
        tree_digest.update(str(child.stat().st_size).encode("ascii"))
        tree_digest.update(b"\n")
    return tree_digest.hexdigest()


def _sbom_for_package(kind: str, package_path: Path, root: Path, artifact_sha256: str) -> dict[str, Any]:
    files = []
    base = package_path if package_path.is_dir() else package_path.parent
    for child in _iter_package_files(package_path):
        files.append(
            {
                "path": child.relative_to(base).as_posix(),
                "size": child.stat().st_size,
                "sha256": sha256_file(child),
            }
        )
    return {
        "schema_version": RELEASE_ARTIFACT_SCHEMA_VERSION,
        "format": "aibenchie-sbom-v1",
        "artifact_kind": kind,
        "package_path": _relative_or_absolute(root, package_path),
        "artifact_sha256": artifact_sha256,
        "generated_at": _now(),
        "files": files,
    }


def _package_manifest(kind: str, package_path: Path, root: Path, artifact_sha256: str, sbom: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": RELEASE_ARTIFACT_SCHEMA_VERSION,
        "format": "aibenchie-release-artifact-manifest-v1",
        "artifact_kind": kind,
        "package_path": _relative_or_absolute(root, package_path),
        "artifact_sha256": artifact_sha256,
        "sbom": sbom,
        "generated_at": _now(),
    }


def _resolve_signing_secret(signing_secret: str | None) -> str:
    secret = signing_secret or os.environ.get(SIGNING_SECRET_ENV, "")
    if not secret:
        raise ValueError(f"{SIGNING_SECRET_ENV} is required to emit release artifact signatures")
    return secret


def _hmac_signature(secret: str, subject: dict[str, Any]) -> str:
    return hmac.new(secret.encode("utf-8"), _canonical_json(subject).encode("utf-8"), hashlib.sha256).hexdigest()


def _signature_payload(
    *,
    kind: str,
    artifact_sha256: str,
    manifest_sha256: str,
    sbom_sha256: str,
    algorithm: str,
    key_id: str,
    signing_secret: str,
) -> dict[str, Any]:
    if algorithm != DEFAULT_SIGNATURE_ALGORITHM:
        raise ValueError(f"unsupported release artifact signature algorithm: {algorithm}")
    signed_payload = {
        "schema_version": RELEASE_ARTIFACT_SCHEMA_VERSION,
        "artifact_kind": kind,
        "artifact_sha256": artifact_sha256,
        "manifest_sha256": manifest_sha256,
        "sbom_sha256": sbom_sha256,
    }
    return {
        "schema_version": RELEASE_ARTIFACT_SCHEMA_VERSION,
        "format": "aibenchie-release-signature-v1",
        "algorithm": algorithm,
        "key_id": key_id,
        "signed_payload_sha256": _json_sha256(signed_payload),
        "signed_payload": signed_payload,
        "signature": _hmac_signature(signing_secret, signed_payload),
        "generated_at": _now(),
    }


def emit_release_artifacts_manifest(
    *,
    packages: dict[str, Path],
    output: Path,
    root: Path | None = None,
    sidecar_dir: Path | None = None,
    signature_algorithm: str = DEFAULT_SIGNATURE_ALGORITHM,
    signing_key_id: str = DEFAULT_SIGNING_KEY_ID,
    signing_secret: str | None = None,
    required_kinds: Iterable[str] = REQUIRED_RELEASE_ARTIFACT_KINDS,
) -> dict[str, Any]:
    resolved_output = output.resolve()
    resolved_root = (root or resolved_output.parent).resolve()
    resolved_sidecar_dir = (sidecar_dir or (resolved_output.parent / "release-attestation")).resolve()
    resolved_sidecar_dir.mkdir(parents=True, exist_ok=True)

    required = list(required_kinds)
    missing = [kind for kind in required if kind not in packages or not packages[kind]]
    if missing:
        raise ValueError(f"missing required release package paths: {', '.join(missing)}")
    resolved_signing_secret = _resolve_signing_secret(signing_secret)

    artifacts: list[dict[str, Any]] = []
    for kind in required:
        package_path = packages[kind].expanduser().resolve()
        if not package_path.exists():
            raise FileNotFoundError(package_path)
        artifact_sha256 = _path_sha256(package_path)

        sbom_payload = _sbom_for_package(kind, package_path, resolved_root, artifact_sha256)
        sbom_path = resolved_sidecar_dir / f"{kind}.sbom.json"
        sbom_path.write_text(_canonical_json(sbom_payload), encoding="utf-8")
        sbom_sha256 = sha256_file(sbom_path)

        manifest_payload = _package_manifest(
            kind,
            package_path,
            resolved_root,
            artifact_sha256,
            {
                "path": _relative_or_absolute(resolved_root, sbom_path),
                "sha256": sbom_sha256,
            },
        )
        manifest_path = resolved_sidecar_dir / f"{kind}.manifest.json"
        manifest_path.write_text(_canonical_json(manifest_payload), encoding="utf-8")
        manifest_sha256 = sha256_file(manifest_path)

        signature_payload = _signature_payload(
            kind=kind,
            artifact_sha256=artifact_sha256,
            manifest_sha256=manifest_sha256,
            sbom_sha256=sbom_sha256,
            algorithm=signature_algorithm,
            key_id=signing_key_id,
            signing_secret=resolved_signing_secret,
        )
        signature_path = resolved_sidecar_dir / f"{kind}.sig.json"
        signature_path.write_text(_canonical_json(signature_payload), encoding="utf-8")
        signature_sha256 = sha256_file(signature_path)

        artifacts.append(
            {
                "name": f"{kind}-package",
                "kind": kind,
                "path": _relative_or_absolute(resolved_root, package_path),
                "sha256": artifact_sha256,
                "digest": {"algorithm": "sha256", "value": artifact_sha256},
                "sbom": {
                    "path": _relative_or_absolute(resolved_root, sbom_path),
                    "sha256": sbom_sha256,
                },
                "signature": {
                    "path": _relative_or_absolute(resolved_root, signature_path),
                    "sha256": signature_sha256,
                    "algorithm": signature_algorithm,
                    "key_id": signing_key_id,
                },
                "manifest": {
                    "path": _relative_or_absolute(resolved_root, manifest_path),
                    "sha256": manifest_sha256,
                },
            }
        )

    payload = {
        "schema_version": RELEASE_ARTIFACT_SCHEMA_VERSION,
        "generated_at": _now(),
        "required_artifact_kinds": required,
        "artifacts": artifacts,
    }
    payload["manifest_sha256"] = _json_sha256({key: value for key, value in payload.items() if key != "manifest_sha256"})
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(_canonical_json(payload), encoding="utf-8")
    return payload


def _validate_reference_hash(root: Path, reference: dict[str, Any], label: str, failures: list[str]) -> None:
    path_value = str(reference.get("path") or "").strip()
    expected = str(reference.get("sha256") or "").strip()
    if not path_value:
        failures.append(f"{label}_path_missing")
        return
    if not _is_sha256(expected):
        failures.append(f"{label}_sha256_missing_or_invalid")
        return
    path = _resolve(root, path_value)
    if not path.exists() or not path.is_file():
        failures.append(f"{label}_file_missing:{path_value}")
        return
    actual = sha256_file(path)
    if actual.lower() != expected.lower():
        failures.append(f"{label}_sha256_mismatch:{path_value}")


def _validate_signature_evidence(
    *,
    root: Path,
    signature_reference: dict[str, Any],
    artifact_kind: str,
    artifact_sha256: str,
    sbom_sha256: str,
    manifest_sha256: str,
    signing_secret: str,
    failures: list[str],
) -> None:
    path_value = str(signature_reference.get("path") or "").strip()
    if not path_value:
        return
    signature_path = _resolve(root, path_value)
    if not signature_path.exists() or not signature_path.is_file():
        return
    try:
        payload = json.loads(signature_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"signature_invalid_json:{path_value}:{exc.lineno}")
        return
    if not isinstance(payload, dict):
        failures.append(f"signature_not_object:{path_value}")
        return

    reference_algorithm = str(signature_reference.get("algorithm") or "").strip()
    signature_algorithm = str(payload.get("algorithm") or reference_algorithm).strip()
    if signature_algorithm != DEFAULT_SIGNATURE_ALGORITHM:
        failures.append(f"signature_algorithm_unsupported:{signature_algorithm or '<missing>'}")
        return
    if reference_algorithm and reference_algorithm != signature_algorithm:
        failures.append("signature_algorithm_reference_mismatch")
    reference_key_id = str(signature_reference.get("key_id") or "").strip()
    signature_key_id = str(payload.get("key_id") or "").strip()
    if reference_key_id and signature_key_id and reference_key_id != signature_key_id:
        failures.append("signature_key_id_reference_mismatch")

    signed_payload = payload.get("signed_payload")
    if not isinstance(signed_payload, dict):
        failures.append("signature_signed_payload_missing")
        return
    expected_signed_payload = {
        "schema_version": RELEASE_ARTIFACT_SCHEMA_VERSION,
        "artifact_kind": artifact_kind,
        "artifact_sha256": artifact_sha256,
        "manifest_sha256": manifest_sha256,
        "sbom_sha256": sbom_sha256,
    }
    if signed_payload != expected_signed_payload:
        failures.append("signature_signed_payload_mismatch")
    expected_payload_hash = _json_sha256(signed_payload)
    if str(payload.get("signed_payload_sha256") or "").lower() != expected_payload_hash.lower():
        failures.append("signature_signed_payload_sha256_mismatch")

    signature_value = str(payload.get("signature") or "").strip()
    if not _is_sha256(signature_value):
        failures.append("signature_value_missing_or_invalid")
        return
    if not signing_secret:
        failures.append(f"signature_secret_missing:{SIGNING_SECRET_ENV}")
        return
    expected_signature = _hmac_signature(signing_secret, signed_payload)
    if not hmac.compare_digest(signature_value.lower(), expected_signature.lower()):
        failures.append("signature_value_mismatch")


def verify_release_artifacts_manifest(
    manifest_path: Path,
    *,
    root: Path | None = None,
    signing_secret: str | None = None,
    required_kinds: Iterable[str] = REQUIRED_RELEASE_ARTIFACT_KINDS,
) -> ReleaseArtifactVerification:
    resolved_manifest = manifest_path.expanduser().resolve()
    resolved_root = (root or resolved_manifest.parent).resolve()
    resolved_signing_secret = signing_secret or os.environ.get(SIGNING_SECRET_ENV, "")
    required = list(required_kinds)
    failures: list[str] = []
    artifact_summaries: list[dict[str, Any]] = []

    if not resolved_manifest.exists():
        return ReleaseArtifactVerification(
            ok=False,
            root=str(resolved_root),
            manifest=str(resolved_manifest),
            required_kinds=required,
            artifact_count=0,
            failures=["release_artifacts_manifest_missing"],
        )

    try:
        payload = json.loads(resolved_manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return ReleaseArtifactVerification(
            ok=False,
            root=str(resolved_root),
            manifest=str(resolved_manifest),
            required_kinds=required,
            artifact_count=0,
            failures=[f"release_artifacts_manifest_invalid_json:{exc.lineno}"],
        )

    artifacts = payload.get("artifacts", []) if isinstance(payload, dict) else []
    if not isinstance(artifacts, list):
        failures.append("release_artifacts_not_a_list")
        artifacts = []

    kinds = {str(artifact.get("kind") or "") for artifact in artifacts if isinstance(artifact, dict)}
    for kind in required:
        if kind not in kinds:
            failures.append(f"required_artifact_missing:{kind}")

    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            failures.append(f"artifact_not_object:{index}")
            continue
        name = str(artifact.get("name") or f"artifact_{index}")
        kind = str(artifact.get("kind") or "")
        path_value = str(artifact.get("path") or "").strip()
        digest = artifact.get("digest") if isinstance(artifact.get("digest"), dict) else {}
        expected_artifact_sha = str(artifact.get("sha256") or digest.get("value") or "").strip()
        artifact_failures: list[str] = []
        if not kind:
            artifact_failures.append("kind_missing")
        if not path_value:
            artifact_failures.append("path_missing")
        if not _is_sha256(expected_artifact_sha):
            artifact_failures.append("artifact_sha256_missing_or_invalid")
        else:
            artifact_path = _resolve(resolved_root, path_value)
            if not artifact_path.exists():
                artifact_failures.append(f"artifact_missing:{path_value}")
            else:
                actual_artifact_sha = _path_sha256(artifact_path)
                if actual_artifact_sha.lower() != expected_artifact_sha.lower():
                    artifact_failures.append(f"artifact_sha256_mismatch:{path_value}")
        if str(digest.get("algorithm") or "").lower() != "sha256":
            artifact_failures.append("digest_algorithm_not_sha256")

        sbom = artifact.get("sbom") if isinstance(artifact.get("sbom"), dict) else {}
        signature = artifact.get("signature") if isinstance(artifact.get("signature"), dict) else {}
        manifest = artifact.get("manifest") if isinstance(artifact.get("manifest"), dict) else {}
        _validate_reference_hash(resolved_root, sbom, f"{name}:sbom", artifact_failures)
        _validate_reference_hash(resolved_root, manifest, f"{name}:manifest", artifact_failures)
        _validate_reference_hash(resolved_root, signature, f"{name}:signature", artifact_failures)
        if not str(signature.get("algorithm") or "").strip():
            artifact_failures.append("signature_algorithm_missing")
        if not str(signature.get("key_id") or "").strip():
            artifact_failures.append("signature_key_id_missing")
        _validate_signature_evidence(
            root=resolved_root,
            signature_reference=signature,
            artifact_kind=kind,
            artifact_sha256=expected_artifact_sha,
            sbom_sha256=str(sbom.get("sha256") or ""),
            manifest_sha256=str(manifest.get("sha256") or ""),
            signing_secret=resolved_signing_secret,
            failures=artifact_failures,
        )

        if artifact_failures:
            failures.extend(f"{name}:{failure}" for failure in artifact_failures)
        artifact_summaries.append(
            {
                "name": name,
                "kind": kind,
                "path": path_value,
                "sha256": expected_artifact_sha,
                "ok": not artifact_failures,
                "failures": artifact_failures,
            }
        )

    manifest_hash = payload.get("manifest_sha256") if isinstance(payload, dict) else ""
    if manifest_hash:
        payload_without_hash = dict(payload)
        payload_without_hash.pop("manifest_sha256", None)
        actual_manifest_hash = _json_sha256(payload_without_hash)
        if str(manifest_hash).lower() != actual_manifest_hash.lower():
            failures.append("release_artifacts_manifest_sha256_mismatch")

    return ReleaseArtifactVerification(
        ok=not failures,
        root=str(resolved_root),
        manifest=str(resolved_manifest),
        required_kinds=required,
        artifact_count=len(artifacts),
        failures=failures,
        artifacts=artifact_summaries,
    )
