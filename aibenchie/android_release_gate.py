from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from aibenchie.real_device_ux import check_android_real_device_ux_preflight
from aibenchie.android_release_evidence import EVIDENCE_POLICY, validate_device_proof, valid_https_url


ANDROID_RELEASE_VERDICT_SCHEMA = "aibenchie.android-release-verdict.v1"
DEFAULT_ANDROID_RELEASE_VERDICT_OUTPUT = Path(".suite/local/aibenchie/android-release-verdict.json")
DEFAULT_SIGNING_FINGERPRINT_CONFIG = Path(".suite/local/aibenchie/android-signing-fingerprints.json")
KNOWN_ANDROID_RELEASE_APPS = {
    "nullxoid_android": "com.nullxoid.android",
    "nullbridge_android": "com.nullxoid.nullbridge",
}
PUBLISH_ACTIONS = {"publish", "latest-debug", "ready_to_publish"}
SHA256_FINGERPRINT_RE = re.compile(r"^([0-9A-F]{2}:){31}[0-9A-F]{2}$")
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


def _normalize_fingerprint(value: str) -> str:
    raw = str(value or "").strip().upper().replace("-", ":").replace(" ", ":")
    if ":" not in raw and len(raw) == 64:
        raw = ":".join(raw[index:index + 2] for index in range(0, 64, 2))
    raw = re.sub(r":+", ":", raw)
    return raw


def _apksigner_candidates() -> list[str]:
    candidates: list[str] = []
    found = shutil.which("apksigner")
    if found:
        candidates.append(found)
    for env_name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        sdk_root = os.environ.get(env_name)
        if not sdk_root:
            continue
        build_tools = Path(sdk_root) / "build-tools"
        if not build_tools.exists():
            continue
        for candidate in sorted(build_tools.glob("*/apksigner*"), reverse=True):
            if candidate.is_file():
                candidates.append(str(candidate))
    return list(dict.fromkeys(candidates))


def _extract_apk_signing_fingerprint(apk_path: Path) -> str:
    if not apk_path.exists():
        return ""
    for apksigner in _apksigner_candidates():
        try:
            output = subprocess.check_output(
                [apksigner, "verify", "--print-certs", str(apk_path)],
                text=True,
                stderr=subprocess.STDOUT,
                timeout=30,
            )
        except Exception:
            continue
        for line in output.splitlines():
            if "SHA-256 digest:" in line:
                return _normalize_fingerprint(line.split("SHA-256 digest:", 1)[1])
    return ""


def _extract_apk_metadata(apk_path: Path) -> dict[str, str]:
    candidates = [shutil.which("aapt")]
    for env_name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(env_name):
            candidates.extend(str(p) for p in sorted((Path(os.environ[env_name]) / "build-tools").glob("*/aapt*"), reverse=True)
                              if p.is_file() and p.stem == "aapt")
    for executable in dict.fromkeys(c for c in candidates if c):
        try:
            output = subprocess.check_output([executable, "dump", "badging", str(apk_path)],
                                             text=True, stderr=subprocess.STDOUT, timeout=30)
            match = re.search(r"^package: name='([^']+)' versionCode='(\d+)' versionName='([^']*)'", output, re.M)
            if match:
                return dict(package_name=match[1], version_code=match[2], app_version=match[3])
        except (OSError, subprocess.SubprocessError):
            continue
    return {}


def _load_expected_fingerprint(root: Path, app_id: str) -> tuple[str, str]:
    env_key = f"AIBENCHIE_ANDROID_SIGNING_FINGERPRINT_{app_id.upper()}"
    env_value = _normalize_fingerprint(os.environ.get(env_key, ""))
    if env_value:
        return env_value, f"env:{env_key}"
    config_path = root / DEFAULT_SIGNING_FINGERPRINT_CONFIG
    if config_path.exists():
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            value = payload.get(app_id)
            if isinstance(value, dict):
                value = value.get("sha256") or value.get("fingerprint")
            normalized = _normalize_fingerprint(str(value or ""))
            if normalized:
                return normalized, _safe_path(config_path, root)
    return "", ""


def _proof_summary(path: Path, root: Path, expected: dict) -> dict[str, Any]:
    return {"path": _safe_path(path, root), **validate_device_proof(path, expected)}


def _proof_path(root: Path, value: str | Path, fallback: str) -> Path:
    path = Path(value).expanduser() if str(value).strip() else Path(fallback)
    return path if path.is_absolute() else root / path


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
    if valid_https_url(value):
        return True
    try:
        url = urlsplit(value)
        return (url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost", "::1"}
                and valid_https_url("https:" + value[5:]))
    except ValueError:
        return False


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
    backend_revision: str = "",
    app_id: str = "",
    app_version: str = "",
    version_code: str = "",
    signing_fingerprint_sha256: str = "",
    expected_signing_fingerprint: str = "",
    expected_signing_fingerprint_source: str = "",
    primary_device_proof: str | Path = "",
    secondary_device_proof: str | Path = "",
    publish_action: str = "diagnostic",
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
    app_key = (app_id or "").strip().lower()
    if not app_key and package_name.strip():
        app_key = next((key for key, package in KNOWN_ANDROID_RELEASE_APPS.items() if package == package_name.strip()), "")
    publish_mode = (publish_action or "diagnostic").strip().lower()
    mode_valid = publish_mode in {"diagnostic", *PUBLISH_ACTIONS}
    expected_package = KNOWN_ANDROID_RELEASE_APPS.get(app_key, "")
    actual_fingerprint = _normalize_fingerprint(signing_fingerprint_sha256)
    actual_fingerprint_source = "argument" if actual_fingerprint else ""
    if not actual_fingerprint:
        actual_fingerprint = _extract_apk_signing_fingerprint(apk_path)
        actual_fingerprint_source = "apk" if actual_fingerprint else ""
    expected_fingerprint = _normalize_fingerprint(expected_signing_fingerprint)
    expected_source = expected_signing_fingerprint_source.strip()
    if not expected_fingerprint and app_key:
        expected_fingerprint, config_source = _load_expected_fingerprint(root, app_key)
        expected_source = expected_source or config_source
    android: dict[str, Any] = {
        "app_id": app_key,
        "package": package_name.strip(),
        "expected_package": expected_package,
        "base_url": base_url.strip(),
        "app_version": app_version.strip(),
        "version_code": str(version_code or "").strip(),
        "publish_action": publish_mode,
        "backend_revision": backend_revision,
        "evidence_policy": EVIDENCE_POLICY,
        "device_required": bool(require_device),
        "device_checked": False,
        "signing": {
            "fingerprint_sha256": actual_fingerprint,
            "fingerprint_source": actual_fingerprint_source or "missing",
            "expected_source": expected_source,
            "match": bool(actual_fingerprint and expected_fingerprint and actual_fingerprint == expected_fingerprint),
        },
    }

    checks.append(_check("release_mode", "pass" if mode_valid else "fail",
                         "Release mode is explicitly supported.", failure="release_mode_invalid"))
    if publish_mode in PUBLISH_ACTIONS:
        checks.append(_check("release_https", "pass" if valid_https_url(base_url) else "fail",
                             "Publication evidence uses HTTPS.", failure="release_https_required"))
        checks.append(_check("backend_revision", "pass" if re.fullmatch(r"[a-f0-9]{40}", backend_revision) else "fail",
                             "Backend candidate is pinned.", failure="backend_revision_required"))
        # A supplied fingerprint is useful diagnostically, but cannot replace APK verification.
        verified_fingerprint = _extract_apk_signing_fingerprint(apk_path)
        checks.append(_check("apk_signer_verified", "pass" if verified_fingerprint and verified_fingerprint == actual_fingerprint else "fail",
                             "Signer was verified from the candidate APK.", failure="apk_signer_unverified"))
        metadata = _extract_apk_metadata(apk_path)
        matches = metadata == dict(package_name=package_name.strip(), version_code=str(version_code), app_version=app_version.strip())
        checks.append(_check("apk_metadata_verified", "pass" if matches else "fail",
                             "Package and version were read from the candidate APK.", failure="apk_metadata_mismatch_or_unavailable"))

    checks.append(_check("repo_exists", "pass" if root.exists() else "fail", "Repository path is available.", failure="repo_missing"))
    checks.append(
        _check(
            "app_id",
            "pass" if app_key in KNOWN_ANDROID_RELEASE_APPS else "fail",
            "Android app id is recognized.",
            failure="app_id_unknown",
            app_id=app_key,
        )
    )
    checks.append(
        _check(
            "package_name",
            "pass" if package_name.strip() and (not expected_package or package_name.strip() == expected_package) else "fail",
            "Android package name matches the selected app.",
            failure="package_name_missing_or_mismatch",
            package=package_name.strip(),
            expected=expected_package,
        )
    )
    checks.append(
        _check(
            "app_version",
            "pass" if app_version.strip() else "fail",
            "Android app version is recorded.",
            failure="app_version_missing",
            app_version=app_version.strip(),
        )
    )
    checks.append(
        _check(
            "version_code",
            "pass" if str(version_code or "").strip().isdigit() else "fail",
            "Android version code is recorded.",
            failure="version_code_missing",
            version_code=str(version_code or "").strip(),
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

    checks.append(
        _check(
            "signing_fingerprint",
            "pass" if SHA256_FINGERPRINT_RE.fullmatch(actual_fingerprint or "") else "fail",
            "Android signing SHA-256 fingerprint is available.",
            failure="signing_fingerprint_missing_or_invalid",
            fingerprint_present=bool(actual_fingerprint),
        )
    )
    checks.append(
        _check(
            "expected_signing_fingerprint",
            "pass" if SHA256_FINGERPRINT_RE.fullmatch(expected_fingerprint or "") else "fail",
            "Expected signing SHA-256 fingerprint is available from local or CI secret config.",
            failure="expected_signing_fingerprint_missing_or_invalid",
            expected_source=expected_source,
        )
    )
    checks.append(
        _check(
            "signing_fingerprint_match",
            "pass" if actual_fingerprint and expected_fingerprint and actual_fingerprint == expected_fingerprint else "fail",
            "Android signing fingerprint matches the expected release identity.",
            failure="signing_fingerprint_mismatch",
            expected_source=expected_source,
        )
    )

    proof_required = publish_mode in PUBLISH_ACTIONS
    expected_proof = dict(app_id=app_key, package_name=package_name.strip(), app_version=app_version.strip(),
                          version_code=str(version_code), apk_sha256=artifacts[0]["sha256"] if artifacts else "",
                          signing_fingerprint_sha256=actual_fingerprint, base_url=base_url.strip(),
                          backend_revision=backend_revision)
    primary_proof = _proof_summary(_proof_path(root, primary_device_proof, "__missing_primary_device_proof__"), root, expected_proof)
    secondary_proof = _proof_summary(_proof_path(root, secondary_device_proof, "__missing_secondary_device_proof__"), root, expected_proof)
    android["device_proofs"] = {"primary": primary_proof, "secondary": secondary_proof}
    checks.append(
        _check(
            "primary_device_proof",
            "pass" if primary_proof.get("valid") else ("fail" if proof_required or primary_proof.get("present") else "skip"),
            "Primary physical-device acceptance proof is valid.",
            required=proof_required or primary_proof.get("present", False),
            failure="primary_device_proof_invalid" if primary_proof.get("present") else "primary_device_proof_missing",
            path=primary_proof.get("path"),
        )
    )
    checks.append(
        _check(
            "secondary_device_proof",
            "pass" if secondary_proof.get("valid") else ("fail" if proof_required or secondary_proof.get("present") else "skip"),
            "Secondary physical-device acceptance proof is valid.",
            required=proof_required or secondary_proof.get("present", False),
            failure="secondary_device_proof_invalid" if secondary_proof.get("present") else "secondary_device_proof_missing",
            path=secondary_proof.get("path"),
        )
    )
    checks.append(
        _check(
            "publish_action",
            "pass" if mode_valid and (publish_mode == "diagnostic" or (primary_proof.get("valid") and secondary_proof.get("valid"))) else "fail",
            "Publish/latest-debug actions require complete device proof.",
            failure="publish_action_missing_device_proof",
            action=publish_mode,
        )
    )
    if proof_required or (primary_proof.get("valid") and secondary_proof.get("valid")):
        distinct = bool(primary_proof.get("valid") and secondary_proof.get("valid")
                        and primary_proof.get("serial_hash") != secondary_proof.get("serial_hash"))
        checks.append(_check("distinct_physical_devices", "pass" if distinct else "fail",
                             "Two distinct physical devices supplied acceptance evidence.",
                             failure="distinct_physical_devices_required"))

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
    verdict = "fail" if required_failures else ("manual-review" if warnings else "pass")
    payload = {
        "schema": ANDROID_RELEASE_VERDICT_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ok": verdict == "pass",
        "verdict": verdict,
        "repo": _repo_identity(root),
        "android": android,
        "notes": notes_summary,
        "artifacts": artifacts,
        "summary": {
            "checks_total": len(checks),
            "passed": sum(check.status == "pass" for check in checks),
            "skipped": sum(check.status == "skip" for check in checks),
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
