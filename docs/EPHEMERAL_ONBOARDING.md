# Ephemeral Onboarding

AIBenchie should be safe for other people to download. Personal Forgejo hosts, tokens, runner names, signing labels, and internal URLs must not ship in the public repo.

## Public Defaults

Tracked files may include placeholders only:

```text
forgejo.example.invalid
YOUR_ORG
YOUR_REPO
release_hardware_key
```

## Local Add-ons

Real local configuration belongs in ignored files:

```text
.suite/local/
.suite/addons/local/
```

Use `.suite/addons/forgejo.local.example.json` as a template, then store the real version under `.suite/local/` or `.suite/addons/local/`.

## Secret Input

Tests and onboarding may request secrets at runtime, but must not persist them.

Allowed:

```text
environment variable for current process
interactive prompt with hidden input
OS keychain where explicitly supported
short-lived in-memory session
```

Forbidden:

```text
committed files
test snapshots
reports
logs
query strings
localStorage
plain diagnostic dumps
```

## AIBenchie Gate

AIBenchie must block release if tracked files contain personal hosts, private IP defaults, user paths, service credentials, or organization-specific secrets.

## Streamlit Cloud

The public Streamlit app should use:

```text
Repository: https://github.com/NullXoid/AIBenchie
Branch: main
Main file path: streamlit_app.py
```

Do not place personal Forgejo tokens or NullBridge service credentials in Streamlit secrets for the public app. If a private deployment needs them, use a separate private app and keep the values session-scoped or in that private deployment's secret store.

The public Streamlit app can test Ollama only when it is running on the same machine as Ollama:

```text
streamlit run streamlit_app.py
```

Streamlit Cloud cannot directly reach Ollama on a user's PC. Browser-to-local model testing should later go through a local backend or NullBridge adapter with explicit user approval, not through saved public app secrets.

For command-line local smoke checks, use the public-safe local runner:

```text
python aibenchie_local.py --list-models
python aibenchie_local.py --model gemma3:1b --json
```

The local runner only accepts localhost Ollama URLs. Personal Forgejo URLs, NullBridge service credentials, and private backend settings still belong in ignored local add-ons or one-session inputs.

## Hosted NullXoid Auth Gate

The hosted NullXoid login check is a manual AIBenchie gate. Configure these as
private Forgejo secrets or one-session environment variables:

```text
AIBENCHIE_NULLXOID_ORIGIN
AIBENCHIE_NULLXOID_BASE_PATH
AIBENCHIE_NULLXOID_USERNAME
AIBENCHIE_NULLXOID_PASSWORD
```

Then run:

```text
python aibenchie_local.py --hosted-nullxoid-auth --json
```

The check verifies anonymous auth state, login response, auth cookies, and
post-login `/auth/me`. It does not print or persist the password or cookie
values.
