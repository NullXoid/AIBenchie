# V0.8 Freeze

- Generated at: `2026-04-20T02:22:33.782528+00:00`
- Base model: `Qwen/Qwen2.5-1.5B-Instruct`
- Adapter path: `models/adapters/lv7_sft_smoke_v0_8/`
- Dataset dir: `data/pilot_v1_5/`
- Config path: `training/qlora_smoke_config.yaml`
- Seed: `42`
- Eval suite: `lv7_smoke_v1_2`
- Strict score: `11/11`
- Pytest result: `52 passed`

## Tracked Files

| path | sha256 | size_bytes | line_count |
| --- | --- | --- | --- |
| `data/pilot_v1_5/sft_messages.jsonl` | `4d78d6b589e42e64b8546741cc0e29af70312ecd6a09a0944233df6b19f25f28` | `374705` | `136` |
| `data/pilot_v1_5/sft_train_ready.jsonl` | `f35b7e8a9dca25ab7d0d941a3f03fec84696a2b685c63670c8487be0f9fdf153` | `469189` | `136` |
| `reports/training/v0_8_sft_eval_results.jsonl` | `411a8eb4dd4abd1caba8e7d1b53af02df11e84cd15e045a0da9ffd559d99a4c7` | `26690` | `11` |
| `training/qlora_smoke_config.yaml` | `6e5a9dc4eb3afb130bc8a6bf88c4b850135a224ae854e1534e34de6e47beb5a8` | `1710` | `52` |

## Adapter Files

| path | sha256 | size_bytes |
| --- | --- | --- |
| `adapter_config.json` | `345bbea9c6bbafa1143b069b5d8aa7a4750d03cb247366baac7d7055b25a0b55` | `1105` |
| `adapter_model.safetensors` | `83ae1626bc7a4694a3c533d1ff4d4c455b0b153e3b3a226dc0c756f643472cbc` | `73911112` |
| `chat_template.jinja` | `cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f` | `2507` |
| `checkpoint-128/adapter_config.json` | `345bbea9c6bbafa1143b069b5d8aa7a4750d03cb247366baac7d7055b25a0b55` | `1105` |
| `checkpoint-128/adapter_model.safetensors` | `83ae1626bc7a4694a3c533d1ff4d4c455b0b153e3b3a226dc0c756f643472cbc` | `73911112` |
| `checkpoint-128/README.md` | `cb3cdefbcf1962832683ba0c254e668036400b8b081eef936ed72964b2419408` | `5206` |
| `checkpoint-128/trainer_state.json` | `647163e9967179d821ed96f5f0016adcf61f9d0f6859fe6c8f6fc5ed006e2663` | `23356` |
| `checkpoint-128/training_args.bin` | `ca9d975314fe963988f5358c7ad188e1669a0ac795dbbef8bf0a3fc403c66794` | `5201` |
| `README.md` | `cb3cdefbcf1962832683ba0c254e668036400b8b081eef936ed72964b2419408` | `5206` |
| `tokenizer.json` | `2f55e63353d3d978b390d346bae531be8b83bc9532c0be500d62b7253aa4c595` | `11421991` |
| `tokenizer_config.json` | `47bfa3e7727312946b29ac10d6dd0672d63cf7815b2a160b9523872040d2e536` | `665` |
| `training_args.bin` | `ca9d975314fe963988f5358c7ad188e1669a0ac795dbbef8bf0a3fc403c66794` | `5201` |

This freeze records the accepted v0.8 artifact state before any holdout robustness review.
