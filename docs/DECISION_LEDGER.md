# AIBenchie Decision Ledger

Durable engineering decisions live here when they affect release trust, deploy contracts, suite gates, or cross-repo responsibilities. Runtime reports and generated `reports/runtime` notes are evidence, not the long-term decision ledger.

## 2026-04-27: Release Packager Remains Separate From Release Verifier

- Status: accepted
- Decision: keep release packaging and release verification as separate commands and modules.
- Context: AIBenchie now creates wrapper, NullXoid Companion/Android, and public-site release packages with digest, SBOM, signature, and package-manifest evidence. The suite verifier consumes that evidence and decides whether the release is attestable.
- Alternatives considered:
  - Put packaging inside the verifier.
  - Keep only a verifier and require operators to package artifacts manually.
  - Add a higher-level orchestration command while preserving separate packager and verifier internals.
- Rationale: packaging is side-effectful and environment-dependent; verification must stay deterministic and read-only. Keeping the boundary clean prevents a verifier run from creating or mutating release evidence, which would weaken the trust story.
- Consequences: release automation must run packaging before verification. Verifier failures mean the package evidence is missing, stale, incomplete, or invalid; they should not trigger implicit repackaging.
- Revisit trigger: revisit only if AIBenchie adds a release orchestration command. That command may call both the packager and verifier, but the verifier itself should remain read-only.
- Related commits: `56339bb`, `d78a165`, `8cfaa1c`, `6a23391`.
- Related files: `aibenchie/release_bundle.py`, `aibenchie/release_artifacts.py`, `aibenchie/suite_security.py`, `docs/RELEASE_DETAILS.md`.
- Validation commands:
  - `python -m pytest tests/test_release_bundle.py tests/test_release_artifacts.py tests/test_suite_security.py -q`
  - `python aibenchie_local.py --package-release-artifacts --wrapper-package <wrapper-dist> --android-package <apk-or-aab> --public-package <site-dist> --release-package-output-dir <release-packages> --release-artifact-key-id release-attestation-key --json`
  - `python aibenchie_local.py --verify-release-artifacts --release-artifacts <release-packages>/release-artifacts.json --json`

## 2026-04-27: AIBenchie Deploy Add-On Is Separate From Release Verification

- Status: accepted
- Decision: keep deploy behavior in a deploy add-on gate, separate from release details and release artifact verification.
- Context: AIBenchie can produce verified package evidence first, then the deploy add-on can validate a provider-neutral release plan for a repo hub such as Forgejo, Gitea, GitHub, or another compatible provider. The saved deploy plan is verified read-only before it is surfaced in release evidence or the suite gate.
- Rationale: deploy is a separate operational concern from release proof. AIBenchie should prove what is safe to ship first; a deploy add-on can later decide where and how to publish it.
- Constraints: provider credentials, deploy tokens, tunnel keys, and signing secrets must stay in runtime/local secret storage and never be committed to the repo. The default add-on path is still the dry-run release-plan gate plus a read-only deploy-plan verifier. The provider executor is gated separately and must require private config, `dry_run: false`, a runtime token, and exact release-tag confirmation before it can create a release or upload assets.
- Revisit trigger: revisit when adding a real provider executor, release upload, changelog publication, or PR/release creation flow.
- Related files: `README.md`, `docs/RELEASE_DETAILS.md`, `aibenchie/deploy_addon.py`, `tests/test_deploy_addon.py`.
- Validation commands:
  - `python aibenchie_local.py --deploy-addon --json`
  - `python aibenchie_local.py --verify-deploy-plan --deploy-plan <deploy-plan.json> --json`
  - `python aibenchie_local.py --execute-deploy-addon --deploy-addon-config <private-config.json> --deploy-publish-confirm <release-tag> --json`
  - `python aibenchie_local.py --verify-release-artifacts --release-artifacts <release-artifacts.json> --json`

## 2026-05-10: EchoLabs Stabilization Backlog Is Complete

- Status: accepted
- Decision: treat the EchoLabs stabilization backlog as complete and require future suite work to enter as new scoped backlog rows, not by reopening completed stabilization rows.
- Context: Web, Android, Desktop, BridgeEcho/NullBridge, Universal API/UX E2E, release artifact attestation, suite-security, generated-output policy, deploy add-on dry run, deploy-plan verification, and hosted API E2E all passed in the current workspace.
- Rationale: the suite now has enough release evidence that old "next work" labels create confusion and duplicate effort. A handoff record should distinguish completed stabilization from new product/release lanes.
- Consequences: future work should start from a clean lane such as provider-backed deployment, Docker gate support, broader real-device UX coverage, or the paused standalone AIBenchie expansion.
- Revisit trigger: revisit only if a default suite release gate regresses or a completed gate is intentionally replaced.
- Related files: `docs/SUITE_PRIORITY_BACKLOG.md`, `docs/echolabs/ECHOLABS_RELEASE_GATES.md`, `docs/echolabs/STABILIZATION_HANDOFF.md`.
- Validation commands:
  - `.\scripts\echolabs_suite_release_gate.ps1`
  - `.\scripts\echolabs_hosted_api_e2e.ps1`
  - `python aibenchie_local.py --suite-security --json`

## 2026-04-27: Prioritize Narrow E2EE Before Broad Privacy Claims

- Status: accepted
- Decision: start NullPrivacy E2EE with one narrow production storage target before claiming suite-wide E2EE.
- Context: AIBenchie has local E2EE proof helpers, but saved chats, artifacts, uploads, workspace notes, CCC memory, offline cache, and private reports are not all product-encrypted yet.
- Rationale: one storage class can be proven end-to-end with wrong-key, tamper, and plaintext-absence gates. Broad claims before storage integration would create user-trust risk.
- Performance note: encryption is overhead by itself. Efficiency gains should come from safe encrypted caching, chunked sync, compression before encryption, and avoiding repeated network/disk work.
- Revisit trigger: revisit after saved-chat E2EE is production-gated and the next storage target is selected.
- Related files: `docs/SUITE_PRIORITY_BACKLOG.md`, `aibenchie/nullprivacy.py`, `tests/test_nullprivacy.py`.

## 2026-04-28: Gate Zero-Knowledge Device Lifecycle Before UI

- Status: accepted
- Decision: prove device enrollment, recovery, and revocation/key rotation as an AIBenchie gate before building the guided setup UI.
- Context: saved chats already use client/device-held encryption, but real users need manageable devices. The next zero-knowledge risk is not only encryption at rest; it is whether a second device can be enrolled, a lost device can be recovered, and a revoked device stops receiving future account-key epochs without exposing secrets to the backend.
- Alternatives considered:
  - Build the UI first and add tests later.
  - Treat device management as documentation only.
  - Put recovery secrets or raw device keys in backend-managed storage for convenience.
- Rationale: device lifecycle is security-critical. A deterministic proof gives the UI a clear contract and prevents broad zero-knowledge claims before enrollment, recovery, revocation, backend key absence, and audit redaction are proven.
- Consequences: `--e2ee-readiness` now requires zero-knowledge device lifecycle evidence. Future UI work should consume the lifecycle primitives rather than creating a separate key path.
- Revisit trigger: revisit when passkey/OIDC setup and device approval UI are ready, or if platform keychain APIs require a different envelope format.
- Related files: `aibenchie/zero_knowledge_devices.py`, `tests/test_zero_knowledge_devices.py`, `docs/E2EE_READINESS.md`, `EchoLabs/.NullXoid:frontend/src/lib/e2eeDeviceLifecycle.js`.
- Validation commands:
  - `python aibenchie_local.py --zero-knowledge-device-proof --json`
  - `python aibenchie_local.py --e2ee-readiness --json`
  - `npm run test:e2ee`

## 2026-04-28: Guided Device Setup Uses Existing Zero-Knowledge Primitives

- Status: accepted
- Decision: build the wrapper setup UI as a thin state layer over the existing device lifecycle primitives, then let AIBenchie run the wrapper frontend E2EE contract as a suite target.
- Context: the product needs an easy settings flow for initializing a browser, exporting a recovery kit, approving a Companion device, recovering, revoking, and seeing redacted audit evidence without asking normal users to use the CLI.
- Alternatives considered:
  - Build a separate UI-only key path.
  - Mark setup UI as complete based only on screenshots.
  - Store recovery secrets or raw account keys in browser storage for convenience.
- Rationale: the UI should not weaken the security boundary. Keeping the UI on top of the same tested primitives means AIBenchie can reject regressions where key material leaks, revocation fails to rotate the recovery kit, or the setup contract is removed.
- Consequences: the master suite now includes a `nullxoid_wrapper_frontend_e2ee` target. The v1 UI is local/browser scoped; live cross-device sync and platform keychain integration remain future work.
- Revisit trigger: revisit when Android/Companion enrollment uses the public API route or when passkey/OIDC device identity changes the storage/envelope design.
- Related files: `EchoLabs/.NullXoid:frontend/src/lib/e2eeDeviceSetupState.js`, `EchoLabs/.NullXoid:frontend/scripts/test-e2ee-device-setup-state.mjs`, `aibenchie/suite_test_catalog.py`, `docs/E2EE_READINESS.md`.
- Validation commands:
  - `npm run test:e2ee`
  - `python -m pytest tests/test_e2ee_readiness.py tests/test_suite_test_catalog.py -q`
  - `python aibenchie_local.py --suite-tests --suite-test-target nullxoid_wrapper_frontend_e2ee --suite-test-require-all --json`
