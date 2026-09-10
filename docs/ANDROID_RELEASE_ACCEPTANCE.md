# Android Release Acceptance Evidence

## Boundary

`diagnostic` checks are not publication approval. Android device inventory emitted
by `android_release_device_proof.py` retains its v1 schema and is diagnostic only.
It does not execute messaging tests or assert that encryption/recovery works.

`publish`, `latest-debug`, and `ready_to_publish` require the
`android-physical-https-v2` policy. Unknown modes fail, rather than falling back to
diagnostic. Both device proofs must validate; missing proofs may be skipped only
in diagnostic mode. A supplied invalid proof fails even a diagnostic invocation.
Summary counts distinguish passed, skipped, warnings, and required failures.

The normal APK signer is verified with apksigner and its package/version read with
aapt for publication; caller-provided metadata cannot substitute for those reads.
Supply the expected signer independently of the candidate. SDK tooling must be
available through PATH, ANDROID_HOME or ANDROID_SDK_ROOT. There is no tool-missing
pass. Pin the tested backend with `--android-release-backend-revision <full SHA>`.

## V2 Physical Proof

Each proof is a bounded UTF-8 JSON object with schema
`aibenchie.android-release-device-proof.v2`. Required fields:

- `generated_at`: timezone-qualified completion time, within 24 hours; more than
  60 seconds in the future is rejected. Do not refresh a timestamp without rerunning
  acceptance. No device clock override substitutes for the operator's clock.
- `app_id`, `package_name`, `app_version`, `version_code` (string), `apk_sha256`,
  `signing_fingerprint_sha256` (uppercase colon-separated), `base_url`, and
  `backend_revision`: exact matches to the candidate passed to the gate. The URL
  must be HTTPS without credentials, query, fragment or ambiguous path components.
- `serial_hash`: SHA-256 of the device's stable hardware identifier, not its
  changing wireless-debugging IP/port. Never put the raw identifier in public
  evidence. The two proofs must represent different physical phones.
- `model`: observed device model, not a filename or operator alias. Two A17 phones
  can qualify two-device behavior; they do not establish older-OS coverage.
- `physical: true`, `adb_forwarding: false`, `transport: "normal-app-https"`,
  `install_state: "installed"`, and `verdict: "pass"` after actual acceptance.
- `checks`: exactly the app-specific names in
  `aibenchie/android_release_evidence.py::REQUIRED_CHECKS`. Each entry contains
  `status: "pass"` and a nonempty `evidence` list of attachment IDs. Pending,
  inconclusive, skipped or failed scenarios cannot qualify a release.
- `evidence`: attachment IDs mapped to `path` and `sha256`. Paths are relative to
  the proof directory, confined within it, and cannot traverse or follow links.
  Each referenced regular file is nonempty and at most 4 MiB. Proof JSON is at
  most 128 KiB; at most 32 attachments are accepted. Duplicate JSON keys fail.

Example check entry (not a complete or passing proof):

```json
{"phone_to_agent":{"status":"pending","evidence":[]}}
```

Store uncompleted drafts as pending. Do not relabel instrumentation/ADB-forwarded
reports as normal-app acceptance or turn the v1 device inventory into a v2 pass.
The current 323-check NullBridge physical reports retain their original limited
scope and cannot satisfy the no-ADB requirement.

## Publication Recheck

`validate_publish_verdict` rechecks the exact verdict policy/mode, age, required
checks, app/backend/signing bindings, APK digest, normalized update-note digest,
the two proof file digests, and their attachment bytes. A diagnostic receipt,
changed attachment, copied phone proof or omitted required check blocks publishing.
NullBridge's publishing status path uses this validator and fails closed if the
upgraded AIBenchie implementation is unavailable. A metadata-only file's existence
is never sufficient. Install AIBenchie and set AIBENCHIE_REPO explicitly in release
jobs; the validator is executable operator tooling, not code supplied by a proof.

Proof files and attachments are operator-owned evidence/attestations. Hash checks
detect changed referenced bytes; they are not signatures or independent proof that
the operator truthfully ran a test. They do not protect against an attacker who
can rewrite the trusted release tooling and all its inputs. Keep that trust boundary
explicit, require review of the actual results, and retain failure evidence.

Never include real messages, credentials, recovery secrets or private keys in
these files. Use synthetic accounts and markers. User-visible behavior is reported
by the tester; relay storage/log leakage, tamper, recovery, revocation and rollback
claims also require technical evidence. A model reply alone proves none of those.
