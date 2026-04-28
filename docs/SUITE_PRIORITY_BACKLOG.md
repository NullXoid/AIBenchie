# Suite Priority Backlog

This backlog ranks cross-repo work by release impact, risk reduction, user value, dependency unblock, and implementation size. Scores are directional, not promises. Re-score after each major merge or deploy.

## Scoring

- Impact: 1-5, how much the item moves the suite forward.
- Risk reduction: 1-5, how much failure/security/privacy risk it removes.
- User value: 1-5, how visible/useful it is to users.
- Dependency unblock: 1-5, how much future work depends on it.
- Effort fit: 1-5, higher means easier to finish soon.
- Priority score: `(impact * 25) + (risk_reduction * 25) + (user_value * 20) + (dependency_unblock * 20) + (effort_fit * 10)`.

## Current Completed Baseline

| Item | Status | Evidence |
| --- | --- | --- |
| CT400 repo-backed wrapper deploy | Done | systemd timer, deploy script, AIBenchie hosted gates |
| Hosted wrapper E2E gates | Done | stack gate, ephemeral chat gate, resource budget gate |
| Release package attestation | Done | package manifest, digest, SBOM, signature, manifest hash checks |
| Release packager/verifier boundary | Done | `docs/DECISION_LEDGER.md` |
| Resource bloat guardrails | Partial | resource budget gate and generated-output policy |
| NullPrivacy E2EE readiness gate | Done | local proof plus evidence for saved chats, private artifacts, CCC memory, workspace notes, private uploads, offline cache, sync blobs, and private AIBenchie reports |
| Zero-knowledge device lifecycle proof | Done | AIBenchie proof plus wrapper frontend helper for device enrollment, recovery-secret restore, wrong-secret rejection, revocation/key rotation, backend key absence, and redacted audit |
| Zero-knowledge setup UI v1 | Done | Wrapper Privacy/Security panel can initialize a device, show a recovery kit, approve a Companion device, recover, revoke, rotate the recovery kit, and expose redacted audit evidence |

## Visual Status Tracks

Public dashboards should show the completed gate as green instead of "work in progress". Remaining privacy hardening gets its own separate visual track.

| Track | Visual label | Meaning | Next display rule |
| --- | --- | --- | --- |
| E2EE readiness | GREEN / PASS | AIBenchie has proof/evidence for the current E2EE readiness boundary. | Show as complete when `--e2ee-readiness` passes. |
| Zero-knowledge device lifecycle | GREEN / GATED | Enrollment, recovery, and revocation/key-rotation proof exists for the current zero-knowledge boundary. | Show as complete when `--zero-knowledge-device-proof` and `--e2ee-readiness` pass. |
| Zero-knowledge setup UI | GREEN / V1 GATED | Guided browser UI exists for approving devices, exporting recovery kits, recovery unlock, revocation, and redacted audit evidence. | Show as complete for v1 when wrapper `npm run test:e2ee` and AIBenchie suite tests pass. |
| Resource bloat guardrails | YELLOW / PARTIAL | Budgets and generated-output policy exist, but runtime lease enforcement is not complete. | Show as partial until leases and cleanup jobs are enforced. |
| NullBridge trust fabric | GREEN / PASS | Signed service identity, deny-by-default routing, redacted audit, notification policy, and AIBenchie gates pass. | Show as complete while the master suite remains green. |

## Ranked Next Work

| Rank | Item | Score | Status | Completion target |
| --- | --- | ---: | --- | --- |
| 1 | Android/Companion remote profile | 455 | Planned | Production profile points to the public HTTPS NullXoid API origin, signs in securely, lists models, syncs saved chats, and passes AIBenchie remote Android gate. |
| 2 | Secure sign-in setup | 450 | Planned | UI-first setup for passkey/OIDC-capable sign-in; no normal user CLI setup. |
| 3 | NullBridge trust fabric hardening | 440 | Partial | Signed backend identity, deny-by-default service routing, redacted audits, and AIBenchie end-to-end denial/proof gates are release-blocking. |
| 4 | Resource Manager v1 runtime enforcement | 420 | Partial | Backend leases, cleanup jobs, retention caps, pressure alerts, and no unbounded heavy work. |
| 5 | Backend Operations UI v1 | 390 | Planned | Read-only UI shows health, deploy, AIBenchie gates, resource pressure, runtime status, and notifications without exposing secrets. |
| 6 | AIBenchie website scoreboard and release evidence display | 365 | Partial | Website shows latest valid score per class/test, overall score, release details, and progress bars from public-safe exports. |
| 7 | Notification system through NullBridge | 345 | Planned | Backend emits operational events, NullBridge applies policy, frontend shows notification center/toasts. |
| 8 | AIBenchie deploy add-on | 295 | Planned | Provider-neutral deploy flow for Forgejo/Gitea/GitHub-style hubs, gated by suite verdict and release attestation. |
| 9 | Docker support documentation | 210 | Planned | Website/docs mark Docker as coming soon, with constraints and no false support claim. |

## Encryption and Performance Notes

Encryption usually adds CPU overhead. It can still improve whole-system efficiency when it enables safer caching, smaller syncs, and less repeated work:

- Compress before encryption for eligible plaintext blobs, never after encryption.
- Chunk large artifacts so only changed chunks sync.
- Cache encrypted local blobs so mobile/off-network clients do not re-fetch everything.
- Keep metadata minimal so indexes stay small.
- Use platform crypto primitives where possible instead of custom production crypto.
- Do not claim encryption makes raw inference faster. The performance benefit should be framed as safer storage, bounded sync, and less repeated network or disk work.

## Immediate Next Recommendation

Next highest-value item is the Android/Companion remote profile. The zero-knowledge setup UI v1 is now done for the wrapper browser surface, so the next gap is proving mobile/off-network authentication and encrypted data access against `https://api.echolabs.diy/nullxoid`.

Acceptance:

- User can approve a new device from an existing device.
- User can export or regenerate a recovery kit without exposing the recovery secret to the backend.
- User can revoke a device and trigger account-key epoch rotation.
- Backend stores only ciphertext envelopes plus minimal routing metadata.
- AIBenchie gate proves enrollment, recovery, revocation, redacted audit behavior, and the wrapper frontend setup-state contract.
- Remote inference is labeled honestly as encrypted in transit, not end-to-end private from the inference service.
