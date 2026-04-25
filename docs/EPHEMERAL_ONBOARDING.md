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
