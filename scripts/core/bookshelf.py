import os
from scripts.utils.utils import color_msg

class Bookshelf:
    def __init__(self):
        self.bookshelf_dirpath = os.path.join(os.getcwd(), "Bookshelf")
        self._ensure_bookshelf_dir()
        self.progress_comics: dict[str, str] = {}

    def bookshelf_tag(self, msg: str) -> None:
        print(color_msg("lightgreen", f"[Bookshelf] {msg}"))

    def _ensure_bookshelf_dir(self) -> None:
        """ ensures bookshelf directory exists """
        os.makedirs(self.bookshelf_dirpath, exist_ok=True)

    def _normalise_comic_name(self, giv_name: str) -> str:
        return giv_name.replace("\u2019", "'").replace("\u2026", "...").replace("\u2013", "-").strip()

    def get_all_comics_downloaded(self):
        if not os.path.exists(self.bookshelf_dirpath):
            return []

        comics = []
        for item in os.listdir(self.bookshelf_dirpath):
            item_path = os.path.join(self.bookshelf_dirpath, item)
            if os.path.isdir(item_path):
                comics.append(item)

        return comics

    def register_comic(self, normalised_name: str) -> str:
        self.bookshelf_tag(f"Running Bookshelf.register_comic")
        comic_dirpath: str = os.path.join(self.bookshelf_dirpath, normalised_name)
        os.makedirs(comic_dirpath, exist_ok=True)
        self.bookshelf_tag(f"[+Dir] Created {normalised_name} comic dir.")
        return comic_dirpath

    def setup_comic(self, comic_name: str) -> str:
        self.bookshelf_tag(f"Running Bookshelf.setup_comic")
        comics_in_bookshelf: list[str] = self.get_all_comics_downloaded()
        normalised_name: str = self._normalise_comic_name(comic_name)
        if normalised_name not in self.progress_comics.keys():
            self.progress_comics[normalised_name] = 1
        else:
            pass

        if normalised_name in comics_in_bookshelf:
            comic_dirpath = os.path.join(self.bookshelf_dirpath, normalised_name)
            return comic_dirpath
        else:
            return self.register_comic(normalised_name)
