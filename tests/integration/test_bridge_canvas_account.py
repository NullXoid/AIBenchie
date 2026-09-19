"""AIBenchie-owned account -> encrypted Bridge -> compiled Windows integration.

Disposable accounts and selected files only. This is not a physical phone/UI
verdict. No test hooks, accounts, or runner are installed in the product.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import secrets
import socket
import subprocess
import sys
import threading
import time
from dataclasses import asdict

import pytest

pytestmark = pytest.mark.skipif(
    not all(os.environ.get(k) for k in ("AIBENCHIE_CANVAS_ACCOUNT_ROOT", "AIBENCHIE_CANVAS_BRIDGE_ROOT", "AIBENCHIE_CANVAS_NATIVE_PROBE")),
    reason="Use the explicit AIBenchie Bridge/Canvas gate; missing prerequisites are blocked there, never pass.",
)


@pytest.fixture
def chain(tmp_path, monkeypatch, request):
    canvas_generated = getattr(request, "param", {}).get("canvas_generated", False)
    server_offset = getattr(request, "param", {}).get("server_offset", 0)
    server_clock = lambda: time.time() + server_offset
    account = Path(os.environ["AIBENCHIE_CANVAS_ACCOUNT_ROOT"]).resolve()
    bridge = Path(os.environ["AIBENCHIE_CANVAS_BRIDGE_ROOT"]).resolve()
    probe = Path(os.environ["AIBENCHIE_CANVAS_NATIVE_PROBE"]).resolve()
    monkeypatch.syspath_prepend(str(account))
    monkeypatch.syspath_prepend(str(bridge / "backend/scripts"))
    from backend import account_approvals, account_authority, account_links, auth, auth_store
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from fastapi import FastAPI, Request
    import uvicorn
    from nullbridge_agent_https_fixture import HttpsFixture
    from nullbridge_agent_enrollment import AgentEnrollmentRegistry, encode, sign_challenge
    from nullbridge_agent_channel import IdentityPin, PROTOCOL, canonical
    from nullbridge_agent_network import AgentNetwork
    from nullbridge_agent_approvals import AgentApprovals
    from nullbridge_account_links import AccountLinks, PREFIX as LINK, DOMAIN, CONSENT_DOMAIN
    from nullbridge_account_permissions import AccountPermissionAuthority, AccountAuthorityClient
    from nullbridge_command_permissions import CommandSource, CommandPermissionGateway
    from nullbridge_permission_authority import ResourceBinding, ResourceOwner
    from nullbridge_permission_grants import Principal, Scope
    from nullbridge_agent_worker import AgentWorker
    from nullbridge_agent_worker_transport import AgentHttpsClient, WorkerPlan
    from nullbridge_agent_worker_vault import EndpointVault, protect
    from nullbridge_file_dispatcher import ApprovedFileConversation

    monkeypatch.setattr(auth_store, "DB_PATH", tmp_path / "account.db")
    monkeypatch.setattr(auth_store, "ADMIN_BOOTSTRAPPED", False)
    monkeypatch.delenv("NX_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("NX_AUTH_CONFIG", raising=False)
    auth_store.init_db()
    uid = auth_store.create_user("canvas-test-master", secrets.token_urlsafe(32), "admin")
    issuer = "https://accounts.example.test"
    policy = tmp_path / "account-policy.json"
    policy.write_text(json.dumps(dict(version=1, issuer=issuer, tenantId="default", revision=1, masterUserIds=[uid])))
    policy.chmod(0o600)
    monkeypatch.setenv(account_authority.POLICY_ENV, str(policy))
    sid = auth_store.create_session(uid, auth.hash_token(secrets.token_urlsafe(32)), "web", "127.0.0.1",
        auth.hash_token(secrets.token_urlsafe(32)), auth_method="password")
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    request.state.auth_type, request.state.session_id = "session", sid
    actor = (request, auth_store.get_user_by_id(uid))

    with (tmp_path / "native.stderr").open("w") as errors:
        native = subprocess.Popen([str(probe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=errors, text=True, encoding="utf-8")
        replies = queue.Queue()
        def read_native():
            for line in native.stdout:
                replies.put(line)
            replies.put(None)
        reader = threading.Thread(target=read_native, daemon=True)
        reader.start()
        native_lock = threading.Lock()
        def owner(action, **body):
            with native_lock:
                native.stdin.write(json.dumps(dict(action=action, **body)) + "\n")
                native.stdin.flush()
                line = replies.get(timeout=45)
                assert line is not None, "Native test process exited"
                result = json.loads(line)
                assert result["ok"], (action, result["error"], result["status"])
                return result
        api_server = api_thread = sock = None
        pump_stop, pump_thread, pump_errors = threading.Event(), None, []
        try:
            public = owner("identity")["publicKey"]
            with HttpsFixture(tmp_path / "tls", nodes=("owner", "agent", "phone", "transport", "operator")) as server:
                registry = AgentEnrollmentRegistry(tmp_path / "registry.db", "canvas-test", clock=server_clock)
                registry.initialize()
                keys = {n: Ed25519PrivateKey.generate() for n in ("agent", "phone", "transport")}
                chat_scopes = ["chat.receive", "chat.reply", "chat.request"]
                enrolled = {}
                for name in ("owner", *keys):
                    enrolled[name] = registry.issue(agent_id=name, workflow_node=name,
                        public_key=public if name == "owner" else encode(keys[name].public_key().public_bytes_raw()), scopes=chat_scopes)
                    if name in keys:
                        registry.prove(sign_challenge(enrolled[name], keys[name], instance_id="canvas-test",
                            agent_id=name, workflow_node=name, scopes=chat_scopes, now=int(server_clock())))
                def pin(name):
                    c = enrolled[name]
                    return IdentityPin(c["requestId"], name, name, c["fingerprint"])
                input_conv, owner_conv, native_conv = [secrets.token_hex(16) for _ in range(3)]
                def route(local, peer, conversation):
                    return dict(sessionId=server.sessions[local]["deviceSessionId"], conversation=conversation,
                        local=asdict(pin(local)), peer=asdict(pin(peer)))
                routes = [route("owner", "agent", native_conv), route("agent", "owner", native_conv),
                    route("agent", "transport", owner_conv), route("transport", "agent", owner_conv),
                    route("phone", "agent", input_conv), route("agent", "phone", input_conv)]
                network = AgentNetwork(registry, tmp_path / "relay.db", routes, clock=server_clock)
                token = secrets.token_hex(32)
                broker = AccountLinks(network, server.auth.store, issuer=issuer, service_token=token, clock=server_clock)
                server.server.agent_network, server.server.account_links = network, broker
                links = account_links.AccountLinks(account_links.BridgeClient(base_url=server.base_url,
                    instance="canvas-test", issuer=issuer, service_token=token, ca_file=str(server.ca_file)),
                    authentication_policy="account-session", clock=server_clock)
                approvals = account_approvals.AccountApprovals(links, validation_token=secrets.token_hex(32))
                app = FastAPI()
                async def validate(req):
                    return approvals.validate(req.headers.get("authorization", "").removeprefix("Bearer "), await req.json())
                validate.__annotations__["req"] = Request
                app.post("/auth/nullbridge/command-approvals/validate")(validate)
                sock = socket.socket()
                sock.bind(("127.0.0.1", 0))
                address = "https://127.0.0.1:" + str(sock.getsockname()[1])
                api_server = uvicorn.Server(uvicorn.Config(app, lifespan="off", access_log=False, log_level="error",
                    ssl_certfile=str(tmp_path / "tls/server.pem"), ssl_keyfile=str(tmp_path / "tls/server-key.pem")))
                api_thread = threading.Thread(target=api_server.run, kwargs={"sockets": [sock]}, daemon=True)
                api_thread.start()
                deadline = time.monotonic() + 10
                while not api_server.started and time.monotonic() < deadline:
                    time.sleep(.01)
                assert api_server.started
                operator = tmp_path / "operator.json"
                operator.write_bytes(canonical(dict(version=1, instance="canvas-test", registry=str(registry.path), masters=[dict(
                    sessionId=server.sessions["operator"]["deviceSessionId"], workflowNode="operator",
                    expiresAt=int(time.time()) + 1800, requestIds=[c["requestId"] for c in enrolled.values()])])))
                control = AgentApprovals(operator, session_store=server.auth.store, clock=server_clock)
                def principal(name, frontend):
                    return Principal("default", uid, name, enrolled[name]["publicKey"], "canvas", frontend, 1)
                def endpoint(name, frontend):
                    return ResourceOwner(principal(name, frontend), server.sessions[name]["deviceSessionId"],
                        pin(name).enrollment, name)
                resources = frozenset(Scope("workspace", n, a) for n in ("standard", "elevated") for a in ("file.read", "file.write"))
                def forbidden(_):
                    raise AssertionError("Server cannot inspect native file contents")
                binding = ResourceBinding(principal("agent", "agent"), server.sessions["agent"]["deviceSessionId"],
                    pin("agent").enrollment, "agent", resources, 900, forbidden)
                signing = Ed25519PrivateKey.generate()
                authority = AccountPermissionAuthority(control, issuer="canvas-issuer", key_id="key", signing_key=signing,
                    clock=server_clock,
                    bindings={"canvas": binding}, owners={"canvas": endpoint("owner", "windows")}, wait_seconds=1,
                    account_links=broker, account_validator=AccountAuthorityClient(address, approvals._token, ca_data=server.ca_file.read_text()),
                    command_sources={"phone": CommandSource(endpoint("phone", "android"), "canvas", input_conv, owner_conv,
                        frozenset(s for s in resources if s.action == "file.write"), 900, endpoint("transport", "windows"))})
                broker.permission_authority = authority
                account_handle = authority.account_handle
                delayed_review = False
                def observed_action(action, body):
                    nonlocal delayed_review
                    try:
                        if action == "command-review" and not delayed_review:
                            delayed_review = True
                            time.sleep(1.1)  # Cross a real clock tick only in the test process.
                        return account_handle(action, body)
                    except Exception as exc:
                        print("Account/Bridge action failed:", action, type(exc).__name__, str(exc))
                        raise
                monkeypatch.setattr(authority, "account_handle", observed_action)
                server.server.agent_approvals = CommandPermissionGateway(control, authority)
                def http(name, path, body=None):
                    status, result, _ = server.request(server.sessions[name]["accessToken"], path,
                        None if body is None else canonical(body))
                    assert status == 200, (path, status, result.get("error"))
                    return result
                native_plan = dict(server=server.base_url, instance="canvas-test", agent="owner", node="owner",
                    conversation=native_conv, enrollment=pin("owner").enrollment, enrollmentScopes=chat_scopes,
                    binding="canvas", principal=asdict(principal("owner", "windows")), requester=asdict(binding.principal),
                    issuer="canvas-issuer", issuerKeyId="key", issuerPublicKey=encode(signing.public_key().public_bytes_raw()),
                    ownerPolicyVersion=2, verifiedWriteContinuity=True)
                owner("configure", plan=native_plan, bearer=server.sessions["owner"]["accessToken"], ca=server.ca_file.read_text())
                assert owner("enroll")["state"] == 3
                for name, c in enrolled.items():
                    registry.approve(c["requestId"], expected_fingerprint=c["fingerprint"], agent_id=name,
                        workflow_node=name, scopes=chat_scopes)
                assert owner("enroll")["state"] == 4
                # Exercise native signing and reciprocal consent, not database link insertion.
                owner("link-configure", server=server.base_url, issuer=issuer,
                    bearer=server.sessions["owner"]["accessToken"], ca=server.ca_file.read_text(),
                    endpoint=broker._endpoint(server.sessions["owner"]["deviceSessionId"], native_conv))
                ticket = owner("link-begin")["linkTicket"]
                review = links.review(*actor, {"ticket": ticket})
                confirmation = {"reviewId": review["reviewId"], "confirm": True}
                assert links.confirm(*actor, confirmation)["state"] == "awaiting_endpoint_confirmation"
                assert owner("link-review")["linkAccount"]["userId"] == uid
                owner("link-confirm")
                owner_link = links.confirm(*actor, confirmation)
                begun = http("phone", LINK + "begin", {"conversation": input_conv})
                http("phone", LINK + "prove", dict(ticket=begun["ticket"],
                    signature=encode(keys["phone"].sign(DOMAIN + b"\n" + canonical(begun["challenge"])))))
                review = links.review(*actor, {"ticket": begun["ticket"]})
                confirmation = {"reviewId": review["reviewId"], "confirm": True}
                links.confirm(*actor, confirmation)
                consent = http("phone", LINK + "consent-review", {"ticket": begun["ticket"]})
                http("phone", LINK + "consent-prove", dict(ticket=begun["ticket"],
                    signature=encode(keys["phone"].sign(CONSENT_DOMAIN + b"\n" + canonical(consent["challenge"])))))
                phone_link = links.confirm(*actor, confirmation)
                files = {n: tmp_path / (n + ".txt") for n in ("standard", "elevated")}
                for name, p in files.items():
                    if canvas_generated:
                        result = owner("canvas-create", name=name + ".txt", text="Initial\n",
                            workspace="workspace", resource=name)
                        document = next(d for d in result["canvas"]["documents"] if d["resource"] == name)
                        files[name] = Path(document["path"])
                    else:
                        p.write_text("Initial\n", encoding="utf-8")
                owner("register-files", files=[dict(workspace="workspace", resource=n, path=str(p), writable=True) for n, p in files.items()])
                owner("protect-file", path=str(files["elevated"]))
                owner("publish")
                def worker(name, peer, conv, state):
                    plan = dict(version=1, protocol=PROTOCOL, baseUrl=server.base_url,
                        instance="canvas-test", conversation=conv, sessionId=server.sessions[name]["deviceSessionId"],
                        local=asdict(pin(name)), peer=asdict(pin(peer)), initiator=name in {"phone", "agent"} and peer != "phone")
                    doc = dict(version=1, binding=dict(baseUrl=server.base_url, sessionId=plan["sessionId"],
                        instance="canvas-test", agent=name, node=name), token=server.sessions[name]["accessToken"],
                        signing=encode(keys[name].private_bytes_raw()), storage=encode(secrets.token_bytes(32)))
                    vault = EndpointVault(doc)
                    return AgentWorker(AgentHttpsClient(WorkerPlan.parse(plan), vault.token, context=server.context),
                        vault, tmp_path / state, None), plan, doc
                source, source_plan, source_doc = worker("agent", "phone", input_conv, "source.db")
                phone, _, _ = worker("phone", "agent", input_conv, "phone.db")
                transport, transport_plan, transport_doc = worker("transport", "agent", owner_conv, "transport.db")
                remote, remote_plan, _ = worker("agent", "transport", owner_conv, "remote.db")
                vault_path = tmp_path / "transport.vault"
                vault_path.write_bytes(protect(canonical(transport_doc)))
                config = tmp_path / "pipe.json"
                config.write_bytes(canonical(dict(version=1, plan=transport_plan, lanAddress=None, caFile=str(server.ca_file))))
                # Same owner-signed registration as "Register selected files"
                # in Windows. It grants nothing and must precede account review;
                # the encrypted file handshake can wait until approval is ready.
                owner("publish")
                owner("listen", program=sys.executable, arguments=[str(Path(__file__).with_name("bridge_owner_probe.py")),
                    "--bridge", str(bridge), "--diagnostics", str(tmp_path / "pipe-diagnostics.log"),
                    "--config", str(config), "--vault", str(vault_path), "--state", str(tmp_path / "transport.db")],
                    transportPlan=transport_plan, scopes=[asdict(s) for s in sorted(resources)], approvalDecision="deny")
                class Planner:
                    calls = 0
                    def generate_nullbridge_reply(self, text):
                        return "Ordinary chat reply"
                    def plan_nullbridge_append(self, text, selected):
                        self.calls += 1
                        _, marker, _, name = text.split()
                        return canonical(dict(action="append", target=name, text=marker + "\n")).decode()
                planner = Planner()
                targets = {n + ".txt": asdict(Scope("workspace", n, "file.write")) for n in files}
                dispatcher = ApprovedFileConversation(source, remote, model=planner, targets=targets,
                    source_id="phone", binding_id="canvas", file_wire=None,
                    trusted_keys=lambda: authority.trusted_keys, clock=lambda: int(server_clock()))
                # The stdin probe otherwise suspends Qt while Python does HTTPS
                # work. Keep its event loop live, like the actual desktop app.
                def keep_native_responsive():
                    try:
                        while not pump_stop.is_set():
                            owner("pump", milliseconds=25)
                            pump_stop.wait(.005)
                    except Exception as exc:
                        pump_errors.append(str(exc))
                pump_thread = threading.Thread(target=keep_native_responsive, daemon=True)
                pump_thread.start()
                yield dict(owner=owner, phone=phone, dispatcher=dispatcher, files=files, approvals=approvals, links=links,
                    actor=actor, owner_link=owner_link, phone_link=phone_link, planner=planner, root=tmp_path,
                    authority=authority, pump_errors=pump_errors,
                    builder=dict(inputPlan=source_plan, ownerPlan=remote_plan, vault=source_doc,
                        caFile=str(server.ca_file), issuer=dict(issuer="canvas-issuer", keyId="key",
                            publicKey=encode(signing.public_key().public_bytes_raw()))))
        finally:
            pump_stop.set()
            if pump_thread:
                pump_thread.join(timeout=5)
            if api_server:
                api_server.should_exit = True
                api_thread.join(timeout=10)
            if sock:
                sock.close()
            if native.poll() is None:
                native.stdin.write('{"action":"exit"}\n')
                native.stdin.flush()
                try:
                    native.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    native.kill()
                    native.wait(timeout=5)
            reader.join(timeout=2)


def test_account_master_to_native_encrypted_save_and_denial(chain):
    from nullbridge_file_dispatcher import CLARIFY, SAVED, STOPPED
    w = chain
    phone, dispatcher, files = w["phone"], w["dispatcher"], w["files"]
    def pump(condition, timeout=45):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            assert not w["pump_errors"], w["pump_errors"]
            native = w["owner"]("pump", milliseconds=50)
            diagnostics = w["root"] / "pipe-diagnostics.log"
            assert native["listenerRunning"], (json.dumps(native), diagnostics.read_text() if diagnostics.exists() else "No pipe error")
            state = dispatcher.step()
            assert state["state"] != "file_setup_required", (state, w["authority"]._selected)
            phone.exchange()
            if condition(state, native):
                return state, native
        raise AssertionError("Combined account/native chain did not reach expected state: " + str(state))
    def reply(rid):
        return next((m["text"] for m in phone.channel.saved_messages() if m["replyTo"] == rid), None)
    def decide(rid, kind, decision="approve"):
        body = dict(linkId=w["owner_link"]["linkId"], requestId=rid, kind=kind)
        if kind == "protected":
            body.update(mode="once", lifetimeSeconds=30)
        try:
            review = w["approvals"].review(*w["actor"], body)
        except Exception:
            print("Review timing:", [(r["action"], r["reviewUntil"], r["expires"]) for r in w["approvals"]._records.values()])
            print("Bridge command timing:", [json.loads(r.review)["reviewExpiresAt"] for r in w["authority"]._commands.values()])
            raise
        assert review["expiresAt"] > time.time()
        assert review["expiresAt"] <= review["review"]["reviewExpiresAt"]
        return w["approvals"].decide(*w["actor"], dict(reviewId=review["reviewId"], decision=decision, confirm=True))
    pump(lambda state, native: phone.connect())
    chat = secrets.token_hex(16)
    phone.send(chat, "Hello")
    pump(lambda *_: reply(chat) is not None)
    assert reply(chat) == "Ordinary chat reply"
    rid = secrets.token_hex(16)
    phone.send(rid, "Append Ada to standard.txt")
    state, _ = pump(lambda s, _: s["state"] == "awaiting_master_file_approval")
    assert files["standard"].read_text() == "Initial\n" and reply(rid) is None
    grant = decide(state["requestId"], "license")["result"]
    immutable = json.dumps(grant, sort_keys=True)
    state, _ = pump(lambda s, _: s["state"] == "awaiting_master_approval")
    assert files["standard"].read_text() == "Initial\n"
    decide(state["requestId"], "command")
    _, native = pump(lambda *_: reply(rid) is not None)
    assert native["listenerRunning"] and native["listenerStatus"].startswith("File saved and verified.")
    assert reply(rid) == SAVED and files["standard"].read_text() == "Initial\nAda\n"
    calls = w["planner"].calls
    phone.send(rid, "Append Ada to standard.txt")
    for _ in range(2):
        pump(lambda *_: True)
    assert w["planner"].calls == calls and files["standard"].read_text().count("Ada") == 1
    for marker, decision in (("Grace", "allow"), ("Denied", "deny")):
        pending = secrets.token_hex(16)
        phone.send(pending, f"Append {marker} to elevated.txt")
        state, _ = pump(lambda s, _: s["state"] == "awaiting_master_approval")
        decide(state["requestId"], "command")
        _, native = pump(lambda _, n: n["protectedRequest"].get("state") == "pending")
        assert marker not in files["elevated"].read_text() and reply(pending) is None
        decide(native["protectedRequest"]["requestId"], "protected", decision)
        pump(lambda *_: reply(pending) is not None)
        assert reply(pending) == (SAVED if decision == "allow" else STOPPED)
        assert (marker in files["elevated"].read_text()) == (decision == "allow")
    assert json.dumps(grant, sort_keys=True) == immutable
    unselected = secrets.token_hex(16)
    phone.send(unselected, "Append Outside to unselected.txt")
    state, _ = pump(lambda s, _: s["state"] == "awaiting_master_approval")
    decide(state["requestId"], "command")
    pump(lambda *_: reply(unselected) is not None)
    assert reply(unselected) == CLARIFY
    assert not (w["root"] / "unselected.txt").exists()
    assert all("Outside" not in path.read_text() for path in files.values())
    denied = secrets.token_hex(16)
    phone.send(denied, "Append Refused to standard.txt")
    state, _ = pump(lambda s, _: s["state"] == "awaiting_master_approval")
    decide(state["requestId"], "command", "deny")
    pump(lambda *_: reply(denied) is not None)
    assert "denied" in reply(denied).lower() and "Refused" not in files["standard"].read_text()
    revoked = secrets.token_hex(16)
    phone.send(revoked, "Append Revoked to standard.txt")
    state, _ = pump(lambda s, _: s["state"] == "awaiting_master_approval")
    decide(state["requestId"], "command")
    w["links"].revoke(*w["actor"], {"linkId": w["phone_link"]["linkId"]})
    pump(lambda *_: reply(revoked) is not None)
    assert reply(revoked) != SAVED and "Revoked" not in files["standard"].read_text()
    # Real plaintext must not appear in relay or encrypted endpoint stores.
    for name in ("relay.db", "source.db", "phone.db", "remote.db", "transport.db"):
        assert b"Append Ada to standard.txt" not in (w["root"] / name).read_bytes()
