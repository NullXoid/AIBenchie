from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable


REAL_DEVICE_UX_SCHEMA = "aibenchie.real-device-ux-proof.v1"
DEFAULT_PROOF_PATH = Path("configs/aibenchie_real_device_ux.example.json")
ALLOWED_PLATFORMS = {"android", "ios", "desktop", "web"}
SECRET_KEY_PARTS = ("token", "secret", "password", "credential", "private_key", "apikey", "api_key", "session")
SECRET_VALUE_PREFIXES = ("ghp_", "github_pat_", "gitea_", "forgejo_", "glpat-", "xoxb-", "sk-", "eyj")
REQUIRED_ANDROID_WORKFLOWS = {"signin", "chat"}
DEFAULT_ANDROID_PROOF_OUTPUT = Path(".suite/local/aibenchie/android-real-device-ux.json")
DEFAULT_ANDROID_PACKAGE = "com.nullxoid.android"
DEFAULT_ANDROID_BASE_URL = "https://api.echolabs.diy/nullxoid"


@dataclass(frozen=True)
class RealDeviceUXCheck:
    name: str
    ok: bool
    failure: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "failure": self.failure,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class RealDeviceUXResult:
    ok: bool
    proof_path: str
    platform: str
    proof_id: str
    workflows: list[str]
    app: dict[str, Any]
    environment: dict[str, Any]
    runtime: dict[str, Any]
    checks: list[RealDeviceUXCheck]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "proof_path": self.proof_path,
            "platform": self.platform,
            "proof_id": self.proof_id,
            "workflows": self.workflows,
            "app": self.app,
            "environment": self.environment,
            "runtime": self.runtime,
            "checks": [check.as_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class AndroidRealDeviceUXPreflightResult:
    ok: bool
    platform: str
    package_name: str
    device_count: int
    devices: list[dict[str, Any]]
    checks: list[RealDeviceUXCheck]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "platform": self.platform,
            "package_name": self.package_name,
            "device_count": self.device_count,
            "devices": self.devices,
            "checks": [check.as_dict() for check in self.checks],
        }


def _check(name: str, ok: bool, failure: str = "", **detail: Any) -> RealDeviceUXCheck:
    return RealDeviceUXCheck(name=name, ok=ok, failure="" if ok else failure, detail=detail)


def _load_json(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "proof_missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"proof_invalid_json:{exc.lineno}"
    if not isinstance(payload, dict):
        return {}, "proof_not_object"
    return payload, ""


def _adb_command_args(args: list[str], adb_serial: str = "") -> list[str]:
    selected_serial = adb_serial.strip()
    if selected_serial:
        return ["-s", selected_serial, *args]
    return args


def _adb_value(adb: str, args: list[str], adb_serial: str = "") -> str:
    return subprocess.check_output(
        [adb, *_adb_command_args(args, adb_serial)],
        stderr=subprocess.STDOUT,
        text=True,
        timeout=15,
    ).strip()


def _adb_bytes(adb: str, args: list[str], adb_serial: str = "") -> bytes:
    return subprocess.check_output(
        [adb, *_adb_command_args(args, adb_serial)],
        stderr=subprocess.STDOUT,
        timeout=15,
    )


def _android_package_version(adb_reader: Callable[[list[str]], str], package_name: str) -> str:
    try:
        package_dump = adb_reader(["shell", "dumpsys", "package", package_name])
    except Exception:
        return ""
    for line in package_dump.splitlines():
        stripped = line.strip()
        if stripped.startswith("versionName="):
            return stripped.split("=", 1)[1].strip()
    return ""


def _is_known_app_version(value: str) -> bool:
    normalized = value.strip().lower()
    return bool(normalized and normalized not in {"unknown", "n/a", "na", "none", "missing"})


def _android_prop(adb_reader: Callable[[list[str]], str], prop: str, fallback: str) -> str:
    try:
        value = adb_reader(["shell", "getprop", prop]).strip()
    except Exception:
        return fallback
    return value or fallback


def _parse_adb_devices(output: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("* ") or stripped.lower().startswith("list of devices"):
            continue
        parts = stripped.split()
        if len(parts) >= 2:
            devices.append({"handle": parts[0], "state": parts[1]})
    return devices


def check_android_real_device_ux_preflight(
    *,
    adb: str = "adb",
    adb_serial: str = "",
    package_name: str = DEFAULT_ANDROID_PACKAGE,
    adb_reader: Callable[[list[str]], str] | None = None,
) -> AndroidRealDeviceUXPreflightResult:
    selected_serial = adb_serial.strip()
    reader = adb_reader or (lambda args: _adb_value(adb, args, selected_serial if args != ["devices"] else ""))
    checks: list[RealDeviceUXCheck] = []
    raw_devices: list[dict[str, str]] = []
    devices_output = ""

    try:
        devices_output = reader(["devices"])
        checks.append(_check("adb_devices", True))
        raw_devices = _parse_adb_devices(devices_output)
    except Exception as exc:
        checks.append(_check("adb_devices", False, f"adb_devices_failed:{exc}"))

    connected = [device for device in raw_devices if device.get("state") == "device"]
    blocked = [device for device in raw_devices if device.get("state") != "device"]
    selected_connected = [device for device in connected if device.get("handle") == selected_serial] if selected_serial else connected
    checks.append(
        _check(
            "connected_device",
            bool(connected),
            "adb_device_missing" if not connected else "",
            blocked_states=sorted({device.get("state", "") for device in blocked if device.get("state")}),
        )
    )
    checks.append(
        _check(
            "selected_device",
            bool(selected_connected),
            "adb_serial_not_connected" if selected_serial else "adb_device_missing",
            selected_device_hash=sha256(selected_serial.encode("utf-8")).hexdigest() if selected_serial else "",
            selector_used=bool(selected_serial),
        )
    )

    public_devices = [
        {
            "device_id_hash": sha256(device["handle"].encode("utf-8")).hexdigest(),
            "state": device.get("state", "unknown"),
        }
        for device in raw_devices
        if device.get("handle")
    ]

    version = ""
    package_ok = False
    if selected_connected:
        version = _android_package_version(reader, package_name)
        package_ok = bool(version)
    checks.append(
        _check(
            "package_installed",
            package_ok,
            "package_missing_or_version_unknown",
            package=package_name,
            version=version,
        )
    )

    return AndroidRealDeviceUXPreflightResult(
        ok=all(check.ok for check in checks),
        platform="android",
        package_name=package_name,
        device_count=len(public_devices),
        devices=public_devices,
        checks=checks,
    )


def _workflow_status(passed: bool) -> str:
    return "pass" if passed else "pending"


def _public_artifact_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.name


def emit_android_real_device_ux_proof(
    output_path: str | Path = DEFAULT_ANDROID_PROOF_OUTPUT,
    *,
    adb: str = "adb",
    adb_serial: str = "",
    package_name: str = DEFAULT_ANDROID_PACKAGE,
    base_url: str = DEFAULT_ANDROID_BASE_URL,
    app_version: str = "",
    proof_id: str = "",
    signin_passed: bool = False,
    chat_passed: bool = False,
    runtime_provider: str = "",
    runtime_model: str = "",
    runtime_endpoint_label: str = "",
    network: str = "real-device",
    capture_screenshot: bool = False,
    artifact_dir: str | Path | None = None,
    adb_reader: Callable[[list[str]], str] | None = None,
    adb_binary_reader: Callable[[list[str]], bytes] | None = None,
) -> dict[str, Any]:
    selected_serial = adb_serial.strip()
    reader = adb_reader or (lambda args: _adb_value(adb, args, selected_serial))
    binary_reader = adb_binary_reader or (lambda args: _adb_bytes(adb, args, selected_serial))
    raw_device_handle = reader(["get-serialno"]).strip()
    if not raw_device_handle:
        raise RuntimeError("adb_device_missing")

    manufacturer = _android_prop(reader, "ro.product.manufacturer", "unknown")
    model = _android_prop(reader, "ro.product.model", "unknown")
    os_release = _android_prop(reader, "ro.build.version.release", "unknown")
    os_sdk = _android_prop(reader, "ro.build.version.sdk", "")
    resolved_version = app_version.strip() or _android_package_version(reader, package_name)
    if not _is_known_app_version(resolved_version):
        raise RuntimeError("android_package_version_missing")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    resolved_proof_id = proof_id.strip() or f"android-real-device-ux-{timestamp}"
    output = Path(output_path).expanduser()
    artifacts: list[dict[str, Any]] = []

    if capture_screenshot:
        screenshot = binary_reader(["exec-out", "screencap", "-p"])
        if not screenshot:
            raise RuntimeError("adb_screenshot_empty")
        selected_artifact_dir = Path(artifact_dir).expanduser() if artifact_dir else output.parent / "artifacts"
        selected_artifact_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = selected_artifact_dir / f"{resolved_proof_id}-screen.png"
        screenshot_path.write_bytes(screenshot)
        artifacts.append(
            {
                "kind": "screenshot",
                "name": "android-current-screen",
                "sha256": sha256(screenshot).hexdigest(),
                "byte_size": len(screenshot),
                "path": _public_artifact_path(screenshot_path),
            }
        )

    payload = {
        "schema": REAL_DEVICE_UX_SCHEMA,
        "template": False,
        "proof_id": resolved_proof_id,
        "platform": "android",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "device": {
            "manufacturer": manufacturer,
            "model": model,
            "os_version": f"Android {os_release}" + (f" API {os_sdk}" if os_sdk else ""),
            "device_id_hash": sha256(raw_device_handle.encode("utf-8")).hexdigest(),
        },
        "app": {
            "package": package_name,
            "version": resolved_version,
            "build_type": "installed",
        },
        "environment": {
            "base_url": base_url,
            "network": network,
        },
        "runtime": {
            "provider": runtime_provider.strip(),
            "model": runtime_model.strip(),
            "endpoint_label": runtime_endpoint_label.strip(),
        },
        "workflows": [
            {
                "id": "signin",
                "name": "Native passkey sign-in",
                "status": _workflow_status(signin_passed),
                "evidence": [
                    {
                        "kind": "operator_confirmation",
                        "summary": "Physical Android sign-in completed." if signin_passed else "Physical Android sign-in awaits operator confirmation.",
                    }
                ],
            },
            {
                "id": "chat",
                "name": "NullXoid chat response",
                "status": _workflow_status(chat_passed),
                "evidence": [
                    {
                        "kind": "operator_confirmation",
                        "summary": "Physical Android chat returned a visible response." if chat_passed else "Physical Android chat awaits operator confirmation.",
                    }
                ],
            },
        ],
        "artifacts": artifacts,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    validation = validate_real_device_ux_proof(output).as_dict()
    return {
        "ok": validation["ok"],
        "output": str(output.resolve()),
        "proof_id": resolved_proof_id,
        "platform": "android",
        "validation": validation,
    }


def _scan_secret_like_values(value: Any, path: str = "") -> list[str]:
    failures: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            key_lower = key_text.lower()
            if any(part in key_lower for part in SECRET_KEY_PARTS):
                failures.append(f"{child_path}:secret_key_not_allowed")
                continue
            failures.extend(_scan_secret_like_values(child, child_path))
        return failures
    if isinstance(value, list):
        for index, child in enumerate(value):
            failures.extend(_scan_secret_like_values(child, f"{path}[{index}]"))
        return failures
    if isinstance(value, str):
        stripped = value.strip()
        lower = stripped.lower()
        if any(lower.startswith(prefix) for prefix in SECRET_VALUE_PREFIXES):
            failures.append(f"{path}:secret_value_not_allowed")
    return failures


def _looks_like_hash(value: Any, *, min_len: int = 16) -> bool:
    text = str(value or "").strip()
    return len(text) >= min_len and bool(re.fullmatch(r"[A-Fa-f0-9:_-]+", text))


def _workflow_ids(payload: dict[str, Any]) -> list[str]:
    workflows = payload.get("workflows") if isinstance(payload.get("workflows"), list) else []
    ids = []
    for workflow in workflows:
        if isinstance(workflow, dict):
            workflow_id = str(workflow.get("id") or workflow.get("name") or "").strip()
            if workflow_id:
                ids.append(workflow_id)
    return ids


def validate_real_device_ux_proof(proof_path: str | Path | None = None) -> RealDeviceUXResult:
    selected = Path(proof_path) if proof_path else DEFAULT_PROOF_PATH
    resolved = selected.expanduser().resolve()
    payload, load_failure = _load_json(resolved)
    checks: list[RealDeviceUXCheck] = []

    checks.append(_check("proof_json", not load_failure, load_failure))
    checks.append(_check("schema", payload.get("schema") == REAL_DEVICE_UX_SCHEMA, "schema_mismatch"))

    secret_failures = _scan_secret_like_values(payload)
    checks.append(_check("secret_boundary", not secret_failures, ";".join(secret_failures), scanned=True))

    template = bool(payload.get("template", False))
    checks.append(_check("not_template", not template, "template_proof_not_release_evidence", template=template))

    platform = str(payload.get("platform") or "").strip().lower()
    checks.append(_check("platform", platform in ALLOWED_PLATFORMS, f"unsupported_platform:{platform or 'missing'}", platform=platform))

    proof_id = str(payload.get("proof_id") or "").strip()
    checks.append(_check("proof_id", bool(proof_id), "proof_id_missing"))

    device = payload.get("device") if isinstance(payload.get("device"), dict) else {}
    device_hash = device.get("device_id_hash")
    checks.append(_check("device_id_hash", _looks_like_hash(device_hash), "device_id_hash_missing_or_invalid"))
    raw_device_fields = [key for key in ("device_id", "serial", "imei", "phone_number") if key in device]
    checks.append(_check("raw_device_identifiers_absent", not raw_device_fields, ";".join(raw_device_fields), fields=raw_device_fields))

    app = payload.get("app") if isinstance(payload.get("app"), dict) else {}
    package_name = str(app.get("package") or app.get("bundle_id") or "").strip()
    version = str(app.get("version") or app.get("build") or "").strip()
    checks.append(_check("app_identity", bool(package_name and _is_known_app_version(version)), "app_identity_missing", package=package_name, version=version))

    environment = payload.get("environment") if isinstance(payload.get("environment"), dict) else {}
    base_url = str(environment.get("base_url") or "").strip()
    checks.append(_check("environment", base_url.startswith("https://") or base_url.startswith("http://127.0.0.1"), "environment_base_url_invalid", base_url=base_url))

    workflows = payload.get("workflows") if isinstance(payload.get("workflows"), list) else []
    workflow_ids = _workflow_ids(payload)
    workflow_failures: list[str] = []
    for index, workflow in enumerate(workflows):
        if not isinstance(workflow, dict):
            workflow_failures.append(f"workflow_not_object:{index}")
            continue
        workflow_id = str(workflow.get("id") or workflow.get("name") or index).strip()
        if str(workflow.get("status") or "").strip().lower() != "pass":
            workflow_failures.append(f"workflow_not_pass:{workflow_id}")
        evidence = workflow.get("evidence") if isinstance(workflow.get("evidence"), list) else []
        if not evidence:
            workflow_failures.append(f"workflow_evidence_missing:{workflow_id}")
    checks.append(_check("workflows", bool(workflows) and not workflow_failures, ";".join(workflow_failures), count=len(workflows)))

    if platform == "android":
        missing = sorted(REQUIRED_ANDROID_WORKFLOWS.difference(workflow_ids))
        checks.append(_check("android_required_workflows", not missing, ";".join(f"workflow_missing:{item}" for item in missing), required=sorted(REQUIRED_ANDROID_WORKFLOWS)))
        runtime = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}
        runtime_model = str(runtime.get("model") or "").strip()
        chat_workflow_passed = any(
            isinstance(workflow, dict)
            and str(workflow.get("id") or workflow.get("name") or "").strip() == "chat"
            and str(workflow.get("status") or "").strip().lower() == "pass"
            for workflow in workflows
        )
        checks.append(
            _check(
                "runtime_model_label",
                bool(runtime_model) or not chat_workflow_passed,
                "runtime_model_missing_for_chat",
                model=runtime_model,
                provider=str(runtime.get("provider") or "").strip(),
                endpoint_label=str(runtime.get("endpoint_label") or "").strip(),
            )
        )
    else:
        runtime = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}

    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), list) else []
    artifact_failures = []
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            artifact_failures.append(f"artifact_not_object:{index}")
            continue
        digest = str(artifact.get("sha256") or "").strip()
        if digest and not (len(digest) == 64 and all(char in "0123456789abcdefABCDEF" for char in digest)):
            artifact_failures.append(f"artifact_sha256_invalid:{index}")
        if "path" in artifact and str(artifact.get("path") or "").startswith(("C:\\", "/Users/", "/home/")):
            artifact_failures.append(f"artifact_path_must_be_public_safe:{index}")
    checks.append(_check("artifact_references", not artifact_failures, ";".join(artifact_failures), count=len(artifacts)))

    return RealDeviceUXResult(
        ok=all(check.ok for check in checks),
        proof_path=str(resolved),
        platform=platform,
        proof_id=proof_id,
        workflows=workflow_ids,
        app={
            "package": package_name,
            "version": version,
            "build_type": str(app.get("build_type") or "").strip(),
        },
        environment={
            "base_url": base_url,
            "network": str(environment.get("network") or "").strip(),
        },
        runtime={
            "provider": str(runtime.get("provider") or "").strip(),
            "model": str(runtime.get("model") or "").strip(),
            "endpoint_label": str(runtime.get("endpoint_label") or "").strip(),
        },
        checks=checks,
    )
