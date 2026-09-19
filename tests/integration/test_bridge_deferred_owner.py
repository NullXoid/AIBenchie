"""Chat and approval stay usable while Windows file setup is unfinished."""
import os
from pathlib import Path
import secrets
import sys

import pytest

root = os.environ.get("AIBENCHIE_CANVAS_BRIDGE_ROOT")
if not root:
    pytest.skip("Set AIBENCHIE_CANVAS_BRIDGE_ROOT for the real Bridge driver", allow_module_level=True)
sys.path[:0] = [str(Path(root) / "backend/scripts"), str(Path(root) / "backend/tests")]

from test_file_dispatcher import guided, dispatch, gate, world, rig
from nullbridge_file_dispatcher import SAVED


def test_chat_and_pending_approval_do_not_start_windows_handshake(guided):
    t = guided
    def not_ready(**kwargs):
        raise AssertionError("Windows transport must not run before approval")
    t.owner.exchange = not_ready
    mid = secrets.token_hex(16)
    t.source.channel.receive(t.w["phone"].send(mid, "Hello while setup is unfinished"))
    assert t.guided.step()["state"] == "awaiting_master_approval"
    assert any(m["replyTo"] == mid and m["text"] == "Chat reply: Hello while setup is unfinished"
               for m in t.w["phone"].saved_messages())
    assert not t.owner.sent and t.model.calls == 0 and t.reply() is None
    t.phase = "denied"
    assert t.guided.step({"permission"})["state"] == "denied"
    assert not t.owner.sent and t.model.calls == 0


def test_approved_command_waits_for_windows_then_retries_without_duplicate(guided):
    t = guided
    assert t.guided.step()["state"] == "awaiting_master_approval"
    t.phase = "approved"
    exchange = t.owner.exchange
    t.owner.exchange = lambda **kwargs: {"state": "waiting_for_peer"}
    assert t.guided.step({"permission"})["state"] == "waiting_for_peer"
    assert not t.owner.sent and t.model.calls == 0
    t.owner.exchange = exchange
    assert t.guided.step()["state"] == "waiting_for_verified_file_result"
    assert len(t.owner.sent) == 1 and t.model.calls == 1
    t.guided.step()
    assert len(t.owner.sent) == 1 and t.model.calls == 1
    t.result()
    t.guided.step({"owner"})
    assert t.reply() == SAVED
