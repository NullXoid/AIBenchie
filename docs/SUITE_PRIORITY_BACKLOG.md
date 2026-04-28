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
| Android/Companion remote profile | Done | Companion defaults and release BuildConfig point at `https://api.echolabs.diy/nullxoid`; AIBenchie verifies hosted API plumbing, Forgejo-first app update metadata, release network-security config, and endpoint tests |
| Secure sign-in setup contract | Done | AIBenchie validates passkey/OIDC-first policy, guided setup policy, Android setup UI, wrapper `/health/features` auth metadata, and hosted JSON route behavior |

## Visual Status Tracks

Public dashboards should show the completed gate as green instead of "work in progress". Remaining privacy hardening gets its own separate visual track.

| Track | Visual label | Meaning | Next display rule |
| --- | --- | --- | --- |
| E2EE readiness | GREEN / PASS | AIBenchie has proof/evidence for the current E2EE readiness boundary. | Show as complete when `--e2ee-readiness` passes. |
| Zero-knowledge device lifecycle | GREEN / GATED | Enrollment, recovery, and revocation/key-rotation proof exists for the current zero-knowledge boundary. | Show as complete when `--zero-knowledge-device-proof` and `--e2ee-readiness` pass. |
| Zero-knowledge setup UI | GREEN / V1 GATED | Guided browser UI exists for approving devices, exporting recovery kits, recovery unlock, revocation, and redacted audit evidence. | Show as complete for v1 when wrapper `npm run test:e2ee` and AIBenchie suite tests pass. |
| Android/Companion remote profile | GREEN / GATED | Mobile/off-network profile uses the public HTTPS API route and passes AIBenchie remote backend checks. | Show as complete when `--companion-remote-backend` and Android unit tests pass. |
| Secure sign-in setup | GREEN / CONTRACT GATED | Setup is UI-first, passkey/OIDC-first, password fallback is migration/development only, and backend auth capabilities are advertised as JSON. | Show as complete when `--secure-signin-setup` and master suite tests pass. |
| Resource bloat guardrails | YELLOW / PARTIAL | Budgets and generated-output policy exist, but runtime lease enforcement is not complete. | Show as partial until leases and cleanup jobs are enforced. |
| NullBridge trust fabric | GREEN / PASS | Signed service identity, deny-by-default routing, redacted audit, notification policy, and AIBenchie gates pass. | Show as complete while the master suite remains green. |

## Ranked Next Work

| Rank | Item | Score | Status | Completion target |
| --- | --- | ---: | --- | --- |
| 1 | Native passkey/OIDC ceremony implementation | 455 | Planned | Implement actual platform passkey and OIDC PKCE credential flows behind the setup contract. |
| 2 | NullBridge trust fabric hardening | 440 | Partial | Signed backend identity, deny-by-default service routing, redacted audits, and AIBenchie end-to-end denial/proof gates are release-blocking. |
| 3 | Resource Manager v1 runtime enforcement | 420 | Partial | Backend leases, cleanup jobs, retention caps, pressure alerts, and no unbounded heavy work. |
| 4 | Backend Operations UI v1 | 390 | Planned | Read-only UI shows health, deploy, AIBenchie gates, resource pressure, runtime status, and notifications without exposing secrets. |
| 5 | AIBenchie website scoreboard and release evidence display | 365 | Partial | Website shows latest valid score per class/test, overall score, release details, and progress bars from public-safe exports. |
| 6 | Notification system through NullBridge | 345 | Planned | Backend emits operational events, NullBridge applies policy, frontend shows notification center/toasts. |
| 7 | AIBenchie deploy add-on | 295 | Planned | Provider-neutral deploy flow for Forgejo/Gitea/GitHub-style hubs, gated by suite verdict and release attestation. |
| 8 | Docker support documentation | 210 | Planned | Website/docs mark Docker as coming soon, with constraints and no false support claim. |

## Encryption and Performance Notes

Encryption usually adds CPU overhead. It can still improve whole-system efficiency when it enables safer caching, smaller syncs, and less repeated work:

- Compress before encryption for eligible plaintext blobs, never after encryption.
- Chunk large artifacts so only changed chunks sync.
- Cache encrypted local blobs so mobile/off-network clients do not re-fetch everything.
- Keep metadata minimal so indexes stay small.
- Use platform crypto primitives where possible instead of custom production crypto.
- Do not claim encryption makes raw inference faster. The performance benefit should be framed as safer storage, bounded sync, and less repeated network or disk work.

## Immediate Next Recommendation

Next highest-value item is native passkey/OIDC ceremony implementation. The setup contract is now gated, so the next gap is connecting that UI-first setup to real platform credential ceremonies without moving tokens into frontend-accessible storage.

Acceptance:

- Android uses Credential Manager for passkeys.
- OIDC uses Authorization Code with PKCE.
- Password fallback remains migration/development and MFA-gated where enabled.
- Mobile session tokens stay in Android Keystore or equivalent platform storage.
- AIBenchie proves the native ceremony cannot leak tokens through URLs, logs, frontend storage, or NullBridge service credentials.
