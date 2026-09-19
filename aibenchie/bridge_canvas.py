"""Explicit AIBenchie gate; never imported by the chat or file execution path."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET


def junit_passed(path: Path, returncode: int) -> bool:
    if returncode != 0 or not path.is_file():
        return False
    try:
        root = ET.parse(path).getroot()
        cases = root.findall(".//testcase")
        return bool(cases) and not any(node.tag in {"failure", "error", "skipped"} for node in root.iter())
    except (ET.ParseError, OSError):
        return False


def fingerprint(root: Path) -> dict:
    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else "unavailable"
    return {"head": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def run(account: Path, bridge: Path, native: Path, output: Path, *, timeout=600) -> dict:
    root = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=False)
    prerequisites = {
        "account_source": account / "backend/account_approvals.py",
        "bridge_source": bridge / "backend/scripts/nullbridge_file_dispatcher.py",
        "native_probe": native,
    }
    missing = [name for name, path in prerequisites.items() if not path.is_file()]
    result = {"schema": "aibenchie.bridge-canvas.v1", "scope": ["AUTH-10", "WIN-12", "WIN-13"],
        "checkedAt": datetime.now(timezone.utc).isoformat(), "verdict": "blocked", "physicalAcceptance": False,
        "limitations": ["Synthetic account session and requester; no physical phone or browser UI.",
                        "Pass does not authorize deployment or close the physical acceptance checklist."],
        "missing": missing}
    if not missing:
        result["targets"] = {"account": fingerprint(account), "bridge": fingerprint(bridge),
            "aibenchie": fingerprint(root), "nativeSha256": hashlib.sha256(native.read_bytes()).hexdigest()}
        env = os.environ.copy()
        env.update(AIBENCHIE_CANVAS_ACCOUNT_ROOT=str(account), AIBENCHIE_CANVAS_BRIDGE_ROOT=str(bridge),
                   AIBENCHIE_CANVAS_NATIVE_PROBE=str(native), PYTHONDONTWRITEBYTECODE="1")
        junit = output / "combined-chain.xml"
        command = [sys.executable, "-m", "pytest", str(root / "tests/integration/test_bridge_canvas_account.py"),
                   str(root / "tests/integration/test_bridge_account_authentication.py"),
                   str(root / "tests/integration/test_native_account_link_clock.py"),
                   str(root / "tests/integration/test_native_file_authority_clock.py"),
                   str(root / "tests/integration/test_bridge_guarded_account_review.py"),
                   str(root / "tests/integration/test_bridge_bootstrap_recovery.py"),
                   str(root / "tests/integration/test_bridge_deferred_owner.py"),
                   str(root / "tests/integration/test_canvas_file_binding.py"),
                   str(root / "tests/integration/test_bridge_canvas_document_viability.py"),
                   "-q", "-p", "no:cacheprovider", "--tb=short", "--junitxml=" + str(junit)]
        try:
            with (output / "combined-chain.log").open("w", encoding="utf-8") as log:
                completed = subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
            result["returncode"] = completed.returncode
            result["verdict"] = "pass" if junit_passed(junit, completed.returncode) else "fail"
        except subprocess.TimeoutExpired:
            result["verdict"], result["reason"] = "fail", "combined_chain_timeout"
        result["evidence"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", type=Path, default=os.environ.get("AIBENCHIE_CANVAS_ACCOUNT_ROOT"))
    parser.add_argument("--bridge", type=Path, default=os.environ.get("AIBENCHIE_CANVAS_BRIDGE_ROOT"))
    parser.add_argument("--native-probe", type=Path, default=os.environ.get("AIBENCHIE_CANVAS_NATIVE_PROBE"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (args.output or root / ".suite/local/bridge-canvas" / uuid.uuid4().hex).resolve()
    if any(p is None for p in (args.account, args.bridge, args.native_probe)):
        print(json.dumps({"verdict": "blocked", "reason": "Explicit account, Bridge and native-probe paths are required",
                          "physicalAcceptance": False}))
        return 2
    result = run(args.account.resolve(), args.bridge.resolve(), args.native_probe.resolve(), output)
    print(json.dumps({"verdict": result["verdict"], "physicalAcceptance": False, "evidence": str(output),
                      "missing": result["missing"]}))
    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
