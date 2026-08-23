# NullPrivacy E2EE Readiness Gate

AIBenchie treats E2EE as complete only when the readiness gate passes. The local crypto proof is necessary, but it is not enough by itself. Product storage targets must also publish evidence that they encrypt data at rest, reject wrong keys and tampering, avoid plaintext persistence, and keep key material out of the repo.

When this gate is green, dashboards and release notes should display it as complete for the current readiness boundary, not as "work in progress". The stricter zero-knowledge track now has a device lifecycle proof: user/device-held keys for supported private payloads, device-to-device enrollment, recovery with a user-held secret, revocation with key rotation, and redacted audit evidence.

Run the gate:

```powershell
python aibenchie_local.py --e2ee-readiness --json
```

Run the focused device lifecycle proof:

```powershell
python aibenchie_local.py --zero-knowledge-device-proof --json
```

To make the broader suite security gate release-blocking for E2EE, set:

```powershell
$env:AIBENCHIE_SUITE_SECURITY_E2EE="1"
python aibenchie_local.py --suite-security --json
```

## Required Targets

The gate reads `.suite/policies/privacy-levels.json` and expects evidence for every `e2ee_storage_targets` entry:

- `saved_chats`
- `private_artifacts`
- `ccc_memory`
- `workspace_notes`
- `private_uploads`
- `offline_cache`
- `sync_blobs`
- `private_aibenchie_reports`

Override the target list only for focused development:

```powershell
$env:AIBENCHIE_E2EE_REQUIRED_TARGETS="saved_chats,private_artifacts"
```

## Evidence Manifest

Default path:

```text
.suite/evidence/e2ee-readiness.json
```

Override path:

```powershell
$env:AIBENCHIE_E2EE_EVIDENCE="path\to\e2ee-readiness.json"
```

Schema shape:

```json
{
  "version": 1,
  "status": "complete",
  "device_lifecycle": {
    "status": "implemented",
    "encryption_boundary": "device_to_device_zero_knowledge",
    "key_management": "user held recovery secret plus device enrollment envelopes that are not server readable",
    "backend_key_material": "forbidden",
    "tests": [
      "device_enrollment",
      "recovery_secret_restores_key",
      "wrong_recovery_secret_rejected",
      "revoked_device_rejected_after_rotation",
      "backend_plaintext_key_absent",
      "audit_redacted",
      "guided_setup_ui_contract"
    ],
    "evidence": [
      "Elabs/.NullXoid:frontend/src/lib/e2eeDeviceLifecycle.js",
      "Elabs/.NullXoid:frontend/src/lib/e2eeDeviceSetupState.js",
      "Elabs/.NullXoid:frontend/scripts/test-e2ee-device-lifecycle.mjs",
      "Elabs/.NullXoid:frontend/scripts/test-e2ee-device-setup-state.mjs"
    ]
  },
  "targets": [
    {
      "target": "saved_chats",
      "status": "implemented",
      "encryption_boundary": "client_or_device",
      "key_management": "non-extractable device-local WebCrypto CryptoKey in IndexedDB",
      "plaintext_storage": "forbidden",
      "tests": [
        "roundtrip",
        "wrong_key_rejected",
        "tamper_rejected",
        "plaintext_absent_at_rest",
        "key_not_persisted_in_repo"
      ],
      "evidence": [
        "tests/e2ee/saved_chats_storage_contract.json"
      ]
    }
  ]
}
```

## Done Means

AIBenchie reports E2EE complete only when:

- the local NullPrivacy envelope proof passes
- the zero-knowledge device lifecycle proof passes
- lifecycle evidence covers enrollment, recovery, wrong-secret rejection, revocation/key rotation, backend key absence, redacted audit events, and guided setup UI contracts
- every required target appears in policy and evidence
- every target is marked `implemented`, `proven`, or `complete`
- the encryption boundary is not `tls_only`, `server_only`, or backend-only
- key management is not committed, stored in repo, or based on raw localStorage/browser-storage keys
- plaintext storage is forbidden
- each target has roundtrip, wrong-key, tamper, plaintext-at-rest, and key-persistence tests
- each target points to concrete evidence

Until then, `--e2ee-readiness` must fail. That failure is intentional: it prevents broad E2EE claims before product storage integration is proven.

## Zero-Knowledge Track

Passing `--e2ee-readiness` now proves the current zero-knowledge device lifecycle boundary, but it still should not be overclaimed as full privacy completion. The boundary proves:

- per-user or per-device key material for supported private payloads
- no backend-side decryption path for zero-knowledge payload classes
- device enrollment, recovery, and revocation behavior
- recovery secrets are user held and wrong recovery secrets are rejected
- revoked devices cannot decrypt the next account-key epoch
- backend records and audit events omit plaintext key material

Remaining future work is server-synced multi-device state, platform keychain storage, and live mobile/device revocation policy. The wrapper now has a v1 guided setup surface; the next gate is proving that flow across real Companion devices.
