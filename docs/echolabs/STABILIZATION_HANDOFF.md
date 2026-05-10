# EchoLabs Stabilization Handoff

Status: complete as of 2026-05-10.

This handoff records the current release posture for the EchoLabs Suite stabilization lane. It should be updated only when the suite release posture changes; new product work should get a new backlog row instead of reopening completed stabilization items.

## Completed Scope

- EchoLabs web shell release gate.
- NullXoid Android release gate.
- NullXoid Desktop release gate.
- BridgeEcho / NullBridge backend release gate.
- AIBenchie Universal API/UX E2E, including the Playwright-style browser target.
- Hosted API E2E for `https://api.echolabs.diy/nullxoid`.
- Suite security gate with hosted stack, public secret scan, generated-output policy, and release artifact attestation.
- Release artifact package verification for wrapper, Android, and public-site assets.
- Deploy add-on dry-run plan gate, read-only plan verifier, release-summary proof hook, and optional suite-gate surface.
- Passkey/OIDC provider configuration and physical Android Credential Manager proof.
- Resource Manager runtime evidence and release evidence display.

## Current Gate Commands

```powershell
.\scripts\echolabs_suite_release_gate.ps1
.\scripts\echolabs_hosted_api_e2e.ps1
```

```powershell
$env:AIBENCHIE_RELEASE_ATTESTATION_SECRET="<runtime secret>"
$env:AIBENCHIE_RELEASE_ARTIFACTS_MANIFEST="<path to release-artifacts.json>"
$env:AIBENCHIE_NULLXOID_ORIGIN="https://api.echolabs.diy"
$env:AIBENCHIE_NULLXOID_BASE_PATH="/nullxoid"
python aibenchie_local.py --suite-security --json
python aibenchie_local.py --verify-release-artifacts --release-artifacts <path to release-artifacts.json> --json
python aibenchie_local.py --deploy-addon --deploy-addon-plan-output .suite\local\aibenchie\deploy-plan.json --json
python aibenchie_local.py --verify-deploy-plan --deploy-plan .suite\local\aibenchie\deploy-plan.json --json
```

## Evidence Locations

- Suite gate: `C:\Users\kasom\projects\_validation\echolabs_suite_gate_latest.json`
- Universal E2E: `C:\Users\kasom\projects\_validation\aibenchie_universal_e2e_latest.json`
- Hosted API E2E: `C:\Users\kasom\projects\_validation\aibenchie_hosted_api_e2e_latest.json`
- Local release packages, deploy plan, and attestation: `AIBenchie\.suite\local\aibenchie\`

The `_validation` and `.suite/local` paths are runtime evidence paths and are intentionally ignored by Git.

## Next Work Policy

Do not reopen the completed stabilization list for normal product growth. Add new work as a new scored backlog row.

Good next lanes:

- Provider-backed deploy executor after the dry-run deploy add-on and read-only plan verifier.
- Docker support gate before advertising containers as supported.
- More real-device UX coverage beyond the current Android proof. The first foundation is `python aibenchie_local.py --real-device-ux-proof <ignored-proof.json> --json`, which validates public-safe physical-device UX evidence without raw identifiers or session material.
- Standalone AIBenchie expansion for arbitrary app/API E2E testing.
