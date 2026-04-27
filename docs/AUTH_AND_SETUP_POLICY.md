# AIBenchie Auth And Setup Policy

AIBenchie is a release and deploy gate, not a secret store.

Standard setup must be guided by UI flows:

- choose a source provider
- choose a sign-in method
- connect a backend
- choose a privacy level
- choose a resource profile
- validate routes
- run AIBenchie gates

The normal path must not require users to open a terminal. CLI commands are acceptable for advanced troubleshooting, but they are not the default onboarding experience.

## Sign-In Model

The preferred user sign-in path is passkeys.

OIDC Authorization Code with PKCE is allowed for teams that already use an identity provider. Password fallback is migration-only and must require MFA for administrative accounts.

AIBenchie must fail a release or deploy gate if it finds:

- frontend NullBridge service credentials
- tokens in URLs
- browser-persisted auth tokens
- password-only admin access
- Android privileged direct NullBridge routes
- shared default admin credentials

## Personal Configuration

Personal settings belong in session-only inputs or ignored local add-ons. They do not belong in tracked repo files, test fixtures, reports, or command examples.

Generated support bundles must be redacted before export.

## NullBridge Boundary

AIBenchie can test NullBridge policy enforcement, but it does not replace NullBridge.

NullBridge remains the backend-side service trust fabric. Frontends authenticate to their platform backend. Platform backends authenticate to NullBridge with service identity and delegated user context.
