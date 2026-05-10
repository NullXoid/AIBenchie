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
| Secure sign-in setup contract | Done | AIBenchie validates passkey/OIDC-first policy, guided setup policy, Android setup UI, wrapper `/health/features` auth metadata, hosted JSON route behavior, and configured-provider Android Digital Asset Links |
| Passkey/OIDC provider configuration foundation | Done | Public-safe provider config template, validation gate, and real-value enforcement mode exist without committing secrets |

## Visual Status Tracks

Public dashboards should show the completed gate as green instead of "work in progress". Remaining privacy hardening gets its own separate visual track.

| Track | Visual label | Meaning | Next display rule |
| --- | --- | --- | --- |
| E2EE readiness | GREEN / PASS | AIBenchie has proof/evidence for the current E2EE readiness boundary. | Show as complete when `--e2ee-readiness` passes. |
| Zero-knowledge device lifecycle | GREEN / GATED | Enrollment, recovery, and revocation/key-rotation proof exists for the current zero-knowledge boundary. | Show as complete when `--zero-knowledge-device-proof` and `--e2ee-readiness` pass. |
| Zero-knowledge setup UI | GREEN / V1 GATED | Guided browser UI exists for approving devices, exporting recovery kits, recovery unlock, revocation, and redacted audit evidence. | Show as complete for v1 when wrapper `npm run test:e2ee` and AIBenchie suite tests pass. |
| Android/Companion remote profile | GREEN / GATED | Mobile/off-network profile uses the public HTTPS API route and passes AIBenchie remote backend checks. | Show as complete when `--companion-remote-backend` and Android unit tests pass. |
| Secure sign-in setup | GREEN / CONTRACT GATED | Setup is UI-first, passkey/OIDC-first, password fallback is migration/development only, Android has native ceremony wiring, backend auth capabilities are advertised as JSON, and configured Android passkey providers require valid Digital Asset Links. | Show as complete when `--secure-signin-setup` and master suite tests pass. |
| Passkey/OIDC provider config | BLUE / FOUNDATION READY | AIBenchie has a public-safe config contract and can enforce real passkey/OIDC values from ignored deployment config. | Show as green only after real provider values pass `--auth-provider-config --auth-provider-config-require-real` and physical Android passkey enrollment is proven. |
| Universal E2E real UX adapters | BLUE / FOUNDATION READY | Universal API/UX E2E has command targets for BridgeEcho, web, Android, and desktop. Browser/user automation is paused at the Playwright-style adapter step. | Show as in progress until a Playwright web workflow runs through `--universal-e2e-lane ux` and captures artifacts. |
| Resource bloat guardrails | YELLOW / PARTIAL | Budgets and generated-output policy exist, but runtime lease enforcement is not complete. | Show as partial until leases and cleanup jobs are enforced. |
| NullBridge trust fabric | GREEN / PASS | Signed service identity, deny-by-default routing, redacted audit, notification policy, and AIBenchie gates pass. | Show as complete while the master suite remains green. |

## Ranked Next Work

| Rank | Item | Score | Status | Completion target |
| --- | --- | ---: | --- | --- |
| 1 | Universal E2E Playwright web UX adapter | 470 | Planned / paused | Resume AIBenchie at the Playwright-style step: open EchoLabs in a browser, run a real user workflow, capture screenshot/artifact evidence, and emit it through the existing Universal E2E verdict. |
| 2 | Passkey/OIDC provider configuration | 455 | Foundation ready | Configure real WebAuthn/OIDC provider settings and publish Android Digital Asset Links for the passkey RP domain. |
| 3 | NullBridge trust fabric hardening | 440 | Hardened / gated | Signed backend identity, explicit deny-by-default service routing, redacted audits, and AIBenchie end-to-end denial/proof gates are release-blocking. |
| 4 | Resource Manager v1 runtime enforcement | 420 | Runtime leases gated | Backend lease issuance, active lease enforcement, cleanup jobs, retention caps, pressure snapshots, and no unbounded heavy work. |
| 5 | Backend Operations UI v1 | 390 | Foundation ready | EchoLabs read-only Ops panel shows health, deploy, AIBenchie gates, resource pressure, runtime status, and notifications without exposing secrets. |
| 6 | AIBenchie website scoreboard and release evidence display | 365 | Foundation ready | Website consumes public-safe scoreboard and release evidence exports, then shows latest valid score per class/test, overall score, release details, and progress bars. |
| 7 | Notification system through NullBridge | 345 | Foundation ready | NullBridge policy-gated publish/query routes and AIBenchie smoke coverage exist; EchoLabs Ops now shows a read-only notification center and toast highlight without raw service payloads. |
| 8 | AIBenchie deploy add-on | 295 | Foundation ready | Provider-neutral deploy plan gate validates Forgejo/Gitea/GitHub-style config, suite verdict, release attestation, and runtime-token boundary; EchoLabs exposes it as an admin-only add-on manifest. |
| 9 | Docker support documentation | 210 | Planned | Website/docs mark Docker as coming soon, with constraints and no false support claim. |

## Paused Automation Pickup

### Universal E2E Playwright Web UX Adapter

Status: planned / paused.

Owner: AIBenchie.

Resume trigger: pick this up when returning to standalone AIBenchie end-to-end testing after the command-target foundation.

Current foundation:

- `configs/echolabs_universal_e2e.json` runs API and UX lanes.
- `npm run aibenchie:e2e` in EchoLabs delegates to standalone AIBenchie and runs all lanes by default.
- `scripts/echolabs_suite_release_gate.ps1` runs Universal E2E and persists `_validation/aibenchie_universal_e2e_latest.json`.
- UX command targets currently cover web build/UI contracts, Android release gate, and desktop release gate.

Next implementation:

- Add a Playwright-style web adapter or command target that opens EchoLabs in a browser.
- Exercise a real user flow: load app, confirm NullXoid Chat shell, type/send a prompt through a mocked or configured backend, verify a visible assistant result, open Canvas/CCC or release dashboard, and capture evidence.
- Persist screenshots, traces, and target evidence in the Universal E2E verdict without changing `aibenchie.universal-e2e.verdict.v1`.
- Keep existing command targets as compatibility gates; the Playwright target should add coverage rather than replacing the current build/contract gate immediately.

Acceptance:

- `python aibenchie_local.py --universal-e2e --universal-e2e-manifest configs/echolabs_universal_e2e.json --universal-e2e-lane ux --json` runs the browser UX target successfully in a clean local checkout.
- Failure output identifies the browser step, selector/action, screenshot or trace path, and target id.
- `.\scripts\echolabs_suite_release_gate.ps1 -SkipWeb -SkipAndroid -SkipDesktop -SkipBridge` still writes `_validation/aibenchie_universal_e2e_latest.json`.
- Existing API/UX command targets remain green.

## Encryption and Performance Notes

Encryption usually adds CPU overhead. It can still improve whole-system efficiency when it enables safer caching, smaller syncs, and less repeated work:

- Compress before encryption for eligible plaintext blobs, never after encryption.
- Chunk large artifacts so only changed chunks sync.
- Cache encrypted local blobs so mobile/off-network clients do not re-fetch everything.
- Keep metadata minimal so indexes stay small.
- Use platform crypto primitives where possible instead of custom production crypto.
- Do not claim encryption makes raw inference faster. The performance benefit should be framed as safer storage, bounded sync, and less repeated network or disk work.

## Immediate Next Recommendation

Native passkey/OIDC ceremony wiring is now implemented and gated. The next auth gap is configuring real providers behind those endpoints without moving tokens into frontend-accessible storage.

Foundation now exists:

- `configs/echolabs_auth_provider_config.example.json` documents the public-safe provider contract.
- `python aibenchie_local.py --auth-provider-config --json` validates the tracked template.
- `python aibenchie_local.py --auth-provider-config --auth-provider-config-require-real --json` enforces non-template deployment values from `AIBENCHIE_AUTH_PROVIDER_CONFIG`.

Acceptance:

- Android uses Credential Manager for passkeys.
- Configured Android passkey providers serve `/.well-known/assetlinks.json` with `delegate_permission/common.get_login_creds` for `com.nullxoid.android` and release signing SHA-256 fingerprints.
- OIDC uses Authorization Code with PKCE.
- Unconfigured passkey/OIDC providers return JSON provider-not-configured responses.
- Password fallback remains migration/development and MFA-gated where enabled.
- Mobile session tokens stay in Android Keystore or equivalent platform storage.
- AIBenchie proves the native ceremony cannot leak tokens through URLs, logs, frontend storage, or NullBridge service credentials.
- A physical Android device proves Credential Manager passkey enrollment after provider metadata and Digital Asset Links are live.
