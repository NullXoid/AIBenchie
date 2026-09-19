"""Delayed setup recovery using the existing Bridge cryptographic test drivers."""
import json
import os
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace

import pytest

root = os.environ.get("AIBENCHIE_CANVAS_BRIDGE_ROOT")
if not root:
    pytest.skip("Set AIBENCHIE_CANVAS_BRIDGE_ROOT for the real Bridge driver", allow_module_level=True)
sys.path[:0] = [str(Path(root) / "backend/scripts"), str(Path(root) / "backend/tests")]

from test_agent_channel import world, connect, resign
from test_agent_network import network
from nullbridge_agent_channel import ChannelError, canonical
from nullbridge_agent_network import NetworkError
from nullbridge_agent_worker import AgentWorker


def test_unused_handshake_renews_same_keys_and_then_exchanges(network, world):
    _, call, _, _ = network
    before = {name: json.loads(endpoint.public_bundle()) for name, endpoint in (("echo", world["a"]), ("xero", world["b"]))}
    for name, bundle in before.items():
        call(name, "bundle", bundle)
    world["clock"][0] += 901
    for name, endpoint in (("echo", world["a"]), ("xero", world["b"])):
        endpoint.renew_unconnected_bundle()
        fresh = json.loads(endpoint.public_bundle())
        assert {k: v for k, v in fresh.items() if k not in {"issuedAt", "expiresAt", "signature"}} == {
            k: v for k, v in before[name].items() if k not in {"issuedAt", "expiresAt", "signature"}}
        assert fresh["expiresAt"] - fresh["issuedAt"] == 900
        assert not call(name, "bundle", fresh)["duplicate"]
        assert call(name, "bundle", fresh)["duplicate"]
    a, b = connect(world)
    mid = secrets.token_hex(16)
    wire = a.send(mid, "Delayed setup, original keys")
    call("echo", "messages", wire)
    assert b.receive(canonical(call("xero", "messages")["items"][0]))["payload"]["text"] == "Delayed setup, original keys"


@pytest.mark.parametrize("change", ["identityKey", "oneTimeKey", "early"])
def test_renewal_cannot_replace_keys_or_an_unexpired_offer(network, world, change):
    _, call, _, _ = network
    old = json.loads(world["a"].public_bundle())
    call("echo", "bundle", old)
    world["clock"][0] += 1 if change == "early" else 901
    body = {**old, "issuedAt": world["clock"][0], "expiresAt": world["clock"][0] + 900}
    if change != "early":
        body[change] = json.loads(world["b"].public_bundle())[change]
    with pytest.raises(NetworkError, match="packet_replacement_denied"):
        call("echo", "bundle", resign(world, body))
    assert call("xero", "bundle")["peerBundle"] == old


def test_established_transcript_cannot_be_renewed_or_reset(network, world):
    _, call, _, _ = network
    original = world["a"].public_bundle()
    call("echo", "bundle", original)
    a, b = connect(world)
    wire = a.send(secrets.token_hex(16), "Existing encrypted message")
    call("echo", "messages", wire)
    b.receive(wire)
    world["clock"][0] += 901
    a.renew_unconnected_bundle()
    assert a.public_bundle() == original
    body = {**json.loads(original), "issuedAt": world["clock"][0], "expiresAt": world["clock"][0] + 900}
    with pytest.raises(NetworkError, match="packet_replacement_denied"):
        call("echo", "bundle", resign(world, body))
    assert b.receive(wire)["duplicate"]


def test_revoked_identity_cannot_refresh_unused_handshake(world):
    world["clock"][0] += 901
    world["registry"].revoke(world["pins"]["echo"].enrollment)
    with pytest.raises(ChannelError):
        world["a"].renew_unconnected_bundle()


def test_worker_waits_for_stale_peer_then_uses_same_retained_channel(network, world):
    _, call, _, _ = network
    call("echo", "bundle", world["a"].public_bundle())
    call("xero", "bundle", world["b"].public_bundle())
    world["clock"][0] += 901
    worker = object.__new__(AgentWorker)
    worker.channel = world["a"]
    worker.plan = SimpleNamespace(initiator=True)
    worker._relay_acknowledged = set()
    worker.http = SimpleNamespace(request=lambda action, body=None: call("echo", action, body))
    assert worker.connect() is False
    world["b"].renew_unconnected_bundle()
    call("xero", "bundle", world["b"].public_bundle())
    assert worker.connect() is True
    world["b"].connect(worker.channel.public_bundle(), initiator=False)
    message = worker.channel.send(secrets.token_hex(16), "Retained channel recovered")
    assert world["b"].receive(message)["payload"]["text"] == "Retained channel recovered"
