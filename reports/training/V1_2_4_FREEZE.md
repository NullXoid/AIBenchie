# V1.2.4 Freeze

- Generated at: `2026-04-20T21:21:16.648370+00:00`
- Base model: `Qwen/Qwen2.5-1.5B-Instruct`
- Starting adapter: `models/adapters/lv7_sft_smoke_v1_0_5/`
- Accepted DPO adapter: `models/adapters/lv7_dpo_smoke_v1_2_4/`
- Blocked DPO adapter: `models/adapters/lv7_dpo_smoke_v1_2/`
- Config path: `training/dpo_smoke_config_v1_2_4.yaml`
- Selected DPO dataset: `data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl`
- Exact suite: `11/11`
- Development holdout: `31/33`
- DPO probes: `13/14`
- Policy rationale present: `33/33`
- Mode match: `32/33`
- Ambiguous Goal checks: `4/4 clarify`
- Pytest result: `141 passed`

This freeze captures the accepted `v1.2.4` DPO smoke adapter before blind evaluation. 
`evals/holdout/paraphrase_v0` remains a development set after repeated failure-derived patches, 
and a fresh blind evidence layer is required before broader generalization claims. 
DPO here is for preference contrast, not lexical-token repair.

## Tracked Files

| path | sha256 | size_bytes | line_count |
| --- | --- | --- | --- |
| `reports/training/v1_2_4_dpo_exact_eval_results.jsonl` | `0c7f7e6a2fe86b377d84cfa59a0233c65c3c681e438d2ab18b8905c55fe7d269` | `26764` | `11` |
| `reports/training/v1_2_4_dpo_holdout_eval_results.jsonl` | `d4f878dc51bb1537b5f40e26d296bd835f5a20fcaba484b09e3f9f68fdef9180` | `81717` | `33` |
| `reports/training/v1_2_4_dpo_probe_results.jsonl` | `869ca0172af4914a0a98c0878d24de408bd616f32018896f3670dc9085183744` | `34739` | `14` |
| `reports/training/v1_2_4_ambiguous_goal_precheck.json` | `36cce9ea7a5831b9469b904226ce677d310812e6fe667d1bedfb99f04eaf101c` | `1796` | `44` |
| `reports/training/v1_2_4_ambiguous_goal_postcheck.json` | `81417556e84a1ab33d01515ca7509966c1d6203fe546d695fdb083c9626f3f44` | `1796` | `44` |
| `reports/training/V1_2_4_DPO_SMOKE_ANALYSIS.md` | `b14d5a6d496c7922ce837ea1b4ecec35954a1143b2b4451f5bf6bf90f923d345` | `3009` | `76` |
| `reports/training/DPO_READINESS_REVIEW_V1_2_4.md` | `2322c6f70fac0ed27544ffebe5c9afe78c45d9322452a7afe62c8d095610d764` | `1048` | `21` |
| `reports/training/v1_2_4_dpo_run_config.json` | `c8135fc15aca1b2c1799e3df9639409653f10818b2b82828bc9f6695289de5d3` | `518` | `16` |
| `reports/training/v1_2_4_dpo_train_log.jsonl` | `2d4daafc67f0664b6c7d970ebc2446ef5ff9331d42d3b6c10cd1f321ef070ce2` | `6269` | `13` |
| `training/dpo_smoke_config_v1_2_4.yaml` | `bc4afdfc85f1065185ebd0fc555913a9378addf50b9ac9aeb8e8051dd9311150` | `3396` | `75` |
| `data/dpo_smoke_v1_1/dpo_pairs_selected.jsonl` | `d0eca059e51c406f3697947455f0c0468426fe3ab53e03db856bfae22eb1da6b` | `77920` | `28` |

## Adapter Files

| path | sha256 | size_bytes |
| --- | --- | --- |
| `adapter_config.json` | `3aa5fbec0043eed8ce824029bd23dec1de8136d2c8608b4f4290f90b52edebed` | `1105` |
| `adapter_model.safetensors` | `2a478457cf54c44fdf38f89461451600429d8ffe1869022edb0c6a4f519137f3` | `36981856` |
| `chat_template.jinja` | `cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f` | `2507` |
| `README.md` | `01e7250ba8a130623aaa01bbcf7aa1d61cb77c25f9a8d92ff7fbff068b760802` | `5218` |
| `ref/adapter_config.json` | `3aa5fbec0043eed8ce824029bd23dec1de8136d2c8608b4f4290f90b52edebed` | `1105` |
| `ref/adapter_model.safetensors` | `50b479faffb7cef1f069d71badee944cc07b4be25d834b054aeec309a3a267fb` | `73911112` |
| `tokenizer.json` | `3fd169731d2cbde95e10bf356d66d5997fd885dd8dbb6fb4684da3f23b2585d8` | `11421892` |
| `tokenizer_config.json` | `47bfa3e7727312946b29ac10d6dd0672d63cf7815b2a160b9523872040d2e536` | `665` |
