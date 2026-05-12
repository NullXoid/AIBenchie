# Distribution Hygiene Gate

AIBenchie includes a credential-free release gate for distribution safety:

```powershell
python aibenchie_local.py --distribution-hygiene --distribution-hygiene-root <workspace>\Lv-7
```

It scans tracked repo files by default and can also scan explicit package ZIPs:

```powershell
python aibenchie_local.py --distribution-hygiene --distribution-package release.zip
```

The gate blocks:

- private local runtime paths such as `_runtime/private/`
- raw owner audio, camera, screenshots, screen recordings, and transcripts
- `.env`, key, keystore, signing, and certificate material
- secret-like literal assignments and token-like strings
- local Windows user paths inside distribution metadata

Personal data is allowed for local owner-approved runtime use, but it must remain in ignored private runtime storage and stay out of repos, packages, public exports, and user-download test bundles.
