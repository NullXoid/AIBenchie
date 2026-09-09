# Retained Product Evidence for E2EE Readiness

The readiness gate still runs its local crypto/lifecycle simulations, but labels
them as simulations. They are NOT proof of installed-client behavior. Legacy
source-reference manifests remain readable and are retained for traceability;
they cannot make the release gate pass without product results.

## Inputs and Trust

The release job must supply a trusted policy, build inventory, receipt references
and artifact directory. Paths are relative to the configured audit root; external
paths, traversal and escaping symlinks are rejected. No network fetching occurs.
Artifact files are hashed in bounded chunks. Result JSON is limited to 256 KiB.

Hash matching detects altered/mismatched files; it does not authenticate a runner
or stop someone who controls all inputs from fabricating a report. The release
operator must pin/control policy and artifact provenance. This gate is not an
independent cryptographic audit or a substitute for signed CI attestations.

Policy must explicitly enumerate every required component/platform for every
storage target AND `device_lifecycle`, for example:

```json
{
  "e2ee_storage_targets": ["saved_chats"],
  "e2ee_required_products": {
    "saved_chats": ["nullxoid:android", "nullxoid:web"],
    "device_lifecycle": ["nullxoid:android", "nullxoid:web"]
  }
}
```

This example is not the whole suite matrix. Do not omit a platform and then claim
the entire suite passed. The current checked-in legacy manifest has no qualifying
product receipt set and intentionally fails readiness. No new product security
claim is made by the unit fixtures testing this validator.

Each manifest build is keyed by the exact `component:platform` ID and contains:

```json
{
  "builds": {
    "nullxoid:android": {
      "artifact": "artifacts/client.apk",
      "sha256": "<64 lowercase hexadecimal characters>",
      "source_revision": "<40 or 64 lowercase hexadecimal characters>"
    }
  }
}
```

Each target and `device_lifecycle` entry retains its existing descriptive fields
and adds `receipts: [{"path": "results/android-chats.json", "sha256": "..."}]`.
Every referenced receipt must be valid. Every required product needs exactly one
passing receipt per target. An absent or additional duplicate receipt fails.

Receipt format:

```json
{
  "schema": "librestead.e2ee-product-result.v1",
  "target": "saved_chats",
  "product": "nullxoid:android",
  "execution": "product_integration",
  "ok": true,
  "source_revision": "<matches build inventory>",
  "artifact_sha256": "<matches actual artifact and inventory>",
  "executed_at": "<timezone-aware ISO timestamp>",
  "checks": {
    "roundtrip": true,
    "wrong_key_rejected": true,
    "tamper_rejected": true,
    "plaintext_absent_at_rest": true,
    "key_not_persisted_in_repo": true
  }
}
```

`device_lifecycle` receipts use every `REQUIRED_DEVICE_LIFECYCLE_CHECKS` entry.
Checks must be JSON boolean true, not `1`, `passed`, skipped or inconclusive.
Receipts must be at most seven days old and no more than five minutes ahead of
the validator clock. Source links alone, local simulations, stale or future
results, wrong build/target/product, changed bytes and missing files fail closed.
Errors never echo raw receipt contents.

Phone-to-agent and agent-to-agent transport, sender identity, replay/downgrade
rejection and revocation require additional acceptance work; a saved-storage
receipt alone must not be used to claim those paths are encrypted.
