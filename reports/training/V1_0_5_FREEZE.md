# V1.0.5 Freeze

- Generated at: `2026-04-22T18:48:48.162232+00:00`
- Base model: `Qwen/Qwen2.5-1.5B-Instruct`
- Adapter path: `models/adapters/lv7_sft_smoke_v1_0_5/`
- Dataset dir: `data/pilot_v1_9/`
- Config path: `training/qlora_smoke_config.yaml`
- Exact suite: `11/11`
- Development holdout: `30/33`
- Policy rationale present: `33/33`
- Mode match: `32/33`
- Catastrophic safety failures: `0`
- Pytest result: `108 passed`

This freeze captures the accepted v1.0.5 SFT state before any v1.1 DPO smoke planning. 
`evals/holdout/paraphrase_v0` remains a development set after repeated failure-derived patches, 
and a future blind holdout is still required before broader generalization claims.

## Tracked Files

| path | sha256 | size_bytes | line_count |
| --- | --- | --- | --- |
| `data/pilot_v1_9/sft_messages.jsonl` | `71bffa889c7b554bf7b0bebe9e4850ddc891142641b1e8c2a677659e51f6ff75` | `720129` | `247` |
| `data/pilot_v1_9/sft_train_ready.jsonl` | `6fe0cbfcc85f73c861afcee6fc95c5cf17db3fd065d9ea657773995e6a1477ac` | `890953` | `247` |
| `data/pilot_v1_9/dpo_pairs.jsonl` | `4752aa0d32e61cc7674d00135e9331f50a203e9aef96199b3194ddf49e67668e` | `152864` | `55` |
| `reports/training/v1_0_5_exact_eval_results.jsonl` | `c75539d49dd942575fd33e94a1369a043a51a90130be622fb34af72ed1384dc9` | `27798` | `11` |
| `reports/training/v1_0_5_holdout_eval_results.jsonl` | `1bd85a535a66070a36124796c2a42b4977723a52fee5009c3a4e11e130ac843c` | `85169` | `33` |
| `training/qlora_smoke_config.yaml` | `af844eda7a59a598eeb49a1b584686a33b0326be7d2f7dd52620988b48c1b95f` | `2224` | `60` |

## Adapter Files

| path | sha256 | size_bytes |
| --- | --- | --- |
| `adapter_config.json` | `8b78760abf18a374c975bf4a91cd224c9625a986aae308b6d33d9650b92964b6` | `1105` |
| `adapter_model.safetensors` | `50b479faffb7cef1f069d71badee944cc07b4be25d834b054aeec309a3a267fb` | `73911112` |
| `chat_template.jinja` | `86179cf5cc68247f52ca23e8004076eb5051aad0b24c4d583827d1223cf9b7d5` | `4114` |
| `checkpoint-160/adapter_config.json` | `8b78760abf18a374c975bf4a91cd224c9625a986aae308b6d33d9650b92964b6` | `1105` |
| `checkpoint-160/adapter_model.safetensors` | `50b479faffb7cef1f069d71badee944cc07b4be25d834b054aeec309a3a267fb` | `73911112` |
| `checkpoint-160/README.md` | `cb3cdefbcf1962832683ba0c254e668036400b8b081eef936ed72964b2419408` | `5206` |
| `checkpoint-160/trainer_state.json` | `c18ea951559ffb69d5269c6bb597bcc2ddcd501f8d15005979c06899ce9b1e0d` | `28838` |
| `checkpoint-160/training_args.bin` | `9ec122389c82cc3d7bd116f213b7d8c9a4475f693ad4bdb8b84d3eb247c17458` | `5201` |
| `README.md` | `cb3cdefbcf1962832683ba0c254e668036400b8b081eef936ed72964b2419408` | `5206` |
| `tokenizer.json` | `2f55e63353d3d978b390d346bae531be8b83bc9532c0be500d62b7253aa4c595` | `11421991` |
| `tokenizer_config.json` | `47bfa3e7727312946b29ac10d6dd0672d63cf7815b2a160b9523872040d2e536` | `665` |
| `training_args.bin` | `9ec122389c82cc3d7bd116f213b7d8c9a4475f693ad4bdb8b84d3eb247c17458` | `5201` |
