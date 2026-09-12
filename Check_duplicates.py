import os
import hashlib
import shutil
from pathlib import Path
from file_utils import get_downloads_path

def file_hash(file_path, chunk_size=8192):
    """
    Generate SHA256 hash for a file.
    Reads in chunks to handle large files efficiently.
    """
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                sha256.update(chunk)
    except (OSError, PermissionError) as e:
        print(f"Error reading {file_path}: {e}")
        return None
    return sha256.hexdigest()

def find_and_mark_duplicates(source_folder, mark_folder):
    """
    Finds duplicate files in source_folder and moves them to mark_folder.
    """
    source_folder = Path(source_folder)
    mark_folder = Path(mark_folder)

    if not source_folder.exists() or not source_folder.is_dir():
        print("Source folder does not exist or is not a directory.")
        return

    mark_folder.mkdir(parents=True, exist_ok=True)

    seen_hashes = {}
    duplicates_found = 0

    for root, directories, files in os.walk(source_folder):
        directories[:] = [
            directory for directory in directories
            if Path(root) / directory != mark_folder
        ]
        for filename in files:
            file_path = Path(root) / filename
            file_hash_value = file_hash(file_path)

            if not file_hash_value:
                continue  # Skip unreadable files

            if file_hash_value in seen_hashes:
                # Duplicate found → move to mark folder
                duplicates_found += 1
                target_path = mark_folder / filename

                # Avoid overwriting files in mark folder
                counter = 1
                while target_path.exists():
                    target_path = mark_folder / f"{target_path.stem}_{counter}{target_path.suffix}"
                    counter += 1

                try:
                    shutil.move(str(file_path), str(target_path))
                    print(f"Moved duplicate: {file_path} → {target_path}")
                except Exception as e:
                    print(f"Error moving {file_path}: {e}")
            else:
                seen_hashes[file_hash_value] = file_path

    print(f"✅ Scan complete. {duplicates_found} duplicates moved to '{mark_folder}'.")

if __name__ == "__main__":
    # Example usage
    source_dir = Path(get_downloads_path())
    mark_dir = source_dir / "marked_for_delete_folder"

    find_and_mark_duplicates(source_dir, mark_dir)