from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

from aibenchie.real_device_ux import check_android_real_device_ux_preflight


ANDROID_RELEASE_VERDICT_SCHEMA = "aibenchie.android-release-verdict.v1"
DEFAULT_ANDROID_RELEASE_VERDICT_OUTPUT = Path(".suite/local/aibenchie/android-release-verdict.json")
REQUIRED_UPDATE_NOTE_SECTIONS = (
    "Summary",
    "User-Visible Changes",
    "Compatibility",
    "Regression Checks",
    "Device Rollout",
    "Known Issues",
)


@dataclass(frozen=True)
class AndroidReleaseCheck:
    name: str
    status: str
    required: bool
    summary: str
    failure: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status in {"pass", "skip"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "ok": self.ok,
            "required": self.required,
            "summary": self.summary,
            "failure": self.failure,
            "detail": self.detail,
        }


def _check(
    name: str,
    status: str,
    summary: str,
    *,
    required: bool = True,
    failure: str = "",
    **detail: Any,
) -> AndroidReleaseCheck:
    return AndroidReleaseCheck(
        name=name,
        status=status,
        required=required,
        summary=summary,
        failure="" if status in {"pass", "skip"} else failure,
        detail={key: value for key, value in detail.items() if value not in ("", None, [], {})},
    )


def _git_value(root: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def _git_dirty(root: Path) -> bool | str:
    try:
        output = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return "unknown"
    return bool(output.strip())


def _repo_identity(root: Path) -> dict[str, Any]:
    return {
        "name": root.name,
        "path_label": root.name,
        "branch": _git_value(root, ["branch", "--show-current"]),
        "commit": _git_value(root, ["rev-parse", "HEAD"]),
        "dirty": _git_dirty(root),
    }


def _resolve_under_root(root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _safe_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _latest_update_note(lines: list[str]) -> tuple[str, list[str]]:
    start = next((index for index, line in enumerate(lines) if line.startswith("## ")), None)
    if start is None:
        return "", []
    end = next((index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")), len(lines))
    title = lines[start].lstrip("#").strip()
    return title, lines[start:end]


def _section_titles(lines: list[str]) -> list[str]:
    titles = []
    for line in lines:
        if line.startswith("### "):
            titles.append(line.lstrip("#").strip())
    return titles


def _valid_base_url(value: str) -> bool:
    text = value.strip().lower()
    return text.startswith("https://") or text.startswith("http://127.0.0.1") or text.startswith("http://localhost")


def _device_version(preflight: dict[str, Any]) -> str:
    checks = preflight.get("checks") if isinstance(preflight.get("checks"), list) else []
    for check in checks:
        if not isinstance(check, dict) or check.get("name") != "package_installed":
            continue
        detail = check.get("detail") if isinstance(check.get("detail"), dict) else {}
        version = str(detail.get("version") or "").strip()
        if version:
            return version
    return ""


def run_android_release_gate(
    *,
    repo: str | Path,
    apk: str | Path,
    update_notes: str | Path,
    package_name: str,
    base_url: str,
    output: str | Path | None = None,
    adb: str = "adb",
    adb_serial: str = "",
    require_device: bool = False,
    adb_reader: Callable[[list[str]], str] | None = None,
) -> dict[str, Any]:
    root = Path(repo).expanduser().resolve()
    apk_path = _resolve_under_root(root, apk) if str(apk).strip() else root / "__missing_android_apk__"
    notes_path = _resolve_under_root(root, update_notes) if str(update_notes).strip() else root / "__missing_android_update_notes__"
    checks: list[AndroidReleaseCheck] = []
    artifacts: list[dict[str, Any]] = []
    notes_summary: dict[str, Any] = {}
    android: dict[str, Any] = {
        "package": package_name.strip(),
        "base_url": base_url.strip(),
        "device_required": bool(require_device),
        "device_checked": False,
    }

    checks.append(_check("repo_exists", "pass" if root.exists() else "fail", "Repository path is available.", failure="repo_missing"))
    checks.append(
        _check(
            "package_name",
            "pass" if package_name.strip() else "fail",
            "Android package name is configured.",
            failure="package_name_missing",
            package=package_name.strip(),
        )
    )
    checks.append(
        _check(
            "base_url",
            "pass" if _valid_base_url(base_url) else "fail",
            "Android backend base URL is release-safe.",
            failure="base_url_missing_or_unsafe",
            base_url=base_url.strip(),
        )
    )

    if notes_path.exists():
        note_text = notes_path.read_text(encoding="utf-8")
        lines = note_text.splitlines()
        title, latest_lines = _latest_update_note(lines)
        sections = _section_titles(latest_lines)
        missing_sections = [section for section in REQUIRED_UPDATE_NOTE_SECTIONS if section not in sections]
        notes_summary = {
            "path": _safe_path(notes_path, root),
            "sha256": sha256(note_text.encode("utf-8")).hexdigest(),
            "latest_entry": title,
            "sections": sections,
            "missing_sections": missing_sections,
        }
        checks.append(_check("update_notes_file", "pass", "Android update notes file is present.", path=notes_summary["path"]))
        checks.append(
            _check(
                "update_notes_latest_entry",
                "pass" if title and latest_lines else "fail",
                "Latest Android update-note entry is present.",
                failure="latest_update_note_missing",
                latest_entry=title,
            )
        )
        checks.append(
            _check(
                "update_notes_required_sections",
                "pass" if not missing_sections else "fail",
                "Latest Android update-note entry has required release sections.",
                failure="missing_update_note_sections:" + ",".join(missing_sections),
                sections=sections,
                missing_sections=missing_sections,
            )
        )
    else:
        checks.append(
            _check(
                "update_notes_file",
                "fail",
                "Android update notes file is present.",
                failure="update_notes_missing",
                path=_safe_path(notes_path, root),
            )
        )

    if apk_path.exists() and apk_path.is_file():
        apk_digest = _sha256_file(apk_path)
        apk_size = apk_path.stat().st_size
        artifact = {
            "kind": "android_apk",
            "path": _safe_path(apk_path, root),
            "sha256": apk_digest,
            "byte_size": apk_size,
        }
        artifacts.append(artifact)
        checks.append(_check("apk_artifact", "pass", "Android APK artifact is available.", **artifact))
    else:
        checks.append(
            _check(
                "apk_artifact",
                "fail",
                "Android APK artifact is available.",
                failure="apk_missing",
                path=_safe_path(apk_path, root),
            )
        )

    should_check_device = bool(require_device or adb_serial.strip())
    if should_check_device:
        preflight = check_android_real_device_ux_preflight(
            adb=adb,
            adb_serial=adb_serial,
            package_name=package_name.strip(),
            adb_reader=adb_reader,
        ).as_dict()
        installed_version = _device_version(preflight)
        android.update(
            {
                "device_checked": True,
                "installed_version": installed_version,
                "preflight": preflight,
            }
        )
        device_status = "pass" if preflight.get("ok") else ("fail" if require_device else "warn")
        checks.append(
            _check(
                "device_preflight",
                device_status,
                "Connected Android device can run the candidate package.",
                required=require_device,
                failure="android_device_preflight_failed",
                installed_version=installed_version,
                device_count=preflight.get("device_count"),
            )
        )
    else:
        checks.append(
            _check(
                "device_preflight",
                "skip",
                "Android device preflight was not requested.",
                required=False,
            )
        )

    required_failures = [check for check in checks if check.required and not check.ok]
    warnings = [check for check in checks if check.status == "warn"]
    verdict = "fail" if required_failures else ("warn" if warnings else "pass")
    payload = {
        "schema": ANDROID_RELEASE_VERDICT_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ok": not required_failures,
        "verdict": verdict,
        "repo": _repo_identity(root),
        "android": android,
        "notes": notes_summary,
        "artifacts": artifacts,
        "summary": {
            "checks_total": len(checks),
            "required_failures": len(required_failures),
            "warnings": len(warnings),
            "device_checked": bool(android.get("device_checked")),
        },
        "checks": [check.as_dict() for check in checks],
    }

    if output:
        output_path = Path(output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        payload["output"] = str(output_path.resolve())
    return payload
