# Bridge-to-Canvas Gate

Scope: existing AUTH-10 / WIN-12 / WIN-13. This adds automated coverage, not
another checklist requirement or permission system.

## Run

Use the matching account and Bridge source candidates and the existing compiled
Windows `nullxoid_permission_probe` test target:

```powershell
python -m aibenchie.bridge_canvas --account <account-root> --bridge <bridge-root> --native-probe <probe.exe>
```

The same paths can be supplied with `AIBENCHIE_CANVAS_ACCOUNT_ROOT`,
`AIBENCHIE_CANVAS_BRIDGE_ROOT`, and `AIBENCHIE_CANVAS_NATIVE_PROBE`. The interpreter
needs the candidates' account/Bridge test dependencies, including vodozemac.
The universal suite manifest includes this command as a required integration gate.

Each invocation writes a new ignored `.suite/local/bridge-canvas/<run-id>` folder
with JUnit, a diagnostic log, result metadata and evidence hashes. Missing inputs
are **blocked**. Failed, skipped, empty or timed-out execution cannot pass. The
result records source revisions, dirty state and the native executable hash.

## What It Exercises

The AIBenchie-owned test uses disposable accounts, synthetic session/credential
records and a synthetic requester/planner. It performs actual reciprocal device
linking, native signing, HTTPS account-authority callbacks, Master review and
decisions, encrypted Olm transport, the existing Windows private-pipe listener,
native file-policy checks and real temporary-file writes.

It checks ordinary chat, deliberately unordered file selection, no write before
file/command approval, the matching encrypted saved response, duplicate request
suppression, separate elevated approval and denial, command denial, account-link
revocation, unselected targets, immutable parent licenses and plaintext absence
from relay stores. A deliberate review delay crosses a real clock tick to catch
account/Bridge deadline mismatches without extending either deadline.

The combined path now uses the explicitly configured `account-session` policy
and a disposable password-authenticated Master session. Focused policy checks
also cover the unchanged default recent-passkey requirement, unsupported methods,
revoked/expired sessions, disabled accounts, Master-role rejection, credential
revocation and the web UI's readiness decision. No real password or passkey is
used. Test-only pipe diagnostics wrap the existing production helper and are
never packaged as a product entry point.

This specifically joins the account and native paths previously tested separately.
Existing component evidence for expiry, file/folder replacement and crash recovery
remains component evidence; do not infer those outcomes from this test.

The gate never reads a desktop password, touches the user's Canvas test files,
changes deployed roles, starts a production service, or operates a real phone.
`physicalAcceptance` remains false even when this integration gate passes. The
original A17/browser/Canvas workflow still needs its own recorded live outcome.

## Internal Canvas Experiment

The opt-in `tests/integration/test_bridge_canvas_document_viability.py` reuses
this fixture and compiled native driver to compare an unconnected internal
Canvas draft with a test-only saved-file/document adapter. It is not a new
mandatory release requirement or a production feature. With the same prerequisite
environment configured, run this individual pytest file for the experiment;
do not repeat the full gate just to reproduce it. See
`../reports/2026-09-18-canvas-document-viability.md` for the result and limitations.

## Runtime Boundary

Delayed-setup coverage reuses the existing encrypted-channel and dispatcher
drivers. It checks same-key renewal of an expired, unused handshake, rejection
of key replacement or established-transcript replacement, revoked identity,
chat while Windows is unavailable, approval before file transport, and
reconnect without a duplicate append. These checks run only in AIBenchie.

New test scenarios, failure injection and release checks belong in AIBenchie.
Existing product test drivers can be reused; they are not app entry points.
Normal chat must not launch this gate or a benchmark. Runtime checks remain only
where they enforce actual operation correctness or security: identity, ownership,
signed scope, expiry/revocation, protected-file consent, file-object identity and
verified receipts. Test configuration must never bypass those checks in production.
