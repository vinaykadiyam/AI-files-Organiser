import os
import shutil
from pathlib import Path
from datetime import datetime

import ollama

from file_utils import get_downloads_path

# ---------------- CONFIGURATION ----------------
DOWNLOADS_DIR = Path(get_downloads_path())
ORGANIZED_DIR = DOWNLOADS_DIR / "Organized"
USE_PHI_LLM = True  # Set to False to skip AI categorization
# ------------------------------------------------

# File type mapping for basic categorization
EXTENSION_MAP = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".odt", ".rtf", ".md"],
    "Spreadsheets": [".xls", ".xlsx", ".csv", ".ods"],
    "Presentations": [".ppt", ".pptx", ".odp"],
    "Videos": [".mp4", ".mkv", ".mov", ".avi", ".flv", ".wmv"],
    "Audio": [".mp3", ".wav", ".aac", ".flac", ".ogg"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Installers": [".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm"],
}

def get_category_basic(file_path: Path) -> str:
    """Categorize file based on extension."""
    ext = file_path.suffix.lower()
    for category, extensions in EXTENSION_MAP.items():
        if ext in extensions:
            return category
    return "Others"

def get_category_ai(file_path: Path) -> str:
    """Use Phi LLM locally to suggest a better category."""
    try:
        prompt = f"""
        Categorize the file '{file_path.name}' into a folder name.
        Allowed categories: {', '.join(EXTENSION_MAP)} and Others.
        Only return the category name.
        """
        response = ollama.chat(
            model="phi",
            messages=[{"role": "user", "content": prompt}],
        )
        category = response["message"]["content"].strip()
        valid_categories = set(EXTENSION_MAP) | {"Others"}
        return category if category in valid_categories else get_category_basic(file_path)
    except Exception as e:
        print(f"[AI ERROR] {e}")
        return get_category_basic(file_path)

def organize_downloads():
    """Organize files in the Downloads folder."""
    if not DOWNLOADS_DIR.exists():
        print(f"Downloads folder not found: {DOWNLOADS_DIR}")
        return

    ORGANIZED_DIR.mkdir(exist_ok=True)

    for item in DOWNLOADS_DIR.iterdir():
        if item.is_file():
            category = get_category_ai(item) if USE_PHI_LLM else get_category_basic(item)
            target_dir = ORGANIZED_DIR / category
            target_dir.mkdir(exist_ok=True)

            # Avoid overwriting files
            target_file = target_dir / item.name
            if target_file.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                target_file = target_dir / f"{item.stem}_{timestamp}{item.suffix}"

            try:
                shutil.move(str(item), str(target_file))
                print(f"Moved: {item.name} → {target_dir.name}")
            except Exception as e:
                print(f"[ERROR] Could not move {item.name}: {e}")

if __name__ == "__main__":
    organize_downloads()