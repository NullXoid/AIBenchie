import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from aibenchie.e2ee_product_evidence import ProductEvidence


CHECKS = ("roundtrip", "tamper_rejected")


@pytest.fixture
def product_case(tmp_path):
    artifact = tmp_path / "client.apk"
    artifact.write_bytes(b"test-only synthetic build")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    build = {"source_revision": "b" * 40, "artifact": artifact.name, "sha256": digest}
    receipt = {
        "schema": "librestead.e2ee-product-result.v1", "product": "assistant:android",
        "target": "saved_chats", "execution": "product_integration", "ok": True,
        "artifact_sha256": digest, "source_revision": build["source_revision"],
        "executed_at": datetime.now(timezone.utc).isoformat(), "checks": {check: True for check in CHECKS},
    }
    policy = {"e2ee_required_products": {"saved_chats": ["assistant:android"]}}
    manifest = {"builds": {"assistant:android": build}}
    return tmp_path, policy, manifest, receipt


def write_receipt(root, receipt):
    path = root / "result.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def run_case(case, refs=None):
    root, policy, manifest, receipt = case
    refs = [write_receipt(root, receipt)] if refs is None else refs
    return ProductEvidence(root, policy, manifest).check("saved_chats", {"receipts": refs}, CHECKS)


def test_valid_artifact_bound_receipt(product_case):
    assert run_case(product_case) == []


@pytest.mark.parametrize("field,value", [
    ("ok", False), ("ok", "true"), ("ok", 1), ("execution", "unit_simulation"),
    ("target", "private_uploads"), ("product", "other:android"), ("product", []),
    ("schema", "old"), ("source_revision", "c" * 40), ("artifact_sha256", "c" * 64),
    ("checks", {"roundtrip": True, "tamper_rejected": "passed"}),
    ("checks", {"roundtrip": True, "tamper_rejected": 1}), ("checks", {}),
    ("executed_at", "not-a-date"), ("executed_at", "2026-01-01T00:00:00"),
    ("executed_at", None),
])
def test_rejects_bad_result_or_identity(product_case, field, value):
    product_case[3][field] = value
    assert run_case(product_case)


@pytest.mark.parametrize("days", [-8, 1])
def test_stale_and_future_receipts_rejected(product_case, days):
    product_case[3]["executed_at"] = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    assert run_case(product_case)


@pytest.mark.parametrize("path", ["missing.json", "../outside.json", "/tmp/result.json", "C:/secret.json", "x\\result.json", "https://example.com/result.json"])
def test_unretained_or_external_paths_rejected(product_case, path):
    assert run_case(product_case, [{"path": path, "sha256": "a" * 64}])


def test_digest_and_artifact_mismatch_rejected(product_case):
    root = product_case[0]
    ref = write_receipt(root, product_case[3])
    (root / "result.json").write_text("{}", encoding="utf-8")
    assert run_case(product_case, [ref])
    ref = write_receipt(root, product_case[3])
    (root / "client.apk").write_bytes(b"different build")
    assert run_case(product_case, [ref])


def test_missing_product_and_duplicate_receipts_rejected(product_case):
    root, policy, _manifest, receipt = product_case
    ref = write_receipt(root, receipt)
    assert run_case(product_case, [ref, ref])
    policy["e2ee_required_products"]["saved_chats"].append("assistant:windows")
    assert "saved_chats:product_result_missing:assistant:windows" in run_case(product_case, [ref])


@pytest.mark.parametrize("payload", [[], None, {"receipts": "source.py"}, {"receipts": []}])
def test_no_receipt_means_no_product_proof(product_case, payload):
    root, policy, manifest, _ = product_case
    if not isinstance(payload, dict):
        payload = None
    assert ProductEvidence(root, policy, manifest).check("saved_chats", payload, CHECKS)


def test_deleted_artifact_rejected(product_case):
    (product_case[0] / "client.apk").unlink()
    assert run_case(product_case)
