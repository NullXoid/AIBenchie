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

When production values are ready, copy the template into ignored deployment configuration or secret storage, replace the placeholders, then run:

```text
$env:AIBENCHIE_AUTH_PROVIDER_CONFIG="path/to/ignored-auth-provider-config.json"
python aibenchie_local.py --auth-provider-config --auth-provider-config-require-real --json
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

This is separate from `--secure-signin-setup`: that gate proves app/backend wiring and hosted route behavior. This gate proves the provider configuration shape is ready and can be enforced with real values.
