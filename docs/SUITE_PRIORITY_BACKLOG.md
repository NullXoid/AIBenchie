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
| NullPrivacy E2EE proof primitive | Partial | AIBenchie local proof tests only; production storage not complete |

## Ranked Next Work

| Rank | Item | Score | Status | Completion target |
| --- | --- | ---: | --- | --- |
| 1 | NullPrivacy E2EE v1 foundation | 490 | Planned | Saved chats or private artifacts are encrypted before backend persistence, wrong-key/tamper tests pass, and AIBenchie proves backend stores ciphertext. |
| 2 | Android/Companion remote profile | 455 | Planned | Production profile points to the public HTTPS NullXoid API origin, signs in securely, lists models, syncs saved chats, and passes AIBenchie remote Android gate. |
| 3 | Secure sign-in setup | 450 | Planned | UI-first setup for passkey/OIDC-capable sign-in; no normal user CLI setup. |
| 4 | NullBridge trust fabric hardening | 440 | Partial | Signed backend identity, deny-by-default service routing, redacted audits, and AIBenchie end-to-end denial/proof gates are release-blocking. |
| 5 | Resource Manager v1 runtime enforcement | 420 | Partial | Backend leases, cleanup jobs, retention caps, pressure alerts, and no unbounded heavy work. |
| 6 | Backend Operations UI v1 | 390 | Planned | Read-only UI shows health, deploy, AIBenchie gates, resource pressure, runtime status, and notifications without exposing secrets. |
| 7 | AIBenchie website scoreboard and release evidence display | 365 | Partial | Website shows latest valid score per class/test, overall score, release details, and progress bars from public-safe exports. |
| 8 | Notification system through NullBridge | 345 | Planned | Backend emits operational events, NullBridge applies policy, frontend shows notification center/toasts. |
| 9 | AIBenchie deploy add-on | 295 | Planned | Provider-neutral deploy flow for Forgejo/Gitea/GitHub-style hubs, gated by suite verdict and release attestation. |
| 10 | Docker support documentation | 210 | Planned | Website/docs mark Docker as coming soon, with constraints and no false support claim. |

## Encryption and Performance Notes

Encryption usually adds CPU overhead. It can still improve whole-system efficiency when it enables safer caching, smaller syncs, and less repeated work:

- Compress before encryption for eligible plaintext blobs, never after encryption.
- Chunk large artifacts so only changed chunks sync.
- Cache encrypted local blobs so mobile/off-network clients do not re-fetch everything.
- Keep metadata minimal so indexes stay small.
- Use platform crypto primitives where possible instead of custom production crypto.
- Do not claim encryption makes raw inference faster. The performance benefit should be framed as safer storage, bounded sync, and less repeated network or disk work.

## Immediate Next Recommendation

Start NullPrivacy E2EE v1 with one narrow storage target: saved chats. A narrow target is easier to prove end-to-end than trying to encrypt every artifact class at once.

Acceptance:

- Client encrypts saved-chat payload before persistence.
- Backend stores only ciphertext envelope plus minimal routing metadata.
- Backend cannot read chat body without client-held key.
- Wrong key and tampered envelope fail.
- AIBenchie gate proves plaintext is absent from stored backend JSON.
- Remote inference is labeled honestly as encrypted in transit, not end-to-end private from the inference service.
