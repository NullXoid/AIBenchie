"""Validate retained product results, not source links or local crypto simulations.

The release job must supply a trusted policy, manifest and artifact directory.
Hashes detect mismatches; they are not a signature or proof of an honest runner.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path, PureWindowsPath
from typing import Any


MAX_RECEIPT_BYTES = 256 * 1024
MAX_AGE = timedelta(days=7)


def _file(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("invalid_path")
    path = Path(value)
    if path.is_absolute() or PureWindowsPath(value).is_absolute() or ".." in path.parts:
        raise ValueError("invalid_path")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError("missing_or_external_file")
    return resolved


def _digest(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("invalid_sha256")
    return value


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ProductEvidence:
    def __init__(self, root: Path, policy: dict[str, Any], manifest: dict[str, Any]):
        self.root = root
        self.policy = policy
        self.manifest = manifest
        self.checked_builds: dict[str, dict[str, Any]] = {}

    def _build(self, product: str) -> dict[str, Any]:
        if product in self.checked_builds:
            return self.checked_builds[product]
        builds = self.manifest.get("builds", {})
        if not isinstance(builds, dict) or not isinstance(builds.get(product), dict):
            raise ValueError("build_missing")
        build = builds[product]
        revision = build.get("source_revision")
        if not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", revision):
            raise ValueError("source_revision_missing")
        if _hash(_file(self.root, build.get("artifact"))) != _digest(build.get("sha256")):
            raise ValueError("artifact_digest_mismatch")
        self.checked_builds[product] = build
        return build

    def check(self, target: str, evidence: dict[str, Any] | None, checks: tuple[str, ...]) -> list[str]:
        failures = []
        required_scope = self.policy.get("e2ee_required_products", {})
        products = required_scope.get(target) if isinstance(required_scope, dict) else None
        if not isinstance(products, list) or not products or any(not isinstance(x, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}:[a-z0-9][a-z0-9_.-]{0,31}", x) for x in products):
            return [f"{target}:product_scope_missing"]
        if len(products) != len(set(products)):
            return [f"{target}:product_scope_duplicate"]
        refs = (evidence or {}).get("receipts")
        if not isinstance(refs, list) or not refs or len(refs) > 100:
            return [f"{target}:product_receipts_missing"]
        covered = set()
        for index, ref in enumerate(refs):
            try:
                if not isinstance(ref, dict):
                    raise ValueError("invalid_receipt_reference")
                path = _file(self.root, ref.get("path"))
                if path.stat().st_size > MAX_RECEIPT_BYTES:
                    raise ValueError("receipt_too_large")
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != _digest(ref.get("sha256")):
                    raise ValueError("receipt_digest_mismatch")
                receipt = json.loads(raw)
                if not isinstance(receipt, dict) or receipt.get("schema") != "librestead.e2ee-product-result.v1":
                    raise ValueError("invalid_receipt_schema")
                if receipt.get("target") != target or receipt.get("execution") != "product_integration" or receipt.get("ok") is not True:
                    raise ValueError("not_passing_product_result")
                product = receipt.get("product")
                if not isinstance(product, str) or product not in products or product in covered:
                    raise ValueError("unexpected_or_duplicate_product")
                build = self._build(product)
                if receipt.get("artifact_sha256") != build["sha256"] or receipt.get("source_revision") != build["source_revision"]:
                    raise ValueError("receipt_build_mismatch")
                timestamp = receipt.get("executed_at")
                if not isinstance(timestamp, str):
                    raise ValueError("execution_time_missing")
                executed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if executed.tzinfo is None:
                    raise ValueError("execution_time_not_utc_aware")
                age = datetime.now(timezone.utc) - executed
                if age < -timedelta(minutes=5) or age > MAX_AGE:
                    raise ValueError("execution_time_out_of_range")
                results = receipt.get("checks")
                if not isinstance(results, dict) or any(results.get(check) is not True for check in checks):
                    raise ValueError("required_product_check_not_passed")
                covered.add(product)
            except (OSError, ValueError, TypeError, OverflowError):
                # Never echo receipt contents or arbitrary paths into public release output.
                failures.append(f"{target}:invalid_product_receipt:{index}")
        for product in products:
            if product not in covered:
                failures.append(f"{target}:product_result_missing:{product}")
        return failures
