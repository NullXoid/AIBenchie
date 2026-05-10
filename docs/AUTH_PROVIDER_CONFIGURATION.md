# EchoLabs Auth Provider Configuration

This contract covers the real provider setup for passkeys and OIDC without storing secrets in AIBenchie.

The tracked template is:

```text
configs/echolabs_auth_provider_config.example.json
```

Run the contract gate:

```text
python aibenchie_local.py --auth-provider-config --json
```

The JSON result includes rollout fields intended for dashboards and release notes:

```text
readiness_stage:
  template_contract_ready  template is valid, but production values are still missing
  provider_values_ready    real provider values passed; physical Android proof is still missing
  production_ready         real provider values and physical Android proof passed
  blocked                  one or more required checks failed

missing_requirements:
  public-safe list of the remaining actions before production readiness

public_assetlinks_statement:
  generated public Digital Asset Links statement for the configured Android package and release fingerprints
```

When production values are ready, copy the template into ignored deployment configuration or secret storage, replace the placeholders, then run:

```text
$env:AIBENCHIE_AUTH_PROVIDER_CONFIG="path/to/ignored-auth-provider-config.json"
python aibenchie_local.py --auth-provider-config --auth-provider-config-require-real --json
```

After provider metadata and Android Digital Asset Links are live, record the physical Android Credential Manager enrollment proof in ignored local configuration:

```text
configs/echolabs_auth_provider_device_proof.example.json
```

Then run the production-ready gate:

```text
$env:AIBENCHIE_AUTH_PROVIDER_CONFIG="path/to/ignored-auth-provider-config.json"
python aibenchie_local.py --auth-provider-config --auth-provider-config-require-real --auth-provider-config-device-proof "path/to/ignored-device-proof.json" --auth-provider-config-require-device-proof --json
```

## Requirements

- Passkey RP ID and origin must be HTTPS and must match the hosted auth domain.
- Android Digital Asset Links must be published at `/.well-known/assetlinks.json`.
- The Digital Asset Links statement must bind `com.nullxoid.android` with `delegate_permission/common.get_login_creds`.
- Production passkey config must use release signing SHA-256 fingerprints.
- OIDC must use Authorization Code with PKCE.
- The Android redirect URI is `nullxoid://auth/oidc/callback`.
- Public/mobile clients must not use or expose a client secret.
- Provider values belong in deployment secret storage or ignored local add-ons, not tracked repo files.
- Physical Android proof must show Credential Manager enrollment, live provider metadata, verified Digital Asset Links, Android Keystore token storage, and clean URL/log/frontend-storage/NullBridge credential leak checks.

## Rollout Boundary

A tracked template passing `--auth-provider-config` is not production readiness. It only proves the public contract shape is valid. Production readiness requires:

1. An ignored real provider config passed with `--auth-provider-config-require-real`.
2. The generated `public_assetlinks_statement` published on the passkey RP origin.
3. A physical Android Credential Manager enrollment proof passed with `--auth-provider-config-require-device-proof`.

This is separate from `--secure-signin-setup`: that gate proves app/backend wiring and hosted route behavior. This gate proves the provider configuration shape is ready and can be enforced with real values.
