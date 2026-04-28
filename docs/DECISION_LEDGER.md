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

## 2026-04-27: AIBenchie Deploy Add-On Is Future Work

- Status: planned
- Decision: document a future deploy add-on, but do not fold deploy behavior into release details or the verifier.
- Context: AIBenchie should eventually publish verified packages to a repo hub such as Forgejo, Gitea, GitHub, or another open/closed source provider.
- Rationale: deploy is a separate operational concern from release proof. AIBenchie should prove what is safe to ship first; a deploy add-on can later decide where and how to publish it.
- Constraints: provider credentials, deploy tokens, tunnel keys, and signing secrets must stay in runtime/local secret storage and never be committed to the repo.
- Revisit trigger: start this when release packages, suite verdicts, and public release details are stable enough to drive a guided deploy workflow.
- Related files: `README.md`, `docs/RELEASE_DETAILS.md`.

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
