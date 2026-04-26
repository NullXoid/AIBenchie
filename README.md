# AIBenchie

AIBenchie is the NullXoid suite release-verdict and regression system.

It benchmarks model behavior, validates platform health, checks security and privacy gates, and produces release evidence before any suite artifact is trusted.

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
$env:AIBENCHIE_NULLXOID_HOST_HEADER="www.echolabs.diy"
$env:AIBENCHIE_NULLXOID_BASE_PATH="/nullxoid"
python aibenchie_local.py --hosted-nullxoid-stack --json
```

This check catches public-site fallback pages, blocked wrapper manifests, dead backend health routes, root API routes blocked by edge security, missing model inventory on open routes, and API endpoints that return HTML instead of JSON. Auth-required JSON responses are treated as healthy plumbing for unauthenticated route checks; credentialed browser/chat checks should run as a separate gate with secrets supplied only at runtime.

Run the credentialed chat stream gate only when you can provide credentials at runtime:

```powershell
$env:AIBENCHIE_NULLXOID_ORIGIN="https://www.echolabs.diy"
$env:AIBENCHIE_NULLXOID_BASE_PATH="/nullxoid"
$env:AIBENCHIE_NULLXOID_USERNAME="<runtime username>"
$env:AIBENCHIE_NULLXOID_PASSWORD="<runtime password>"
$env:AIBENCHIE_NULLXOID_MODEL="<optional model id>"
python aibenchie_local.py --hosted-nullxoid-chat --json
```

This check logs in, reads the authenticated user/workspace/project/model contract, and verifies `/chat/stream` returns a real response instead of HTML, a Cloudflare challenge, or an HTTP 500. Credentials are read from environment variables and are not written to reports.

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

## Release Verdict Rule

A release should not ship only because it builds. It needs source, test evidence, manifest, artifact digests, SBOM, AIBenchie verdict, and the required signature policy for that channel.
