"""Clock-skew regression through the existing encrypted account/native chain."""
import copy
import os
from pathlib import Path
import secrets
import time
from dataclasses import asdict

import pytest

from test_canvas_file_binding import native
from test_bridge_canvas_account import (
    chain,
    pytestmark,
    test_account_master_to_native_encrypted_save_and_denial as _exercise_chain,
)


@pytest.mark.parametrize("chain", [{"server_offset": 3}, {"server_offset": -3}],
                         indirect=True, ids=["server-ahead", "server-behind"])
def test_server_clock_registration_write_receipt_and_protection(chain):
    _exercise_chain(chain)


@pytest.mark.parametrize("case", ["large-ahead", "large-behind", "missing-time", "wrong-nonce", "expired-device"])
def test_untrusted_time_or_expired_device_never_proves(native, tmp_path, monkeypatch, case):
    monkeypatch.syspath_prepend(str(Path(os.environ["AIBENCHIE_CANVAS_BRIDGE_ROOT"]) / "backend/scripts"))
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from nullbridge_agent_channel import IdentityPin
    from nullbridge_agent_enrollment import AgentEnrollmentRegistry, encode
    from nullbridge_agent_https_fixture import HttpsFixture
    from nullbridge_agent_network import AgentNetwork

    public = native("identity")["publicKey"]
    with HttpsFixture(tmp_path / "tls", nodes=("device", "peer")) as server:
        registry = AgentEnrollmentRegistry(tmp_path / "registry.db", "clock-test")
        registry.initialize()
        peer_key = encode(Ed25519PrivateKey.generate().public_key().public_bytes_raw())
        entries = {node: registry.issue(agent_id=node, workflow_node=node, public_key=key,
                   scopes=["chat.receive", "chat.reply"]) for node, key in (("device", public), ("peer", peer_key))}
        pins = {node: IdentityPin(c["requestId"], node, node, c["fingerprint"]) for node, c in entries.items()}
        conversation = secrets.token_hex(16)
        network = AgentNetwork(registry, tmp_path / "relay.db", [dict(
            sessionId=server.sessions["device"]["deviceSessionId"], conversation=conversation,
            local=asdict(pins["device"]), peer=asdict(pins["peer"]))])
        original = network.handle
        def altered(method, path, *args, **kwargs):
            result = original(method, path, *args, **kwargs)
            if path.endswith("/setup"):
                result = copy.deepcopy(result)
                if case == "missing-time":
                    result.pop("checkedAt")
                elif case == "wrong-nonce":
                    result["nonce"] = secrets.token_hex(16)
                elif case == "expired-device":
                    result["challenge"]["credentialExpiresAt"] = int(time.time()) - 1
                else:
                    result["checkedAt"] += 30 if case == "large-ahead" else -30
            return result
        monkeypatch.setattr(network, "handle", altered)
        server.server.agent_network = network
        plan = dict(server=server.base_url, instance="clock-test", agent="device", node="device",
            conversation=conversation, enrollment=entries["device"]["requestId"],
            enrollmentScopes=entries["device"]["scopes"], binding="canvas", issuer="issuer", issuerKeyId="key",
            issuerPublicKey=peer_key, ownerPolicyVersion=2,
            principal=dict(tenant="default", account="synthetic", subject="device", subject_key=public,
                           audience="canvas", frontend="windows", protocol_version=1))
        assert native("configure", plan=plan, bearer=server.sessions["device"]["accessToken"],
                      ca=server.ca_file.read_text())["ok"]
        result = native("enroll")
        assert result["state"] == 9 and not result["document"], result
        assert registry.status(entries["device"]["requestId"])["state"] == "pending"
