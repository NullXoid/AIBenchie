# Release Details Policy

AIBenchie release details are the human-readable companion to the suite verdict. They must explain what changed, which repos and commits were used, which gates passed, what artifacts were produced, and what remains risky.

## Required Fields

Every release detail entry should include:

- release id or version
- release date in UTC
- release type: public, private, internal, retroactive, or reconstructed
- source repos, branches, and commit hashes
- scope summary
- AIBenchie suite verdict path and result
- required gates and pass/fail status
- artifacts, manifest path, digests, SBOM references, and signature references when available
- release package attestation status: `fully_attestable`, `incomplete`, or `not_recorded`
- security, privacy, NullBridge, resource, and deploy notes
- known risks and blocked items
- rollback instructions
- operator or reviewer

## Retroactive Entries

Retroactive release details are allowed. They must be labeled `retroactive: true` or `release_type: reconstructed`, and they must separate evidence from memory.

Use:

- `evidence`: commands, logs, commit hashes, signed summaries, generated reports, deploy output, or screenshots that still exist
- `unknowns`: details that cannot be proven after the fact
- `confidence`: high, medium, or low

Do not invent digests, test results, SBOMs, signatures, manifests, or dates. If a gate was not run at the time, record it as `not_run` and, if useful, add a later validation as `post_release_validation`.

## Artifact Attestation

Release packages are fully attestable only when every artifact records:

- artifact digest value
- SBOM path and SHA-256 digest
- verifiable HMAC-SHA256 signature evidence, signature algorithm, and signing key id
- release manifest path and SHA-256 digest

If any field is missing, AIBenchie must keep the release details usable but mark the package as `incomplete`. Retroactive entries can stay useful as historical evidence, but they must not be upgraded to `fully_attestable` unless the missing digest, SBOM, signature, and manifest evidence exists and the signature verifies.

When generating release details from the CLI, provide package evidence with `--release-artifacts path/to/release-artifacts.json`. The file may be a JSON array or an object with an `artifacts` array. Generated AIBenchie summary files remain release evidence, but the release package attestation status is controlled by the artifact evidence supplied for the package being shipped.

Use AIBenchie to create and verify that package evidence:

```powershell
$env:AIBENCHIE_RELEASE_ATTESTATION_SECRET="<release-attestation-secret-from-runner>"
python aibenchie_local.py --package-release-artifacts `
  --wrapper-package path/to/nullxoid-wrapper/frontend/dist `
  --android-package path/to/nullxoid-companion.apk `
  --public-package path/to/echolabs-site/dist `
  --release-package-output-dir path/to/release-packages `
  --release-artifact-key-id release-attestation-key `
  --json

python aibenchie_local.py --emit-release-artifacts `
  --wrapper-package path/to/nullxoid-wrapper.zip `
  --android-package path/to/nullxoid-companion.apk `
  --public-package path/to/echolabs-site.zip `
  --release-artifacts-output path/to/release-artifacts.json `
  --release-artifact-key-id release-attestation-key `
  --json

python aibenchie_local.py --verify-release-artifacts --release-artifacts path/to/release-artifacts.json --json
```

`--package-release-artifacts` is the preferred current flow for real builds. It packages the wrapper build, Android/Companion artifact, and public website build into stable release packages before attestation. That is what makes the public website part of the same release contract as the wrapper and mobile app instead of a separate unverified deploy.

The packager and verifier are intentionally separate. Packaging creates release evidence; verification stays read-only and proves that evidence. The decision record is in [DECISION_LEDGER.md](DECISION_LEDGER.md).

The suite security gate treats release artifact evidence as release-blocking. Set `AIBENCHIE_RELEASE_ARTIFACTS_MANIFEST` to the manifest path when the manifest is not at the AIBenchie repo root. The gate fails if wrapper, Android/Companion, or public package evidence is missing, if artifact/SBOM/signature/manifest hashes do not match files on disk, if the signature lacks an algorithm or signing key id, or if the HMAC-SHA256 signature cannot be verified with `AIBENCHIE_RELEASE_ATTESTATION_SECRET`.

## Why Suite Verdict Includes NullBridge

NullBridge owns service identity, route policy, deny-by-default routing, and audit behavior. AIBenchie owns the release decision. Putting NullBridge trust and notification proofs into the AIBenchie verdict makes these controls release-blocking instead of optional.

This catches cross-repo regressions before publish, proves implementation and policy together, and gives every release a repeatable evidence trail.

## Deploy Add-On

AIBenchie has a provider-neutral deploy add-on foundation for repo hubs such as Forgejo, Gitea, GitHub, or another provider. The current contract is a dry-run deploy plan gate plus a read-only deploy-plan verifier. It supports open and closed source repo targets, keeps credentials in runtime/local secret storage, and refuses to emit a plan unless the suite verdict and release artifact attestation pass.

The deploy add-on is deliberately separate from release details. Release details prove what was built and verified. The deploy add-on can use that proof to prepare a sanitized deploy plan for the selected repo hub. A future provider executor must be added as its own explicit, gated capability before any assets are uploaded or releases are published.

When a runner sets `AIBENCHIE_DEPLOY_PLAN` or `AIBENCHIE_DEPLOY_ADDON_PLAN`, the release summary includes only a public-safe deploy proof summary: pass/fail, dry-run state, provider type, release tag, check counts, and asset count. Raw provider configuration and token environment names stay out of public release evidence.

## Real-Device UX Proof

Real-device UX proof is optional release evidence for physical device runs. Keep the actual proof JSON under an ignored runtime path such as `.suite/local/aibenchie/android-real-device-ux.json`.

When a runner sets `AIBENCHIE_REAL_DEVICE_UX_PROOF` or `AIBENCHIE_ANDROID_REAL_DEVICE_UX_PROOF`, the release summary includes only a public-safe proof summary: pass/fail, platform, proof id, workflow count, check count, and failed-check count. Raw device identifiers, session material, screenshots, local paths, and detailed workflow notes stay out of public release evidence.
