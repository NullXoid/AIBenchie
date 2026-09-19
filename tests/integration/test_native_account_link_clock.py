"""Account-link clock boundaries through the existing native signer and HTTPS fixture."""
import copy
import os
from pathlib import Path
import secrets
import time
from dataclasses import asdict

import pytest

from test_canvas_file_binding import native

pytestmark = pytest.mark.skipif(
    not all(os.environ.get(k) for k in ("AIBENCHIE_CANVAS_NATIVE_PROBE", "AIBENCHIE_CANVAS_BRIDGE_ROOT")),
    reason="The compiled native signer and Bridge fixture are required",
)


@pytest.mark.parametrize("case", ["small-ahead", "large-ahead", "expired", "long-lifetime", "wrong-issuer", "wrong-endpoint"])
def test_account_link_clock_boundaries(native, tmp_path, monkeypatch, case):
    monkeypatch.syspath_prepend(str(Path(os.environ["AIBENCHIE_CANVAS_BRIDGE_ROOT"]) / "backend/scripts"))
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from nullbridge_account_links import AccountLinks, PREFIX
    from nullbridge_agent_channel import IdentityPin, canonical
    from nullbridge_agent_enrollment import AgentEnrollmentRegistry, encode, sign_challenge
    from nullbridge_agent_https_fixture import HttpsFixture
    from nullbridge_agent_network import AgentNetwork

    public = native("identity")["publicKey"]
    with HttpsFixture(tmp_path / "tls", nodes=("device", "peer")) as server:
        registry = AgentEnrollmentRegistry(tmp_path / "registry.db", "clock-test")
        registry.initialize()
        peer = Ed25519PrivateKey.generate()
        challenges, pins = {}, {}
        for node, key in (("device", public), ("peer", encode(peer.public_key().public_bytes_raw()))):
            c = registry.issue(agent_id=node, workflow_node=node, public_key=key, scopes=["chat.receive", "chat.reply"])
            challenges[node] = c
            pins[node] = IdentityPin(c["requestId"], node, node, c["fingerprint"])
            if node == "peer":
                registry.prove(sign_challenge(c, peer, instance_id=registry.instance_id, agent_id=node,
                    workflow_node=node, scopes=c["scopes"], now=int(time.time())))
        conversation = secrets.token_hex(16)
        routes = [dict(sessionId=server.sessions[n]["deviceSessionId"], conversation=conversation,
            local=asdict(pins[n]), peer=asdict(pins[p])) for n, p in (("device", "peer"), ("peer", "device"))]
        network = AgentNetwork(registry, tmp_path / "relay.db", routes)
        server.server.agent_network = network
        plan = dict(server=server.base_url, instance=registry.instance_id, agent="device", node="device",
            conversation=conversation, enrollment=pins["device"].enrollment,
            enrollmentScopes=challenges["device"]["scopes"], binding="canvas", ownerPolicyVersion=2,
            issuer="permission-issuer", issuerKeyId="issuer-v1", issuerPublicKey=encode(peer.public_key().public_bytes_raw()),
            principal=dict(tenant="default", account="synthetic", subject="device", subject_key=public,
                audience="canvas", frontend="windows", protocol_version=1))
        assert native("configure", plan=plan, bearer=server.sessions["device"]["accessToken"], ca=server.ca_file.read_text())["ok"]
        assert native("enroll")["state"] == 3
        for node, c in challenges.items():
            registry.approve(c["requestId"], expected_fingerprint=c["fingerprint"], agent_id=node,
                workflow_node=node, scopes=c["scopes"])
        assert native("enroll")["state"] == 4
        offset = {"small-ahead": 3, "large-ahead": 30, "expired": -330}.get(case, 0)
        issuer, token = "https://accounts.example.test", secrets.token_hex(32)
        broker = AccountLinks(network, server.auth.store, issuer=issuer, service_token=token,
            clock=lambda: time.time() + offset)
        server.server.account_links = broker
        config = dict(server=server.base_url, bearer=server.sessions["device"]["accessToken"], issuer=issuer,
            endpoint=broker._endpoint(server.sessions["device"]["deviceSessionId"], conversation), ca=server.ca_file.read_text())
        if case == "wrong-issuer":
            config["issuer"] = "https://other.example.test"
        if case == "wrong-endpoint":
            config["endpoint"] = copy.deepcopy(config["endpoint"])
            config["endpoint"]["sessionId"] = server.sessions["peer"]["deviceSessionId"]
        if case == "long-lifetime":
            original = broker.handle
            def altered(action, body, **kwargs):
                result = original(action, body, **kwargs)
                if action == "begin":
                    result["challenge"]["expiresAt"] += 1
                return result
            monkeypatch.setattr(broker, "handle", altered)
        assert native("link-configure", **config)["ok"]
        opened = native("link-begin")
        if case != "small-ahead":
            assert opened["linkState"] == 6, opened
            assert not opened["linkTicket"]
            assert all(not row["proved"] for row in broker._pending.values())
            return
        assert opened["linkState"] == 2, opened["linkStatus"]
        assert 0 < opened["linkSeconds"] <= 300
        resumed = native("link-begin")
        assert resumed["linkTicket"] == opened["linkTicket"]
        assert resumed["linkSeconds"] <= opened["linkSeconds"]
        claim = dict(ticket=opened["linkTicket"], binding=secrets.token_hex(32), expiresAt=int(time.time()) + 90,
            account=dict(issuer=issuer, userId="synthetic-clock-account", username="Clock test"))
        status, result, _ = server.request(token, PREFIX + "service/claim", canonical(claim))
        assert status == 200 and not result["endpointConfirmed"]
        assert native("link-review")["linkState"] == 3
        assert native("link-confirm")["linkState"] == 5
        status, result, _ = server.request(token, PREFIX + "service/claim", canonical(claim))
        assert status == 200 and result["endpointConfirmed"]
        assert not result["grantsPermissions"]
