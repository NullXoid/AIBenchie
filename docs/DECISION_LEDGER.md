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
