"""Bridge approval with the production account transaction guard enabled.

The existing HTTPS/native driver supplies synthetic identities. Only the
independent ledger transport is in-process; its ledger, encryption, transaction
guard and admission queue are the product implementations.
"""
import os
import json
import secrets
import sqlite3
import time
from types import SimpleNamespace

import pytest

from test_bridge_canvas_account import chain, pytestmark


def guard_accounts(root, monkeypatch):
    from backend import account_state_guard as guard, auth_store
    from backend.account_state_reference import AuthStateLedger

    config = object.__new__(guard.GuardConfig)
    config.binding = "aibenchie-bridge-guard"
    config.key = os.urandom(32)
    config.store = secrets.token_hex(32)
    config.transport = SimpleNamespace(authority=secrets.token_hex(32))
    ledger = AuthStateLedger(root / "reference.db", config.transport.authority)
    ledger.create()
    active = root / "guarded-account.db"
    packet = guard.prepare_enrollment(auth_store.DB_PATH, active, config)
    ledger.enroll(config.store, packet["head"], packet["snapshot"])
    config.client = SimpleNamespace(
        check=lambda head: ledger.check(config.store, head),
        advance=lambda before, after, image: ledger.advance(config.store, before, after, image),
    )

    def connect():
        db = sqlite3.connect(active, timeout=.25)
        db.row_factory = sqlite3.Row
        return guard.GuardedConnection(db, config)

    monkeypatch.delenv("NX_ACCOUNT_ADMISSION_SOCKET", raising=False)
    monkeypatch.setattr(auth_store, "DB_PATH", active)
    monkeypatch.setattr(auth_store, "_connect", connect)
    return ledger, config


def test_file_and_command_review_with_guarded_endpoint_links(chain, monkeypatch):
    from backend import auth_store
    from fastapi import HTTPException

    w = chain
    ledger, config = guard_accounts(w["root"], monkeypatch)
    original = ledger.recover(config.store)
    phone, dispatcher = w["phone"], w["dispatcher"]
    end = time.monotonic() + 15
    while not phone.connect() and time.monotonic() < end:
        dispatcher.step()
    assert phone.connect()
    message = secrets.token_hex(16)
    phone.send(message, "Append Guarded to standard.txt")
    state = dispatcher.step()
    assert state["state"] == "awaiting_master_file_approval"
    service = w["approvals"]

    def review(request_id, kind):
        return service.review(*w["actor"], dict(linkId=w["owner_link"]["linkId"],
            requestId=request_id, kind=kind))

    reviewed = review(state["requestId"], "license")
    service.decide(*w["actor"], dict(reviewId=reviewed["reviewId"], decision="approve", confirm=True))
    state = dispatcher.step()
    assert state["state"] == "awaiting_master_approval"
    reviewed = review(state["requestId"], "command")
    assert reviewed["decisionRequired"] and reviewed["kind"] == "command"
    assert ledger.recover(config.store) == original, "Reads must not advance account state"
    assert w["files"]["standard"].read_text() == "Initial\n"

    # Closing the enumeration transaction must not omit fresh linked-session checks.
    with auth_store._connect() as db:
        db.execute("UPDATE account_endpoint_links SET revoked_at=? WHERE id=?",
                   (int(time.time()), w["phone_link"]["linkId"]))
    with pytest.raises(HTTPException):
        service.decide(*w["actor"], dict(reviewId=reviewed["reviewId"], decision="approve", confirm=True))
    assert w["files"]["standard"].read_text() == "Initial\n"
    assert not any(record.wire for record in w["authority"]._commands.values())


def test_built_dispatcher_shares_existing_pacer_across_all_channels(chain):
    from nullbridge_agent_worker_transport import RequestPacer
    from nullbridge_agent_worker_vault import protect
    from nullbridge_file_dispatcher import build_dispatcher

    w = chain
    built = dict(w["builder"])
    vault = w["root"] / "built.vault"
    vault.write_bytes(protect(json.dumps(built.pop("vault")).encode()))
    config = w["root"] / "dispatcher.json"
    config.write_text(json.dumps(dict(built, version=1, lanAddress=None,
        model=dict(runtime="ollama", base_url="http://127.0.0.1:11434", model="test"),
        sshRoute=None, fileDocument=None, commandDocument=None,
        targets=w["dispatcher"].targets, commandSourceId="phone", bindingId="canvas")))
    dispatcher, notices = build_dispatcher(config, vault,
        w["root"] / "built-source.db", w["root"] / "built-owner.db")
    clients = [dispatcher.source.http, dispatcher.owner.http,
               notices["source"], notices["owner"], notices["permission"].http]
    assert isinstance(clients[0].pacer, RequestPacer)
    assert all(client.pacer is clients[0].pacer for client in clients)


def _send_file_request(w, text):
    phone, dispatcher = w["phone"], w["dispatcher"]
    end = time.monotonic() + 15
    while not phone.connect() and time.monotonic() < end:
        dispatcher.step()
    assert phone.connect()
    message = secrets.token_hex(16)
    phone.send(message, text)
    return message


def test_file_challenge_refreshes_authenticated_time_after_response(chain, monkeypatch):
    w = chain
    message = _send_file_request(w, "Append Tick to standard.txt")
    dispatcher, http = w["dispatcher"], w["dispatcher"].source.http
    original = http.request
    dispatcher.clock = http.server_now
    calls = []

    def across_tick(action, *args, **kwargs):
        result = original(action, *args, **kwargs)
        calls.append(action)
        if action == "file-request":
            # Model the prior whole-second anchor lagging the response by one tick.
            http.anchor = (result["challenge"]["issuedAt"] - 1, time.monotonic())
        return result

    monkeypatch.setattr(http, "request", across_tick)
    state = dispatcher.step()
    assert state["state"] == "awaiting_master_file_approval"
    request_index = calls.index("file-request")
    assert calls[request_index + 1] == "authority"
    assert dispatcher.source.channel.file_permission_request(message) is not None
    assert w["files"]["standard"].read_text() == "Initial\n"


def test_lost_challenge_expiry_finishes_without_new_grant_or_setup_loop(chain, monkeypatch):
    from nullbridge_agent_worker_transport import WorkerError
    from nullbridge_file_dispatcher import PERMISSION_FAILED

    w = chain
    message = _send_file_request(w, "Append Lost to standard.txt")
    dispatcher, http = w["dispatcher"], w["dispatcher"].source.http
    original = http.request
    lost = []

    def lose_response(action, *args, **kwargs):
        result = original(action, *args, **kwargs)
        if action == "file-request" and not lost:
            lost.append(result["challenge"]["requestId"])
            raise WorkerError("agent_transport_unavailable")
        return result

    monkeypatch.setattr(http, "request", lose_response)
    with pytest.raises(WorkerError, match="agent_transport_unavailable"):
        dispatcher.step()
    assert dispatcher.source.channel.file_permission_request(message) is None
    w["authority"]._requests[lost[0]].expires = int(time.time()) - 1
    state = dispatcher.step()
    assert state["state"] == "file_permission_unavailable"
    w["phone"].exchange()
    replies = [m for m in w["phone"].channel.saved_messages() if m["replyTo"] == message]
    assert len(replies) == 1 and replies[0]["text"] == PERMISSION_FAILED
    assert set(w["authority"]._requests) == set(lost)
    assert not w["authority"]._issued
    assert w["files"]["standard"].read_text() == "Initial\n"


def test_selected_owner_evidence_stays_fresh_before_file_approval(chain):
    from nullbridge_file_dispatcher import SAVED

    w = chain
    end = time.monotonic() + 15
    while w["owner"]("pump", milliseconds=100)["state"] != 4 and time.monotonic() < end:
        pass
    assert w["owner"]("pump", milliseconds=10)["state"] == 4
    first_expiry = w["authority"]._owner_versions["canvas"][1]
    # Real native timer and HTTPS publication, beyond the initial 30-second lease.
    time.sleep(max(0, first_expiry - time.time()) + 2)
    native = w["owner"]("pump", milliseconds=10)
    assert not w["pump_errors"], w["pump_errors"]
    versions, expiry = w["authority"]._owner_versions["canvas"]
    assert expiry > int(time.time()), ("Selected-file evidence expired before approval", native)
    assert native["state"] == 4 and native["listenerRunning"], native
    assert not w["authority"]._issued
    assert len(versions) == 2
    message = _send_file_request(w, "Append Waited to standard.txt")
    state = w["dispatcher"].step()
    review = w["approvals"].review(*w["actor"], dict(linkId=w["owner_link"]["linkId"],
        requestId=state["requestId"], kind="license"))
    w["approvals"].decide(*w["actor"], dict(reviewId=review["reviewId"], decision="approve", confirm=True))
    state = w["dispatcher"].step()
    assert state["state"] == "awaiting_master_approval"
    assert w["files"]["standard"].read_text() == "Initial\n"
    review = w["approvals"].review(*w["actor"], dict(linkId=w["owner_link"]["linkId"],
        requestId=state["requestId"], kind="command"))
    w["approvals"].decide(*w["actor"], dict(reviewId=review["reviewId"], decision="approve", confirm=True))
    end, replies = time.monotonic() + 45, []
    while not replies and time.monotonic() < end:
        w["dispatcher"].step()
        w["phone"].exchange()
        replies = [m for m in w["phone"].channel.saved_messages() if m["replyTo"] == message]
        time.sleep(.05)
    assert len(replies) == 1 and replies[0]["text"] == SAVED
    assert w["files"]["standard"].read_text() == "Initial\nWaited\n"
    assert w["files"]["elevated"].read_text() == "Initial\n"
