"""Explicit retained-key renewal; not imported by a Bridge runtime."""
import importlib.util
import os
from pathlib import Path
import sys

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


@pytest.fixture
def registry(tmp_path):
    scripts = Path(os.environ["AIBENCHIE_CANVAS_BRIDGE_ROOT"]) / "backend/scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location("renewal_candidate", scripts / "nullbridge_agent_enrollment.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        now = [1000]
        key = Ed25519PrivateKey.generate()
        reg = module.AgentEnrollmentRegistry(tmp_path / "registry.db", "pilot", clock=lambda: now[0])
        reg.initialize()
        identity = dict(agent_id="phone", workflow_node="phone", scopes=["chat.receive", "chat.request"])
        initial = reg.issue(**identity, public_key=module.encode(key.public_key().public_bytes_raw()), credential_seconds=900)
        proof = module.sign_challenge(initial, key, instance_id="pilot", now=now[0], **identity)
        reg.prove(proof)
        reg.approve(initial["requestId"], expected_fingerprint=initial["fingerprint"], **identity)
        yield module, reg, now, key, identity, initial, proof
    finally:
        sys.path.remove(str(scripts))


def test_renew_requires_new_proof_and_keeps_exact_identity(registry):
    mod, reg, now, key, identity, old, old_proof = registry
    now[0] = 1900
    new = reg.renew(old["requestId"], expected_fingerprint=old["fingerprint"], **identity)
    for field in ("publicKey", "fingerprint", "requestId", "agentId", "workflowNode", "scopes"):
        assert new[field] == old[field]
    assert new["nonce"] != old["nonce"]
    assert not reg.status(old["requestId"])["identityApproved"]
    with pytest.raises(mod.EnrollmentError, match="invalid_key_proof"):
        reg.prove(old_proof)
    reg.prove(mod.sign_challenge(new, key, instance_id="pilot", now=now[0], **identity))
    result = reg.approve(new["requestId"], expected_fingerprint=old["fingerprint"], **identity)
    assert result["identityApproved"] and result["expiresAt"] == 1900 + 604800


@pytest.mark.parametrize("change", ["live", "revoked", "scope", "key", "duration"])
def test_renew_cannot_override_authority(registry, change):
    mod, reg, now, _, identity, old, _ = registry
    now[0] = 1900 if change != "live" else 1001
    kwargs = dict(identity, expected_fingerprint=old["fingerprint"])
    if change == "revoked":
        reg.revoke(old["requestId"])
    if change == "scope":
        kwargs["scopes"] = ["chat.reply"]
    if change == "key":
        kwargs["expected_fingerprint"] = "ed25519:" + "0" * 64
    if change == "duration":
        kwargs["credential_seconds"] = 604801
    before = reg.status(old["requestId"])
    with pytest.raises(mod.EnrollmentError):
        reg.renew(old["requestId"], **kwargs)
    assert reg.status(old["requestId"]) == before
