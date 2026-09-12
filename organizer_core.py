from __future__ import annotations

import hashlib
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import ollama
import PyPDF2
import pytesseract
from PIL import Image


DEFAULT_MODEL = "phi"
ORGANIZED_DIR_NAME = "Organized"
DUPLICATES_DIR_NAME = "Duplicates"
EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ORGANIZED_DIR_NAME,
    "organized_files",
    DUPLICATES_DIR_NAME,
    "marked_for_delete_folder",
}

CATEGORIES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt"],
    "Spreadsheets": [".xls", ".xlsx", ".csv", ".ods"],
    "Presentations": [".ppt", ".pptx", ".odp"],
    "Videos": [".mp4", ".mkv", ".mov", ".avi", ".flv", ".wmv"],
    "Audio": [".mp3", ".wav", ".aac", ".flac", ".ogg"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Installers": [".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm"],
    "Code": [".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".json"],
}
FALLBACK_CATEGORY = "Other"
TEXT_EXTENSIONS = {".txt", ".md", ".rtf", ".csv", ".json", ".py", ".js", ".ts", ".html", ".css"}
IMAGE_EXTENSIONS = set(CATEGORIES["Images"])


@dataclass
class RunStats:
    scanned: int = 0
    categorized: int = 0
    duplicate_groups: int = 0
    duplicates_moved: int = 0
    errors: list[str] = field(default_factory=list)


def default_folder() -> Path:
    """Return the current user's Downloads folder without a machine-specific path."""
    return Path.home() / "Downloads"


def iter_files(folder: Path) -> Iterable[Path]:
    """Yield files recursively while excluding generated and environment folders."""
    for root, directories, filenames in os.walk(folder):
        directories[:] = [
            name for name in directories if name not in EXCLUDED_DIR_NAMES
        ]
        for filename in filenames:
            path = Path(root) / filename
            if path.is_file():
                yield path


def file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str | None:
    """Return a SHA-256 hash, or None when the file cannot be read."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as file:
            while chunk := file.read(chunk_size):
                digest.update(chunk)
    except OSError as error:
        print(f"[READ ERROR] {path}: {error}")
        return None
    return digest.hexdigest()


def extract_content(path: Path, max_chars: int = 8000) -> str:
    """Extract bounded text for the classifier from supported file types."""
    extension = path.suffix.lower()
    try:
        if extension in TEXT_EXTENSIONS:
            return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]

        if extension == ".pdf":
            with path.open("rb") as file:
                reader = PyPDF2.PdfReader(file)
                text = "".join(page.extract_text() or "" for page in reader.pages)
            return text[:max_chars]

        if extension in IMAGE_EXTENSIONS and extension != ".svg":
            return pytesseract.image_to_string(Image.open(path))[:max_chars]
    except (OSError, ValueError, PyPDF2.errors.PdfReadError) as error:
        print(f"[CONTENT ERROR] {path}: {error}")
    except Exception as error:
        print(f"[OCR ERROR] {path}: {error}")
    return ""


def fallback_category(path: Path) -> str:
    extension = path.suffix.lower()
    for category, extensions in CATEGORIES.items():
        if extension in extensions:
            return category
    return FALLBACK_CATEGORY


def _response_text(response) -> str:
    try:
        return response["message"]["content"].strip()
    except (KeyError, TypeError):
        return ""


def classify_file(path: Path, model: str = DEFAULT_MODEL, use_llm: bool = True) -> str:
    """Classify a file with Ollama and fall back deterministically by extension."""
    basic_category = fallback_category(path)
    if not use_llm:
        return basic_category

    content = extract_content(path)
    category_names = ", ".join([*CATEGORIES, FALLBACK_CATEGORY])
    prompt = f"""
Classify this local file into exactly one of these categories: {category_names}.

Filename: {path.name}
Extension: {path.suffix.lower()}
Extracted content (may be empty):
{content}

Return only the category name. Do not add punctuation or explanation.
"""
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = _response_text(response)
        normalized = response_text.casefold().strip(" .:-")
        for category in [*CATEGORIES, FALLBACK_CATEGORY]:
            if normalized == category.casefold():
                return category
        print(f"[AI WARNING] Invalid category for {path.name}: {response_text!r}")
    except Exception as error:
        print(f"[AI ERROR] {path.name}: {error}")
    return basic_category


def unique_target(folder: Path, source: Path) -> Path:
    """Create a collision-safe target path without overwriting an existing file."""
    target = folder / source.name
    counter = 1
    while target.exists():
        target = folder / f"{source.stem}_{counter}{source.suffix}"
        counter += 1
    return target


def find_duplicate_groups(folder: Path) -> dict[Path, dict[str, list[Path]]]:
    """Find exact duplicate groups independently inside every directory."""
    groups_by_folder: dict[Path, dict[str, list[Path]]] = {}
    hashes_by_folder: dict[Path, dict[str, list[Path]]] = {}

    for path in iter_files(folder):
        parent = path.parent
        digest = file_hash(path)
        if digest is not None:
            hashes_by_folder.setdefault(parent, {}).setdefault(digest, []).append(path)

    for parent, hashes in hashes_by_folder.items():
        duplicates = {}
        for digest, paths in hashes.items():
            if len(paths) > 1:
                duplicates[digest] = sorted(
                    paths,
                    key=lambda item: (item.stat().st_mtime_ns, str(item).casefold()),
                    reverse=True,
                )
        if duplicates:
            groups_by_folder[parent] = duplicates
    return groups_by_folder


def move_duplicates(
    groups_by_folder: dict[Path, dict[str, list[Path]]],
    dry_run: bool = False,
) -> int:
    """Keep newest files and move older copies into their source folder's Duplicates."""
    moved = 0
    for source_folder, groups in groups_by_folder.items():
        duplicates_folder = source_folder / DUPLICATES_DIR_NAME
        if not dry_run:
            duplicates_folder.mkdir(exist_ok=True)

        for paths in groups.values():
            newest = paths[0]
            for older in paths[1:]:
                target = unique_target(duplicates_folder, older)
                if dry_run:
                    print(f"[DRY RUN] Keep {newest}; move {older} -> {target}")
                    moved += 1
                    continue
                try:
                    shutil.move(str(older), str(target))
                    print(f"Kept newest: {newest}")
                    print(f"Moved duplicate: {older} -> {target}")
                    moved += 1
                except OSError as error:
                    print(f"[MOVE ERROR] {older}: {error}")
    return moved


def move_to_category(path: Path, root: Path, category: str, dry_run: bool = False) -> Path:
    destination_folder = root / ORGANIZED_DIR_NAME / category
    target = unique_target(destination_folder, path)
    if dry_run:
        print(f"[DRY RUN] Move {path} -> {target}")
        return target
    destination_folder.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(target))
    print(f"Organized: {path} -> {target}")
    return target


def organize_files(root: Path, model: str, use_llm: bool, dry_run: bool, stats: RunStats) -> None:
    for path in list(iter_files(root)):
        stats.scanned += 1
        try:
            category = classify_file(path, model=model, use_llm=use_llm)
            move_to_category(path, root, category, dry_run=dry_run)
            stats.categorized += 1
        except OSError as error:
            message = f"{path}: {error}"
            stats.errors.append(message)
            print(f"[MOVE ERROR] {message}")


def run_once(root: Path, model: str, use_llm: bool, dry_run: bool = False) -> RunStats:
    """Deduplicate source folders, organize files, then deduplicate output folders."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Folder does not exist: {root}")

    stats = RunStats()
    source_groups = find_duplicate_groups(root)
    stats.duplicate_groups += sum(len(groups) for groups in source_groups.values())
    stats.duplicates_moved += move_duplicates(source_groups, dry_run=dry_run)
    organize_files(root, model, use_llm, dry_run, stats)

    organized_root = root / ORGANIZED_DIR_NAME
    if organized_root.exists() and not dry_run:
        output_groups = find_duplicate_groups(organized_root)
        stats.duplicate_groups += sum(len(groups) for groups in output_groups.values())
        stats.duplicates_moved += move_duplicates(output_groups, dry_run=False)

    return stats


def watch(root: Path, model: str, use_llm: bool, dry_run: bool, interval: int) -> None:
    print(f"Watching {root} every {interval} seconds. Press Ctrl+C to stop.")
    while True:
        stats = run_once(root, model, use_llm, dry_run)
        print(
            f"Scan complete: {stats.scanned} scanned, "
            f"{stats.categorized} organized, {stats.duplicates_moved} duplicates moved."
        )
        time.sleep(interval)
