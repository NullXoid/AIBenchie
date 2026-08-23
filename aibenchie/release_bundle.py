from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Any

from aibenchie.release_artifacts import (
    DEFAULT_SIGNATURE_ALGORITHM,
    DEFAULT_SIGNING_KEY_ID,
    emit_release_artifacts_manifest,
)


EXCLUDED_PACKAGE_PARTS = {
    ".git",
    ".gradle",
    ".pytest_cache",
    ".suite",
    ".venv",
    "__pycache__",
    "node_modules",
    "release-attestation",
    "release-packages",
    "aibenchie-release-artifact-freeze-summary.json",
}
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
PACKAGE_BASENAMES = {
    "wrapper": "nullxoid-wrapper",
    "android": "nullxoid-companion",
    "public": "echolabs-public-site",
}
REQUIRED_SOURCE_KINDS = ("wrapper", "android", "public")


def _iter_packaged_files(source: Path) -> list[Path]:
    files: list[Path] = []
    for child in source.rglob("*"):
        if not child.is_file():
            continue
        relative_parts = set(child.relative_to(source).parts)
        if relative_parts & EXCLUDED_PACKAGE_PARTS:
            continue
        files.append(child)
    return sorted(files, key=lambda item: item.relative_to(source).as_posix())


def _zip_directory(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for child in _iter_packaged_files(source):
            relative = child.relative_to(source).as_posix()
            info = zipfile.ZipInfo(relative)
            info.date_time = FIXED_ZIP_TIMESTAMP
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with child.open("rb") as source_handle:
                with archive.open(info, "w") as archive_handle:
                    shutil.copyfileobj(source_handle, archive_handle, length=1024 * 1024)


def _package_destination(kind: str, source: Path, output_dir: Path) -> Path:
    basename = PACKAGE_BASENAMES[kind]
    if source.is_dir():
        return output_dir / f"{basename}.zip"
    suffix = source.suffix.lower()
    if kind == "android" and suffix in {".apk", ".aab", ".zip"}:
        return output_dir / f"{basename}{suffix}"
    if suffix in {".zip", ".tgz", ".gz", ".tar"}:
        return output_dir / f"{basename}{suffix}"
    return output_dir / f"{basename}.bin"


def _package_source(kind: str, source: Path, output_dir: Path) -> Path:
    resolved_source = source.expanduser().resolve()
    if not resolved_source.exists():
        raise FileNotFoundError(resolved_source)

    destination = _package_destination(kind, resolved_source, output_dir)
    if resolved_source.is_dir():
        _zip_directory(resolved_source, destination)
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    if resolved_source.resolve() != destination.resolve():
        shutil.copy2(resolved_source, destination)
    return destination


def package_release_artifacts(
    *,
    wrapper_source: Path,
    android_source: Path,
    public_source: Path,
    output_dir: Path,
    manifest_output: Path | None = None,
    sidecar_dir: Path | None = None,
    signature_algorithm: str = DEFAULT_SIGNATURE_ALGORITHM,
    signing_key_id: str = DEFAULT_SIGNING_KEY_ID,
) -> dict[str, Any]:
    resolved_output_dir = output_dir.expanduser().resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    sources = {
        "wrapper": wrapper_source,
        "android": android_source,
        "public": public_source,
    }
    packages = {
        kind: _package_source(kind, sources[kind], resolved_output_dir)
        for kind in REQUIRED_SOURCE_KINDS
    }
    resolved_manifest_output = (
        manifest_output.expanduser().resolve()
        if manifest_output is not None
        else resolved_output_dir / "release-artifacts.json"
    )
    resolved_sidecar_dir = (
        sidecar_dir.expanduser().resolve()
        if sidecar_dir is not None
        else resolved_output_dir / "release-attestation"
    )

    manifest = emit_release_artifacts_manifest(
        packages=packages,
        output=resolved_manifest_output,
        root=resolved_manifest_output.parent,
        sidecar_dir=resolved_sidecar_dir,
        signature_algorithm=signature_algorithm,
        signing_key_id=signing_key_id,
    )
    return {
        "ok": True,
        "output_dir": str(resolved_output_dir),
        "release_artifacts": str(resolved_manifest_output),
        "packages": {kind: str(path) for kind, path in packages.items()},
        "manifest": manifest,
    }
