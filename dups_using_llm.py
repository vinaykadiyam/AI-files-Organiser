import hashlib
import os
import shutil
from pathlib import Path

from file_utils import get_downloads_path


DUPLICATES_FOLDER_NAME = "Duplicates"


def file_hash(path, block_size=65536):
    """Return a file's SHA-256 hash, or None if the file cannot be read."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as file:
            while chunk := file.read(block_size):
                digest.update(chunk)
    except OSError as error:
        print(f"Could not read {path}: {error}")
        return None
    return digest.hexdigest()


def find_duplicates(folder):
    """Find duplicate files within each individual folder.

    Each result group is ordered newest first, so the first path is kept.
    """
    folder = Path(folder)
    duplicates = {}

    for root, directories, files in os.walk(folder):
        directories[:] = [
            directory
            for directory in directories
            if directory != DUPLICATES_FOLDER_NAME
        ]

        hashes = {}
        for name in files:
            path = Path(root) / name
            digest = file_hash(path)
            if digest is None:
                continue
            hashes.setdefault(digest, []).append(path)

        folder_duplicates = {
            digest: sorted(
                paths,
                key=lambda path: (path.stat().st_mtime_ns, str(path)),
                reverse=True,
            )
            for digest, paths in hashes.items()
            if len(paths) > 1
        }
        if folder_duplicates:
            duplicates[Path(root)] = folder_duplicates

    return duplicates


def _unique_target(folder, source):
    """Return a non-conflicting destination for a duplicate file."""
    target = folder / source.name
    counter = 1
    while target.exists():
        target = folder / f"{source.stem}_{counter}{source.suffix}"
        counter += 1
    return target


def move_duplicates(duplicates):
    """Move every duplicate except the newest file in each group."""
    moved_count = 0

    for source_folder, groups in duplicates.items():
        duplicates_folder = source_folder / DUPLICATES_FOLDER_NAME
        duplicates_folder.mkdir(exist_ok=True)

        for paths in groups.values():
            newest = paths[0]
            for older_file in paths[1:]:
                if not older_file.exists():
                    continue

                target = _unique_target(duplicates_folder, older_file)
                try:
                    shutil.move(str(older_file), str(target))
                    moved_count += 1
                    print(f"Kept newest: {newest}")
                    print(f"Moved older duplicate: {older_file} -> {target}")
                except OSError as error:
                    print(f"Could not move {older_file}: {error}")

    return moved_count


if __name__ == "__main__":
    downloads_folder = Path(get_downloads_path())
    duplicate_groups = find_duplicates(downloads_folder)
    group_count = sum(len(groups) for groups in duplicate_groups.values())
    print(f"Found {group_count} duplicate group(s).")

    if duplicate_groups:
        moved_count = move_duplicates(duplicate_groups)
        print(f"Moved {moved_count} older duplicate file(s).")
    else:
        print("No duplicates found.")
