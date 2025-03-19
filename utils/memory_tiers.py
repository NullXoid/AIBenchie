# utils/memory_tiers.py

import json
from pathlib import Path
from datetime import datetime

# Define paths for memory tiers
TIERS = {
    "identity": Path("memory/identity_memory.json"),
    "context": Path("memory/context_memory.json"),
    "longterm": Path("memory/memory.json")
}

# Get identity value for a specific label
def get_identity_value(label):
    """Search high-tier memory for a specific identity label."""
    identity_path = TIERS["identity"]
    if not identity_path.exists():
        return None

    with open(identity_path, "r") as f:
        try:
            items = json.load(f)
            for item in items:
                if item.get("label", "").lower() == label.lower():
                    return item.get("content")
        except json.JSONDecodeError:
            pass
    return None

# Ensure memory directory and files exist
for path in TIERS.values():
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]")

# Load data from a tier
def load_memory(tier):
    path = TIERS[tier]
    return json.loads(path.read_text())

# Save data to a tier
def save_memory(tier, data):
    path = TIERS[tier]
    path.write_text(json.dumps(data, indent=2))

# Add a new memory item
def add_memory_item(tier, label, content, tags=None):
    item = {
        "timestamp": datetime.now().isoformat(),
        "label": label,
        "content": content,
        "tags": tags or []
    }
    data = load_memory(tier)
    data.append(item)
    save_memory(tier, data)

# Search for keyword in a tier
def search_memory(tier, keyword):
    data = load_memory(tier)
    return [item for item in data if keyword.lower() in item["content"].lower()]

# Escalate search through tiers in order
TIER_ORDER = ["identity", "context", "longterm"]

def search_all_tiers(keyword):
    results = []
    for tier in TIER_ORDER:
        matches = search_memory(tier, keyword)
        if matches:
            results.extend(matches)
            break
    return results

# Move item between tiers by label match
def move_memory_item(label, from_tier, to_tier):
    from_data = load_memory(from_tier)
    to_data = load_memory(to_tier)

    moved = [item for item in from_data if item["label"] == label]
    if not moved:
        return False

    from_data = [item for item in from_data if item["label"] != label]
    to_data.extend(moved)

    save_memory(from_tier, from_data)
    save_memory(to_tier, to_data)
    return True

# Get memory by label from a specific tier
def get_memory_by_label(label, tier="identity"):
    data = load_memory(tier)
    for item in data:
        if item["label"] == label:
            return item["content"]
    return None

# Promote memory importance one tier up if possible
def promote_memory(label):
    for i in reversed(range(len(TIER_ORDER))):
        tier = TIER_ORDER[i]
        data = load_memory(tier)
        if any(item["label"] == label for item in data):
            if i == 0:
                return False  # Already in highest tier
            return move_memory_item(label, tier, TIER_ORDER[i - 1])
    return False

# Demote memory importance one tier down if possible
def demote_memory(label):
    for i in range(len(TIER_ORDER)):
        tier = TIER_ORDER[i]
        data = load_memory(tier)
        if any(item["label"] == label for item in data):
            if i == len(TIER_ORDER) - 1:
                return False  # Already in lowest tier
            return move_memory_item(label, tier, TIER_ORDER[i + 1])
    return False

# Get the current tier of a memory item by label
def get_memory_tier(label):
    for tier in TIER_ORDER:
        data = load_memory(tier)
        if any(item["label"] == label for item in data):
            return tier
    return None

# Detect importance command and adjust tier
def handle_importance_command(command: str, label: str):
    command = command.lower().strip()
    if "more important" in command:
        success = promote_memory(label)
        return f"🔼 Promoted '{label}' to a higher tier." if success else f"'{label}' is already in the highest tier."
    elif "not that important" in command:
        success = demote_memory(label)
        return f"🔽 Demoted '{label}' to a lower tier." if success else f"'{label}' is already in the lowest tier."
    return "⚠️ No importance-related action detected."

# Used in controller to apply importance phrases to recent memory
def detect_and_apply_importance(user_input, recent_label):
    if "more important" in user_input.lower() or "not that important" in user_input.lower():
        return handle_importance_command(user_input, recent_label)
    return None
