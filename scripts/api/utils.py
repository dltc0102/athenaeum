import re, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BOOKSHELF_DIR = ROOT / "Bookshelf"
COVER_DIR = ROOT / "cover_images"
PROGRESS_PATH = ROOT / "progress.json"
FAVORITES_PATH = ROOT / "favorites.json"
ARCHIVE_PATH = ROOT / "archive.json"

def load_json(path: Path, default):
    if not path.exists():
        save_json(path, default)
        return default

    try:
        with open(path, "r", encoding="utf-8") as file:
            content = file.read().strip()

            if not content:
                save_json(path, default)
                return default

            return json.loads(content)

    except json.JSONDecodeError:
        save_json(path, default)
        return default

def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

def list_comics() -> list[str]:
    if not BOOKSHELF_DIR.exists():
        return []

    return sorted([
        item.name
        for item in BOOKSHELF_DIR.iterdir()
        if item.is_dir()
    ], key=str.lower)

def comic_name_to_cover_stem(comic_name: str) -> str:
    filename = comic_name.lower()
    filename = filename.replace("♂", "").replace("♀", "")
    filename = re.sub(r"[^\w\s\-+]", "", filename)
    filename = filename.replace(" ", "_").replace("-", "_")
    filename = re.sub(r"_+", "_", filename)
    filename = filename.strip("_")
    return filename

def get_cover_filename(comic_name: str) -> str | None:
    cover_stem = comic_name_to_cover_stem(comic_name)

    for file in COVER_DIR.iterdir():
        if file.is_file() and file.stem == cover_stem:
            return file.name

    return None

def normalize_chapter(value: str) -> str:
    return str(value).strip()

def chapter_sort_key(value: str):
    parts = re.findall(r"\d+|\D+", value)
    return [int(part) if part.isdigit() else part.lower() for part in parts]

def get_chapters(comic_name: str) -> list[str]:
    comic_dir = BOOKSHELF_DIR / comic_name

    if not comic_dir.exists():
        return []

    chapters = set()

    for file in comic_dir.iterdir():
        match = re.match(r"chapter-(.+)-p\d+\.(jpg|jpeg|png|webp)$", file.name, re.I)
        if match:
            chapters.add(match.group(1))

    return sorted(chapters, key=chapter_sort_key)

def get_chapter_images(comic_name: str, chapter_num: str) -> list[str]:
    comic_dir = BOOKSHELF_DIR / comic_name

    if not comic_dir.exists():
        return []

    pattern = re.compile(
        rf"chapter-{re.escape(chapter_num)}-p(\d+)\.(jpg|jpeg|png|webp)$",
        re.I,
    )

    images = []

    for file in comic_dir.iterdir():
        match = pattern.match(file.name)
        if match:
            images.append((int(match.group(1)), file.name))

    return [
        filename
        for _, filename in sorted(images)
    ]