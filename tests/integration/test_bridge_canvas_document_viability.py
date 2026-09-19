"""Production Canvas binding in a disposable controller, not physical acceptance."""
from __future__ import annotations

import hashlib
import json
import secrets
import time

import pytest

from test_bridge_canvas_account import chain, pytestmark


@pytest.mark.parametrize("chain", [{"canvas_generated": True}], indirect=True)
def test_existing_bridge_can_feed_real_canvas_controller_with_explicit_adapter(chain):
    from nullbridge_file_dispatcher import SAVED, STOPPED

    w = chain
    phone, dispatcher = w["phone"], w["dispatcher"]

    def pump(condition, timeout=45):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            assert not w["pump_errors"], w["pump_errors"]
            native = w["owner"]("pump", milliseconds=50)
            assert native["listenerRunning"], native["listenerStatus"]
            assert not native["canvas"]["error"], native["canvas"]
            state = dispatcher.step()
            assert state["state"] != "file_setup_required", state
            phone.exchange()
            if condition(state, native):
                return state, native
        raise AssertionError(f"Canvas experiment timed out: {state}")

    def reply(rid):
        return next((m["text"] for m in phone.channel.saved_messages() if m["replyTo"] == rid), None)

    def decide(rid, kind, decision="approve"):
        body = dict(linkId=w["owner_link"]["linkId"], requestId=rid, kind=kind)
        if kind == "protected":
            body.update(mode="once", lifetimeSeconds=30)
        review = w["approvals"].review(*w["actor"], body)
        return w["approvals"].decide(*w["actor"],
            dict(reviewId=review["reviewId"], decision=decision, confirm=True))

    def documents():
        return {d["resource"]: d for d in w["owner"]("canvas-state")["canvas"]["documents"]}

    def append(marker, target="standard"):
        rid = secrets.token_hex(16)
        phone.send(rid, f"Append {marker} to {target}.txt")
        state, _ = pump(lambda s, _: s["state"] == "awaiting_master_approval")
        decide(state["requestId"], "command")
        return rid

    initial = documents()
    assert all(p.read_text() == "Initial\n" for p in w["files"].values())
    pump(lambda *_: phone.connect())
    before = secrets.token_hex(16)
    phone.send(before, "Append Baseline to standard.txt")
    state, _ = pump(lambda s, _: s["state"] == "awaiting_master_file_approval")
    assert w["files"]["standard"].read_text() == "Initial\n"
    decide(state["requestId"], "license")
    state, _ = pump(lambda s, _: s["state"] == "awaiting_master_approval")
    decide(state["requestId"], "command")
    pump(lambda *_: reply(before) is not None)
    assert reply(before) == SAVED
    assert w["files"]["standard"].read_text() == "Initial\nBaseline\n"
    assert documents()["standard"]["text"] == "Initial\n", "Baseline unexpectedly connected to Canvas"

    w["owner"]("canvas-connect")
    rid = append("Connected")
    pump(lambda *_: reply(rid) is not None)
    assert reply(rid) == SAVED
    updated = documents()
    assert updated["standard"]["id"] == initial["standard"]["id"]
    assert updated["standard"]["text"] == w["files"]["standard"].read_text() == "Initial\nBaseline\nConnected\n"
    assert updated["elevated"]["text"] == "Initial\n"

    # A transport retry must not reapply the append to disk or the document.
    calls = w["planner"].calls
    phone.send(rid, "Append Connected to standard.txt")
    for _ in range(2):
        pump(lambda *_: True)
    assert w["planner"].calls == calls
    assert documents()["standard"]["text"].count("Connected") == 1
    assert w["files"]["standard"].read_text().count("Connected") == 1

    denied = append("NotAllowed", "elevated")
    _, native = pump(lambda _, n: n["protectedRequest"].get("state") == "pending")
    assert documents()["elevated"]["text"] == w["files"]["elevated"].read_text() == "Initial\n"
    decide(native["protectedRequest"]["requestId"], "protected", "deny")
    pump(lambda *_: reply(denied) is not None)
    assert reply(denied) == STOPPED
    assert documents()["elevated"]["text"] == w["files"]["elevated"].read_text() == "Initial\n"

    w["owner"]("canvas-edit", id=updated["standard"]["id"], text="Unsaved local work\n")
    blocked = append("MustNotOverwrite")
    pump(lambda *_: reply(blocked) is not None)
    assert reply(blocked) == STOPPED
    assert documents()["standard"]["text"] == "Unsaved local work\n"
    assert w["files"]["standard"].read_text() == "Initial\nBaseline\nConnected\n"

    snapshot = w["owner"]("canvas-state")["canvas"]
    assert snapshot["notifications"] == 2 and snapshot["updates"] == 1
    assert not snapshot["error"]
    assert snapshot["testOnlyAdapter"] is False and snapshot["unsaved"] is True
    evidence = dict(syntheticEnvironment=True, productionAdapter=True, physicalPhone=False, deployed=False,
        baseline="disk save succeeds; internal Canvas draft remains unchanged",
        adapter="production CanvasFileBridge reloads the existing Canvas document after verified save",
        requestId=rid, phoneReply=reply(rid), native=snapshot,
        persistedSha256=hashlib.sha256(w["files"]["standard"].read_bytes()).hexdigest(),
        duplicateAppend=False, elevatedDenied=True, unsavedWorkProtected=True,
        verifiedSavedDocument=updated["standard"])
    (w["root"] / "canvas-viability.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
