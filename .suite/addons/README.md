# AIBenchie Local Add-ons

AIBenchie ships with public-safe default policies. Organization-specific settings belong in ignored local add-ons, not in the public repo.

Use this layout for private configuration:

```text
.suite/
  local/
    forgejo.local.json
    signing.local.json
    runners.local.json
```

The `.suite/local/` and `.suite/addons/local/` directories are ignored by git. Put real Forgejo URLs, private runner names, signing key labels, package registries, and internal network targets there.

Public examples should use reserved placeholders such as:

```text
forgejo.example.invalid
YOUR_ORG
YOUR_REPO
release_hardware_key
```

Do not commit:

```text
private IP addresses
real Forgejo hosts
personal usernames
local filesystem paths
service tokens
hardware-key serials
package publish credentials
NullBridge production credentials
```
