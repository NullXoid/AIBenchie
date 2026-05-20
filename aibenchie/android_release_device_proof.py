from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable


ANDROID_RELEASE_DEVICE_PROOF_SCHEMA = "aibenchie.android-release-device-proof.v1"
DEFAULT_ANDROID_RELEASE_DEVICE_PROOF_OUTPUT = Path(".suite/local/aibenchie/android-release-device-proof.json")


def _adb_args(args: list[str], adb_serial: str = "") -> list[str]:
    selected = adb_serial.strip()
    if selected and args != ["devices", "-l"]:
        return ["-s", selected, *args]
    return args


def _adb_value(adb: str, args: list[str], adb_serial: str = "") -> str:
    return subprocess.check_output(
        [adb, *_adb_args(args, adb_serial)],
        stderr=subprocess.STDOUT,
        text=True,
        timeout=15,
    ).strip()


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _parse_devices_l(text: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("list of devices"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        item: dict[str, str] = {
            "serial_hash": _hash(parts[0]),
            "state": parts[1],
        }
        for part in parts[2:]:
            key, sep, value = part.partition(":")
            if sep and key in {"product", "model", "device", "transport_id"}:
                item[key] = value
        devices.append(item)
    return devices


def _package_values(dumpsys: str) -> tuple[str, str, str]:
    if "Unable to find package" in dumpsys or "Package [" not in dumpsys:
        return "not_installed", "", ""
    version_name = ""
    version_code = ""
    name_match = re.search(r"\bversionName=([^\s]+)", dumpsys)
    if name_match:
        version_name = name_match.group(1)
    code_match = re.search(r"\bversionCode=(\d+)", dumpsys)
    if code_match:
        version_code = code_match.group(1)
    return "installed", version_name, version_code


def emit_android_release_device_proof(
    output: str | Path = DEFAULT_ANDROID_RELEASE_DEVICE_PROOF_OUTPUT,
    *,
    app_id: str,
    package_name: str,
    device_alias: str,
    verdict_path: str = "",
    adb: str = "adb",
    adb_serial: str = "",
    adb_reader: Callable[[list[str]], str] | None = None,
) -> dict[str, Any]:
    selected_serial = adb_serial.strip()
    reader = adb_reader or (lambda args: _adb_value(adb, args, selected_serial))
    devices_text = reader(["devices", "-l"])
    serial = reader(["get-serialno"]).strip()
    manufacturer = reader(["shell", "getprop", "ro.product.manufacturer"]).strip() or "unknown"
    model = reader(["shell", "getprop", "ro.product.model"]).strip() or "unknown"
    os_release = reader(["shell", "getprop", "ro.build.version.release"]).strip() or "unknown"
    os_sdk = reader(["shell", "getprop", "ro.build.version.sdk"]).strip()
    dumpsys = reader(["shell", "dumpsys", "package", package_name])
    install_state, app_version, version_code = _package_values(dumpsys)
    payload = {
        "schema": ANDROID_RELEASE_DEVICE_PROOF_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "app_id": app_id,
        "package_name": package_name,
        "serial_alias": device_alias,
        "serial_hash": _hash(serial or selected_serial or device_alias),
        "model": model,
        "manufacturer": manufacturer,
        "os_version": f"Android {os_release}" + (f" API {os_sdk}" if os_sdk else ""),
        "install_state": install_state,
        "app_version": app_version,
        "version_code": version_code,
        "verdict_path": verdict_path,
        "adb_devices_l": {
            "parsed": _parse_devices_l(devices_text),
            "raw_serials_redacted": True,
        },
    }
    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload["output"] = str(output_path.resolve())
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit sanitized Android release device proof.")
    parser.add_argument("--output", default=str(DEFAULT_ANDROID_RELEASE_DEVICE_PROOF_OUTPUT))
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--package-name", required=True)
    parser.add_argument("--device-alias", required=True)
    parser.add_argument("--verdict-path", default="")
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--adb-serial", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = emit_android_release_device_proof(
        output=args.output,
        app_id=args.app_id,
        package_name=args.package_name,
        device_alias=args.device_alias,
        verdict_path=args.verdict_path,
        adb=args.adb,
        adb_serial=args.adb_serial,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Android release device proof: {payload['output']}")
        print(f"Device: {payload['serial_alias']} {payload['model']}")
        print(f"Package: {payload['package_name']} {payload['install_state']}")
    return 0 if payload["install_state"] == "installed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
