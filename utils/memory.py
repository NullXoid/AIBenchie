import json
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path("memory/memory.json")
NOTES_FILE = Path("memory/notes.md")

# Ensure memory folder and files exist
MEMORY_FILE.parent.mkdir(exist_ok=True)
if not MEMORY_FILE.exists():
    MEMORY_FILE.write_text("[]")

if not NOTES_FILE.exists():
    NOTES_FILE.write_text("# NullXoid Notes\n\n")

def save_memory_item(label, content, tags=None):
    item = {
        "timestamp": datetime.now().isoformat(),
        "label": label,
        "content": content,
        "tags": tags or []
    }
    data = json.loads(MEMORY_FILE.read_text())
    data.append(item)
    MEMORY_FILE.write_text(json.dumps(data, indent=2))

def save_note(text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with NOTES_FILE.open("a", encoding="utf-8") as f:
        f.write(f"\n## {timestamp}\n{text}\n")

def get_recent_memory(limit=5):
    data = json.loads(MEMORY_FILE.read_text())
    return data[-limit:]

def find_memory_by_keyword(keyword):
    data = json.loads(MEMORY_FILE.read_text())
    return [item for item in data if keyword.lower() in item["content"].lower()]
