# AIBenchie

AIBenchie is the NullXoid suite release-verdict and regression system.

It benchmarks model behavior, validates platform health, checks security and privacy gates, and produces release evidence before any suite artifact is trusted.

Standard setup is guided UI first. Users should be able to choose source host, sign-in method, backend connection, privacy level, resource profile, and validation gates without dropping into a CLI. See [docs/AUTH_AND_SETUP_POLICY.md](docs/AUTH_AND_SETUP_POLICY.md).

```text
Source repo or build artifact
  -> AIBenchie gates
  -> signed verdict
  -> release manifest / report
  -> publish decision
```

## Suite Role

AIBenchie is not the chat UI, not the LV7 training repo, and not a place to store personal infrastructure settings.

Its job is to answer:

- Did this version improve or regress?
- Are every required platform and backend route healthy?
- Did NullBridge deny unsupported callers, targets, and capabilities?
- Did Prompt Editor redact restricted output?
- Did privacy, E2EE, artifact, and release-provenance checks pass?
- Is the release safe enough to ship?

## Public And Private Boundary

This repository is intended to be usable by other people.

Do not commit:

- Forgejo, GitHub, Streamlit, or provider tokens
- local server IPs, private hostnames, or personal repo URLs
- production NullBridge credentials
- private model provider keys
- personal benchmark secrets
- raw user data, private memory, or private artifacts

Private setup belongs in runtime input, environment variables, `.suite/local/`, `.suite/addons/local/`, or a private add-on that is ignored by git.

## Source Providers

AIBenchie should support user choice instead of forcing one source host.

Supported provider directions:

- GitHub
- Forgejo / Gitea
- local checkout
- future self-hosted providers through add-ons

Provider credentials must be entered at runtime or supplied by a local secret manager. Tests may require sensitive values interactively, but they must not save those values.

## Relationship To Lv-7

Lv-7 is the intelligence, training, eval, and agent-behavior layer.

AIBenchie can consume sanitized Lv-7 benchmark fixtures and release reports, but Lv-7 remains its own source of truth. Historical AIBenchie tests still reference some Lv-7-style fixture paths; those are compatibility fixtures until the remaining test data is split into a dedicated benchmark fixture package.

## Main Tracks

- model quality
- runtime performance
- platform health
- streaming stability
- guided setup
- auth posture
- NullBridge authorization enforcement
- website auth leakage checks
- Prompt Editor redaction checks
- NullPrivacy and E2EE checks
- artifact sandboxing
- CCC scoping
- resource budget checks
- Forgejo / GitHub workflow policy
- runner isolation
- release manifest validation
- SBOM and artifact digest validation
- release package attestation details
- hardware-signature and break-glass checks

## Local Use

Install dependencies:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Run the local UI:

```powershell
streamlit run streamlit_app.py
```

Run tests:

```powershell
python -m pytest
```

Default pytest runs the current deterministic gate set. Historical milestone replay tests that need frozen local
adapter/runtime artifacts are marked `archival` and skipped by default, because they can mutate tracked
`reports/runtime` evidence and fail when old model artifacts are not present. Run them only when intentionally
replaying those milestones:

```powershell
python -m pytest --run-archival
# or
$env:AIBENCHIE_RUN_ARCHIVAL_TESTS="1"
python -m pytest
```

Run AIBenchie as the master suite tester:

```powershell
python aibenchie_local.py --suite-tests --json
```

AIBenchie owns the release verdict and suite-wide test catalog. NullBridge, NullXoid Wrapper, Companion/Android, and other repos keep their repo-local contract tests, but AIBenchie is the runner that decides whether the suite passes.

Wiring the NullBridge trust and notification gates into the broader suite verdict makes signed service identity, deny-by-default routing, and redacted audit behavior release-blocking. That benefits the project because a single verdict can catch cross-repo regressions before publish, prove implementation and policy together, and preserve repeatable evidence instead of relying on manual retesting.

Run the standalone Universal E2E foundation:

```powershell
$env:AIBENCHIE_BACKEND_URL="http://127.0.0.1:8090"
python aibenchie_local.py --universal-e2e --universal-e2e-manifest configs/echolabs_universal_e2e.json --universal-e2e-lane api --json
```

Universal E2E separates API contract checks from UX workflow checks while keeping one manifest and one verdict format. See [docs/UNIVERSAL_E2E.md](docs/UNIVERSAL_E2E.md).

EchoLabs suite architecture docs and the cross-repo release gate live under [docs/echolabs](docs/echolabs):

- [Naming glossary](docs/echolabs/ECHOLABS_NAMING_GLOSSARY.md)
- [Service and pipeline map](docs/echolabs/NULLXOID_SERVICE_MAP.md)
- [Pipeline ownership](docs/echolabs/PIPELINE_OWNERSHIP.md)
- [Release gates](docs/echolabs/ECHOLABS_RELEASE_GATES.md)

Run the release-blocking NullPrivacy E2EE readiness gate:

```powershell
python aibenchie_local.py --e2ee-readiness --json
```

This gate is documented in [docs/E2EE_READINESS.md](docs/E2EE_READINESS.md). It only passes when the crypto proof, zero-knowledge device lifecycle proof, guided setup contract, and product evidence for every E2EE storage target are present. To include it in the broader suite security verdict, set `AIBENCHIE_SUITE_SECURITY_E2EE=1`.

Run the focused zero-knowledge device lifecycle proof:

```powershell
python aibenchie_local.py --zero-knowledge-device-proof --json
```

That proof covers device enrollment, recovery with a user-held secret, wrong-secret rejection, revocation with account-key rotation, backend plaintext-key absence, guided setup evidence, and redacted lifecycle audit evidence.

Configure repo locations at runtime when they are not next to this checkout:

```powershell
$env:AIBENCHIE_NULLBRIDGE_REPO="..\NullBridge"
$env:AIBENCHIE_NULLXOID_WRAPPER_REPO="..\NullXoid-live"
$env:AIBENCHIE_ANDROID_REPO="..\NullXoidAndroid"
python aibenchie_local.py --suite-tests --suite-test-require-all --json
```

Run a focused target:

```powershell
python aibenchie_local.py --suite-tests --suite-test-target nullbridge_trust_fabric --json
```

Run focused local NullBridge trust checks with generated temporary secrets:

```powershell
python aibenchie_local.py --trust-smoke --json
python aibenchie_local.py --notification-smoke --json
```

The notification smoke gate proves that only signed backends can publish operational events, frontend-originated publishes are rejected, source identity is bound to the signed service, subscribers only receive authorized user/platform events, and stored payloads/audit entries are redacted.

Optional heavier targets, such as Android unit tests, are off by default:

```powershell
python aibenchie_local.py --suite-tests --suite-test-optional --suite-test-target android_companion_unit --json
```

AIBenchie auto-detects Android Studio's bundled JBR on Windows. If Java is installed somewhere else, set it explicitly:

```powershell
$env:AIBENCHIE_JAVA_HOME="C:\path\to\jdk"
```

List local Ollama models when Ollama is running:

```powershell
python aibenchie_local.py --list-models
```

Run a local model smoke check:

```powershell
python aibenchie_local.py --model <model-name> --json
```

Run hosted NullXoid wrapper route checks without saving secrets:

```powershell
$env:AIBENCHIE_NULLXOID_ORIGIN="http://127.0.0.1"
$env:AIBENCHIE_NULLXOID_HOST_HEADER="app.example.test"
$env:AIBENCHIE_NULLXOID_BASE_PATH="/nullxoid"
python aibenchie_local.py --hosted-nullxoid-stack --json
```

This check catches public-site fallback pages, blocked wrapper manifests, dead backend health routes, operations-status routes exposed without JSON auth errors, root API routes blocked by edge security, missing model inventory on open routes, and API endpoints that return HTML instead of JSON. Auth-required JSON responses are treated as healthy plumbing for unauthenticated route checks; credentialed browser/chat checks should run as a separate gate with secrets supplied only at runtime.

Run the Companion/Android remote backend gate:

```powershell
$env:AIBENCHIE_COMPANION_ANDROID_REPO="..\NullXoidAndroid"
$env:AIBENCHIE_COMPANION_PUBLIC_API="https://api.echolabs.diy/nullxoid"
$env:AIBENCHIE_NULLXOID_ORIGIN="https://api.echolabs.diy"
$env:AIBENCHIE_NULLXOID_BASE_PATH="/nullxoid"
python aibenchie_local.py --companion-remote-backend --json
```

This check proves the NullXoid Companion/Android repo is aligned with the public HTTPS backend route used by phones outside the LAN. It verifies the hosted API preset, release-time BuildConfig override, Forgejo-first update source, release network security config, endpoint tests, SettingsStore public URL, and the hosted API route contract. No personal admin credentials are stored or required.

Run the secure sign-in setup gate:

```powershell
$env:AIBENCHIE_ANDROID_REPO="..\NullXoidAndroid"
$env:AIBENCHIE_NULLXOID_WRAPPER_REPO="..\Felnx\NullXoid\.NullXoid"
$env:AIBENCHIE_COMPANION_PUBLIC_API="https://api.echolabs.diy/nullxoid"
$env:AIBENCHIE_NULLXOID_ORIGIN="https://api.echolabs.diy"
$env:AIBENCHIE_NULLXOID_BASE_PATH="/nullxoid"
python aibenchie_local.py --secure-signin-setup --json
```

This gate proves the setup boundary for easy secure sign-in: AIBenchie validates passkey/OIDC-first policy, guided setup policy, Android's native passkey/OIDC ceremony wiring, wrapper `/health/features` auth capability metadata, hosted JSON route behavior, and absence of frontend NullBridge service credentials. It does not store user credentials and requires unconfigured passkey/OIDC providers to fail as JSON instead of falling through to HTML or privileged NullBridge routes.

When `/health/features` reports that the hosted passkey provider is configured, this gate also requires Android Digital Asset Links at `/.well-known/assetlinks.json` on the passkey RP origin. The statement must bind `com.nullxoid.android` to `delegate_permission/common.get_login_creds` with valid release signing SHA-256 fingerprints. After that passes, physical Android testing is required to prove Credential Manager enrollment on a real device.

Run the credentialed chat stream gate only when you can provide credentials at runtime:

```powershell
$env:AIBENCHIE_NULLXOID_ORIGIN="https://app.example.test"
$env:AIBENCHIE_NULLXOID_BASE_PATH="/nullxoid"
$env:AIBENCHIE_NULLXOID_USERNAME="<runtime username>"
$env:AIBENCHIE_NULLXOID_PASSWORD="<runtime password>"
$env:AIBENCHIE_NULLXOID_MODEL="<optional model id>"
python aibenchie_local.py --hosted-nullxoid-chat --json
```

This check logs in, reads the authenticated user/workspace/project/model contract, verifies authenticated operations status is JSON and does not expose service credentials or local paths, and verifies `/chat/stream` returns a real response instead of HTML, a Cloudflare challenge, or an HTTP 500. Credentials are read from environment variables and are not written to reports.

Run the deployment resource budget gate:

```powershell
python aibenchie_local.py --resource-budget --json
```

The default `ct400-wrapper` profile checks that the live backend venv stays lightweight, disposable npm/pip caches are gone, old heavy venv backups are absent, runtime logs stay bounded, and AIBenchie reports do not grow without limit. Custom deployments can provide their own runtime-only budget without committing private paths:

```powershell
$env:AIBENCHIE_RESOURCE_PROFILE="custom"
$env:AIBENCHIE_RESOURCE_BUDGETS_JSON='[{"name":"cache","pattern":"/srv/app/.cache","max_mb":100}]'
python aibenchie_local.py --resource-budget --json
```

Run the generated-output policy gate:

```powershell
python aibenchie_local.py --generated-output-policy --json
```

This keeps the repository from becoming a dumping ground for raw generated output. Committed data should be intentional benchmark fixtures, sanitized reports, signed summaries, or release evidence. Local/private runs should write to ignored paths instead:

```text
.suite/local/
.suite/addons/local/
reports/local/
reports/runtime/.local/
data/local/
data/private/
```

The gate fails when tracked report/data paths contain oversized files, oversized totals, raw logs, temp files, archives, databases, images, HTML dumps, or dirty generated-output fixtures. Tracked release evidence under `reports/runtime` and selected `dpo_train_ready` fixtures must stay clean unless the change is intentional and reviewed. Override budgets only at runtime:

```powershell
$env:AIBENCHIE_GENERATED_RUNTIME_MAX_MB="50"
$env:AIBENCHIE_GENERATED_RUNTIME_MAX_FILES="150"
$env:AIBENCHIE_GENERATED_DATA_MAX_MB="250"
$env:AIBENCHIE_GENERATED_DATA_MAX_FILES="300"
python aibenchie_local.py --generated-output-policy --json
```

Write the public scoreboard export:

```powershell
python aibenchie_local.py --public-scoreboard --json
```

The scoreboard is the website-facing view of AIBenchie evidence. It scans valid JSON reports under `reports/runtime`, keeps only the latest report for each class or test, computes an overall score, and writes a compact public-safe export to `public_export/aibenchie-scoreboard.json`. Raw `data/` fixtures and full runtime reports stay in AIBenchie; the website consumes only the reduced scoreboard.

Run the suite security E2E gate:

```powershell
$env:AIBENCHIE_NULLXOID_ORIGIN="https://api.example.test"
$env:AIBENCHIE_NULLXOID_BASE_PATH="/nullxoid"
python aibenchie_local.py --suite-security --json
```

This is AIBenchie's evidence gate for the deployed suite. It verifies that hosted NullXoid routes return the expected JSON/static contracts instead of public-site fallback HTML, Cloudflare challenge HTML, or HTTP 500s. It also scans public repo files for committed secrets and runs the generated-output policy so runtime reports, caches, and raw data do not grow into tracked bloat.

Release reports now include a release package attestation section. A package is only marked `fully_attestable` when every artifact has a digest, SBOM path and digest, verifiable HMAC-SHA256 signature evidence, signing key id, and release manifest path and digest. Otherwise the release details remain usable but are labeled `incomplete`.

Emit release package evidence before generating release details:

```powershell
$env:AIBENCHIE_RELEASE_ATTESTATION_SECRET="<release-attestation-secret-from-runner>"
python aibenchie_local.py --package-release-artifacts `
  --wrapper-package ..\NullXoid-live\frontend\dist `
  --android-package ..\NullXoidAndroid\app\build\outputs\apk\release\app-release.apk `
  --public-package ..\echolabs-site\dist `
  --release-package-output-dir .\release-packages `
  --release-artifact-key-id release-attestation-key `
  --json

python aibenchie_local.py --emit-release-artifacts `
  --wrapper-package .\dist\nullxoid-wrapper.zip `
  --android-package .\dist\nullxoid-companion.apk `
  --public-package .\dist\echolabs-site.zip `
  --release-artifacts-output .\release-artifacts.json `
  --release-artifact-key-id release-attestation-key `
  --json

python aibenchie_local.py --verify-release-artifacts --release-artifacts .\release-artifacts.json --json
```

The package command turns actual build outputs into release packages first: wrapper build output becomes `nullxoid-wrapper.zip`, NullXoid Companion/Android becomes `nullxoid-companion.apk` or `.aab`, and the public website build becomes `echolabs-public-site.zip`. The emitted `release-artifacts.json` is the release evidence contract. It records wrapper, Android/Companion, and public-site package digests plus generated SBOM, HMAC-SHA256 signature, and package-manifest sidecars. AIBenchie's suite security gate reads `AIBENCHIE_RELEASE_ARTIFACTS_MANIFEST` or `release-artifacts.json` and fails if wrapper, Android, or public package evidence is missing, any recorded hash is stale, or the signature cannot be verified with `AIBENCHIE_RELEASE_ATTESTATION_SECRET`.

To attach package evidence to a generated release report, pass an artifact manifest:

```powershell
python aibenchie_local.py --release-report --release-artifacts .\release-artifacts.json --json
```

The artifact manifest can be either a JSON array or an object with an `artifacts` array. Each artifact should include `name`, `path`, `sha256`, `sbom.path`, `sbom.sha256`, `signature.path` or `signature.value`, `signature.algorithm`, `signature.key_id`, `manifest.path`, and `manifest.sha256`.

Optional checks are enabled only with runtime environment variables:

```powershell
$env:AIBENCHIE_SUITE_SECURITY_EPHEMERAL="1"
$env:AIBENCHIE_NULLXOID_EPHEMERAL_HELPER_ORIGIN="http://127.0.0.1:8090"
$env:AIBENCHIE_SUITE_SECURITY_NULLBRIDGE="1"
python aibenchie_local.py --suite-security --json
```

The ephemeral chat gate creates a short-lived restricted test user through a loopback helper, proves hosted chat works, then removes the user. Do not use personal admin credentials for this gate. The NullBridge option runs a local generated-secret trust smoke check; it verifies NullBridge behavior, but the runtime service identity and route policy still belong to NullBridge itself.

## Release Verdict Rule

A release should not ship only because it builds. It needs source, test evidence, manifest, artifact digests, SBOM, AIBenchie verdict, and the required signature policy for that channel.

Use [docs/RELEASE_DETAILS.md](docs/RELEASE_DETAILS.md) and [templates/release-details.md](templates/release-details.md) for proper release notes. Older releases can be documented retroactively, but they must be labeled reconstructed and tied to the evidence that still exists.

Architecture decisions that affect release trust and deploy boundaries are recorded in [docs/DECISION_LEDGER.md](docs/DECISION_LEDGER.md).
Cross-repo priorities are scored in [docs/SUITE_PRIORITY_BACKLOG.md](docs/SUITE_PRIORITY_BACKLOG.md).

## Planned Deploy Add-On

A future AIBenchie deploy add-on can publish verified packages to a repo hub such as Forgejo, Gitea, GitHub, or another open/closed source provider. That add-on should consume the suite verdict and release artifact manifest before deploy, keep provider credentials in runtime/local secret storage, and support guided setup so users do not need to drop into the CLI for normal releases. It is intentionally separate from the current package attestation gate: AIBenchie proves what is safe to ship first, then a deploy add-on can decide where to publish it.
