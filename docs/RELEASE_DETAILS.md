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
- artifacts, manifest path, digests, and SBOM references when available
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

Do not invent digests, test results, SBOMs, signatures, or dates. If a gate was not run at the time, record it as `not_run` and, if useful, add a later validation as `post_release_validation`.

## Why Suite Verdict Includes NullBridge

NullBridge owns service identity, route policy, deny-by-default routing, and audit behavior. AIBenchie owns the release decision. Putting NullBridge trust and notification proofs into the AIBenchie verdict makes these controls release-blocking instead of optional.

This catches cross-repo regressions before publish, proves implementation and policy together, and gives every release a repeatable evidence trail.
