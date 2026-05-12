from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


MAX_TEXT_SCAN_BYTES = 1024 * 1024

SKIP_DIR_PARTS = {
    ".git",
    ".gradle",
    ".pytest_cache",
    ".suite",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
}

PRIVATE_PATH_FRAGMENTS = (
    "_runtime/private",
    "_runtime/captures",
    "_runtime/audio",
    "_runtime/video",
    "_runtime/camera",
    "_runtime/transcripts",
    "data/private",
    "reports/local",
    "reports/runtime/.local",
    ".suite/local",
    ".suite/addons/local",
)

PRIVATE_MEDIA_HINTS = (
    "audio",
    "camera",
    "capture",
    "frame",
    "mic",
    "microphone",
    "owner",
    "private",
    "screenshot",
    "screenrecord",
    "transcript",
    "voice",
    "webcam",
)

RAW_MEDIA_SUFFIXES = {
    ".aac",
    ".avi",
    ".flac",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".pcm",
    ".raw",
    ".wav",
    ".webm",
}

SCREEN_OR_CAMERA_SUFFIXES = {
    ".bmp",
    ".gif",
    ".heic",
    ".jpeg",
    ".jpg",
    ".png",
    ".tiff",
    ".webp",
}

SECRET_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".npmrc",
    "id_ed25519",
    "id_rsa",
}

SECRET_SUFFIXES = {
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".pem",
    ".pfx",
}

DISTRIBUTION_METADATA_PREFIXES = (
    "public_export",
    "release",
    "release-artifacts",
    "release-packages",
    "release-attestation",
    "dist",
)

SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|bearer|client[_-]?secret|"
    r"forgejo[_-]?token|nextcloud[_-]?password|password|private[_-]?key|refresh[_-]?token|"
    r"secret|signing[_-]?key)\b[\"']?\s*[:=]\s*[\"']([A-Za-z0-9_./+=:@$%~-]{20,})"
)
LOCAL_WINDOWS_PATH = re.compile(r"\b[A-Za-z]:(?:\\{1,2})Users(?:\\{1,2})[^\\\r\n]+(?:\\{1,2})")
PRIVATE_KEY_MARKER = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
TOKEN_PREFIXES = re.compile(r"\b(?:ghp|github_pat|glpat|sk|xoxb|xoxp|ya29)_[A-Za-z0-9_=-]{16,}")

SAFE_SECRET_VALUE_WORDS = (
    "canary",
    "dummy",
    "example",
    "fake",
    "local-secret-config",
    "placeholder",
    "public",
    "redacted",
    "sample",
    "service-jwt-secret",
    "template",
    "test",
)


@dataclass(frozen=True)
class HygieneFinding:
    path: str
    rule: str
    detail: str
    source: str = "repo"

    def as_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "path": self.path,
            "rule": self.rule,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class DistributionHygieneResult:
    ok: bool
    root: str
    scanned_files: int
    scanned_packages: int
    findings: list[HygieneFinding] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "root": self.root,
            "scanned_files": self.scanned_files,
            "scanned_packages": self.scanned_packages,
            "findings": [finding.as_dict() for finding in self.findings],
        }


def normalize_path(value: str | Path) -> str:
    return str(value).replace("\\", "/").lstrip("./")


def _has_prefix(path: str, prefixes: Iterable[str]) -> bool:
    normalized = normalize_path(path).lower()
    return any(normalized == prefix or normalized.startswith(f"{prefix}/") for prefix in prefixes)


def _is_example_env(path: str) -> bool:
    normalized = normalize_path(path).lower()
    name = Path(normalized).name
    return name.endswith(".example") or name.endswith(".sample") or normalized.endswith(".env.example")


def _is_private_path(path: str) -> bool:
    normalized = normalize_path(path).lower()
    if "!/" in normalized:
        normalized = normalized.split("!/", 1)[1]
    return any(normalized == item or normalized.startswith(f"{item}/") for item in PRIVATE_PATH_FRAGMENTS)


def _is_private_media_path(path: str) -> bool:
    normalized = normalize_path(path).lower()
    suffix = Path(normalized).suffix
    if suffix not in RAW_MEDIA_SUFFIXES | SCREEN_OR_CAMERA_SUFFIXES:
        return False
    return any(hint in normalized for hint in PRIVATE_MEDIA_HINTS)


def _is_secret_file_path(path: str) -> bool:
    normalized = normalize_path(path).lower()
    name = Path(normalized).name
    if _is_example_env(normalized):
        return False
    return name in SECRET_FILE_NAMES or Path(normalized).suffix in SECRET_SUFFIXES


def _is_distribution_metadata_path(path: str) -> bool:
    normalized = normalize_path(path).lower()
    name = Path(normalized).name
    if _has_prefix(normalized, DISTRIBUTION_METADATA_PREFIXES):
        return True
    return any(token in name for token in ("manifest", "release", "sbom"))


def _safe_secret_value(value: str) -> bool:
    lower = value.lower()
    return any(word in lower for word in SAFE_SECRET_VALUE_WORDS)


def _decode_text(blob: bytes) -> str | None:
    if b"\0" in blob:
        return None
    try:
        return blob.decode("utf-8")
    except UnicodeDecodeError:
        return blob.decode("utf-8", errors="ignore")


def _read_small_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_TEXT_SCAN_BYTES:
            return None
        return _decode_text(path.read_bytes())
    except OSError:
        return None


def _path_findings(path: str, *, source: str) -> list[HygieneFinding]:
    findings: list[HygieneFinding] = []
    if _is_private_path(path):
        findings.append(
            HygieneFinding(
                path=path,
                rule="private_runtime_path",
                detail="private/local owner data path must not be tracked or packaged",
                source=source,
            )
        )
    if _is_private_media_path(path):
        findings.append(
            HygieneFinding(
                path=path,
                rule="raw_owner_media",
                detail="raw audio/camera/screenshot/transcript artifact must stay in ignored private runtime storage",
                source=source,
            )
        )
    if _is_secret_file_path(path):
        findings.append(
            HygieneFinding(
                path=path,
                rule="secret_file",
                detail="secret or signing material file must not be distributed",
                source=source,
            )
        )
    return findings


def _content_findings(path: str, text: str, *, source: str) -> list[HygieneFinding]:
    findings: list[HygieneFinding] = []
    if PRIVATE_KEY_MARKER.search(text):
        findings.append(
            HygieneFinding(
                path=path,
                rule="private_key_material",
                detail="private key marker found",
                source=source,
            )
        )
    for match in SECRET_ASSIGNMENT.finditer(text):
        value = match.group(1)
        if _safe_secret_value(value):
            continue
        findings.append(
            HygieneFinding(
                path=path,
                rule="secret_literal",
                detail="secret-like assignment found",
                source=source,
            )
        )
        break
    if TOKEN_PREFIXES.search(text):
        findings.append(
            HygieneFinding(
                path=path,
                rule="token_literal",
                detail="token-like literal found",
                source=source,
            )
        )
    if _is_distribution_metadata_path(path) and LOCAL_WINDOWS_PATH.search(text):
        findings.append(
            HygieneFinding(
                path=path,
                rule="local_machine_path",
                detail="local Windows user path found in distribution metadata",
                source=source,
            )
        )
    return findings


def _git_tracked_files(root: Path) -> list[Path] | None:
    if not (root / ".git").exists():
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=False,
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    files = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8", errors="ignore")
        files.append(root / relative)
    return files


def _fallback_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if set(part.lower() for part in relative.parts) & SKIP_DIR_PARTS:
            continue
        files.append(path)
    return sorted(files)


def _iter_repo_files(root: Path) -> list[Path]:
    tracked = _git_tracked_files(root)
    if tracked is not None:
        return [path for path in tracked if path.is_file()]
    return _fallback_files(root)


def scan_repo(root: Path) -> tuple[list[HygieneFinding], int]:
    findings: list[HygieneFinding] = []
    scanned = 0
    for path in _iter_repo_files(root):
        try:
            relative = normalize_path(path.relative_to(root))
        except ValueError:
            relative = str(path)
        scanned += 1
        findings.extend(_path_findings(relative, source="repo"))
        text = _read_small_text(path)
        if text is not None:
            findings.extend(_content_findings(relative, text, source="repo"))
    return findings, scanned


def scan_zip_package(path: Path) -> tuple[list[HygieneFinding], int]:
    findings: list[HygieneFinding] = []
    scanned = 0
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            scanned += 1
            entry_path = normalize_path(info.filename)
            display_path = f"{path.name}!/{entry_path}"
            findings.extend(_path_findings(display_path, source="package"))
            if info.file_size <= MAX_TEXT_SCAN_BYTES:
                try:
                    text = _decode_text(archive.read(info))
                except (OSError, RuntimeError, zipfile.BadZipFile):
                    text = None
                if text is not None:
                    findings.extend(_content_findings(display_path, text, source="package"))
    return findings, scanned


def scan_package(path: Path) -> tuple[list[HygieneFinding], int]:
    if path.suffix.lower() == ".zip":
        return scan_zip_package(path)
    findings = _path_findings(path.name, source="package")
    text = _read_small_text(path)
    if text is not None:
        findings.extend(_content_findings(path.name, text, source="package"))
    return findings, 1


def run_distribution_hygiene_check(
    *,
    root: Path | None = None,
    packages: Iterable[Path] | None = None
) -> DistributionHygieneResult:
    resolved_root = (root or repo_root_from_env()).resolve()
    repo_findings, scanned_files = scan_repo(resolved_root)
    package_findings: list[HygieneFinding] = []
    scanned_packages = 0
    for package in packages or []:
        resolved_package = package.expanduser().resolve()
        if not resolved_package.exists():
            package_findings.append(
                HygieneFinding(
                    path=str(package),
                    rule="package_missing",
                    detail="distribution package path does not exist",
                    source="package",
                )
            )
            scanned_packages += 1
            continue
        findings, _ = scan_package(resolved_package)
        package_findings.extend(findings)
        scanned_packages += 1

    findings = sorted(repo_findings + package_findings, key=lambda item: (item.source, item.path, item.rule))
    return DistributionHygieneResult(
        ok=not findings,
        root=str(resolved_root),
        scanned_files=scanned_files,
        scanned_packages=scanned_packages,
        findings=findings,
    )


def repo_root_from_env(env: dict[str, str] | None = None) -> Path:
    source = os.environ if env is None else env
    configured = source.get("AIBENCHIE_DISTRIBUTION_ROOT", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run AIBenchie distribution hygiene checks.")
    parser.add_argument("--root", type=Path, default=repo_root_from_env())
    parser.add_argument("--package", action="append", type=Path, default=[])
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_distribution_hygiene_check(root=args.root, packages=args.package).as_dict()
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"AIBenchie Distribution Hygiene: {'PASS' if result['ok'] else 'FAIL'}")
        print(f"Root: {result['root']}")
        print(f"Scanned files: {result['scanned_files']}")
        print(f"Scanned packages: {result['scanned_packages']}")
        for finding in result["findings"]:
            print(f"- {finding['source']}:{finding['path']} [{finding['rule']}] {finding['detail']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
