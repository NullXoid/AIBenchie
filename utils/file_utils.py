# utils/file_utils.py
# Description: File resolution utility for locating user files across common directories with fuzzy name support.

from pathlib import Path
from rich import print
from rich.prompt import Prompt
import re

def resolve_file_path(filename: str):
    search_dirs = [
        Path.home() / "Desktop",
        Path.home() / "Downloads",
        Path.home() / "Documents"
    ]

    # Normalize search keyword (lowercase, no extension)
    name_pattern = Path(filename).stem.lower()

    matches = []
    for directory in search_dirs:
        for path in directory.glob("*"):
            if name_pattern in path.stem.lower():  # Fuzzy match (e.g., "comfyui" matches "ComfyUI.lnk")
                matches.append(path)

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print("[yellow]Multiple matches found:[/yellow]")
        for i, match in enumerate(matches):
            print(f"[{i}] {match}")
        choice = Prompt.ask("Which file do you want to open? (index)", default="0")
        try:
            index = int(choice)
            return matches[index]
        except Exception:
            print("[red]Invalid choice.[/red]")
            return None
    else:
        print(f"[red]No matches found for {filename}[/red]")
        return None
