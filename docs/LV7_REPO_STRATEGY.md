# LV7 Repo Strategy

LV7 should exist as a Forgejo repo, but the core should remain private until the trust fabric and release fabric are mature.

## Recommended Split

Keep private:

```text
agent strategies
routing heuristics
evaluation prompts
model-selection scoring
tool orchestration recipes
private benchmark corpora
release decision weights
```

Publish later:

```text
LV7 SDK interfaces
adapter contracts
safe examples
policy schemas
runtime-lite components
public test harnesses
```

## Product Position

LV7 is not the public chatbot. It is the high-capability orchestration layer behind the suite. It should operate through NullBridge, Resource Manager leases, Prompt Editor safety passes, and AIBenchie release gates.

Until those controls are proven, public users should receive stable contracts and safe adapters, not the full private orchestration core.
