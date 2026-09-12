import os
import shutil
from PIL import Image
import pytesseract


def get_downloads_path():
    return os.path.expanduser("C:\\Users\\pavan\\Downloads")


def get_all_files():
    path = get_downloads_path()
    return [os.path.join(path, f) for f in os.listdir(path)]


def extract_text_from_image(path):
    try:
        return pytesseract.image_to_string(Image.open(path))
    except:
        return ""


def move_file(old_path, new_name, category):
    base_dir = os.path.join(get_downloads_path(), "organized_files")
    category_path = os.path.join(base_dir, category)

    os.makedirs(category_path, exist_ok=True)

    ext = os.path.splitext(old_path)[1]
    new_name = (new_name or "").strip()
    if not new_name:
        new_name = os.path.splitext(os.path.basename(old_path))[0] or "unknown"

    new_path = os.path.join(category_path, new_name + ext)

    shutil.move(old_path, new_path)

    print(f"Moved: {old_path} -> {new_path}")