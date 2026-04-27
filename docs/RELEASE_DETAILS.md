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
- signature reference, signature algorithm, and signing key id
- release manifest path and SHA-256 digest

If any field is missing, AIBenchie must keep the release details usable but mark the package as `incomplete`. Retroactive entries can stay useful as historical evidence, but they must not be upgraded to `fully_attestable` unless the missing digest, SBOM, signature, and manifest evidence exists.

When generating release details from the CLI, provide package evidence with `--release-artifacts path/to/release-artifacts.json`. The file may be a JSON array or an object with an `artifacts` array. Generated AIBenchie summary files remain release evidence, but the release package attestation status is controlled by the artifact evidence supplied for the package being shipped.

Use AIBenchie to create and verify that package evidence:

```powershell
python aibenchie_local.py --emit-release-artifacts `
  --wrapper-package path/to/nullxoid-wrapper.zip `
  --android-package path/to/nullxoid-companion.apk `
  --public-package path/to/echolabs-site.zip `
  --release-artifacts-output path/to/release-artifacts.json `
  --release-artifact-key-id release-attestation-key `
  --json

python aibenchie_local.py --verify-release-artifacts --release-artifacts path/to/release-artifacts.json --json
```

The suite security gate treats release artifact evidence as release-blocking. Set `AIBENCHIE_RELEASE_ARTIFACTS_MANIFEST` to the manifest path when the manifest is not at the AIBenchie repo root. The gate fails if wrapper, Android/Companion, or public package evidence is missing, if artifact/SBOM/signature/manifest hashes do not match files on disk, or if the signature reference lacks an algorithm or signing key id.

## Why Suite Verdict Includes NullBridge

NullBridge owns service identity, route policy, deny-by-default routing, and audit behavior. AIBenchie owns the release decision. Putting NullBridge trust and notification proofs into the AIBenchie verdict makes these controls release-blocking instead of optional.

This catches cross-repo regressions before publish, proves implementation and policy together, and gives every release a repeatable evidence trail.
