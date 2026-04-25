from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SOURCE_JSONL = ROOT / "data" / "lv7_traceable_batches_001R_002" / "combined" / "all_training_records_v1_1.jsonl"
SOURCE_JSONL_V1_2 = ROOT / "data" / "lv7_traceable_batches_003" / "combined" / "all_training_records_v1_2.jsonl"
SOURCE_JSONL_V1_3 = ROOT / "data" / "lv7_traceable_batches_004" / "combined" / "all_training_records_v1_3.jsonl"
SOURCE_JSONL_V1_4 = ROOT / "data" / "lv7_traceable_batches_005" / "combined" / "all_training_records_v1_4.jsonl"
SOURCE_JSONL_V1_5 = ROOT / "data" / "lv7_traceable_batches_006" / "combined" / "all_training_records_v1_5.jsonl"
SOURCE_JSONL_V1_6 = ROOT / "data" / "lv7_traceable_batches_007" / "combined" / "all_training_records_v1_6.jsonl"
SOURCE_JSONL_V1_7 = ROOT / "data" / "lv7_traceable_batches_008" / "combined" / "all_training_records_v1_7.jsonl"
SOURCE_JSONL_V1_8 = ROOT / "data" / "lv7_traceable_batches_009" / "combined" / "all_training_records_v1_8.jsonl"
SOURCE_JSONL_V1_9 = ROOT / "data" / "lv7_traceable_batches_010" / "combined" / "all_training_records_v1_9.jsonl"
SCENARIOS_DIR = ROOT / "evals" / "scenarios"
HOLDOUT_PARAPHRASE_DIR = ROOT / "evals" / "holdout" / "paraphrase_v0"
SFT_MESSAGES_V1_2 = ROOT / "data" / "pilot_v1_2" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_2 = ROOT / "data" / "pilot_v1_2" / "sft_train_ready.jsonl"
PILOT_V1_3_DIR = ROOT / "data" / "pilot_v1_3"
SFT_MESSAGES_V1_3 = ROOT / "data" / "pilot_v1_3" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_3 = ROOT / "data" / "pilot_v1_3" / "sft_train_ready.jsonl"
PILOT_V1_4_DIR = ROOT / "data" / "pilot_v1_4"
SFT_MESSAGES_V1_4 = ROOT / "data" / "pilot_v1_4" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_4 = ROOT / "data" / "pilot_v1_4" / "sft_train_ready.jsonl"
PILOT_V1_5_DIR = ROOT / "data" / "pilot_v1_5"
SFT_MESSAGES_V1_5 = ROOT / "data" / "pilot_v1_5" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_5 = ROOT / "data" / "pilot_v1_5" / "sft_train_ready.jsonl"
PILOT_V1_6_DIR = ROOT / "data" / "pilot_v1_6"
SFT_MESSAGES_V1_6 = ROOT / "data" / "pilot_v1_6" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_6 = ROOT / "data" / "pilot_v1_6" / "sft_train_ready.jsonl"
PILOT_V1_7_DIR = ROOT / "data" / "pilot_v1_7"
SFT_MESSAGES_V1_7 = ROOT / "data" / "pilot_v1_7" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_7 = ROOT / "data" / "pilot_v1_7" / "sft_train_ready.jsonl"
PILOT_V1_8_DIR = ROOT / "data" / "pilot_v1_8"
SFT_MESSAGES_V1_8 = ROOT / "data" / "pilot_v1_8" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_8 = ROOT / "data" / "pilot_v1_8" / "sft_train_ready.jsonl"
PILOT_V1_9_DIR = ROOT / "data" / "pilot_v1_9"
SFT_MESSAGES_V1_9 = ROOT / "data" / "pilot_v1_9" / "sft_messages.jsonl"
SFT_TRAIN_READY_V1_9 = ROOT / "data" / "pilot_v1_9" / "sft_train_ready.jsonl"
