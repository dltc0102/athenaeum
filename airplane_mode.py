# to download specific comics with chapters for offline reading

import os, shutil, zipfile, json, re, ebooklib, io
from ebooklib import epub
from PIL import Image
from pathlib import Path
from tqdm import tqdm


""" Changelog 
v1.0.1
Fixes:
-   Problem: Aeronaeum folder for output was being reset everytime the program was run, thus completed downloads were being erased and 
    extended the time taken for other comics to download.
    Solution: Made sure that Aeronaeum folder is not deleted, but incomplete directories are

-   Problem: Splitting images for all chapters made the chunks folder too big (n_chapters*n_chunks)
    Solution: For every 5 chapters of split image chunks, the chunks are added to epub and deleted from the chunk folder to reduce folder size.
    Changes:
        - removed airplane_temp directory

Changes:
- Reduced the __init__ function of Ebook classmethod to have less clutter, improving readability


-----

v1.0.0
+ Converted comic pngs into cbz to be read in the cbz viewer

"""
class Ebook:
    def __init__(self, comic_config: str | list[str]):
        self.chapter_regex = re.compile(r"chapter-(\d+)-p(\d+)\.(webp|jpg|jpeg|png)")
        self.comic_input = comic_config

        if isinstance(comic_config, str):
            self.comic_name = comic_config
            self.comic_config = self.get_comic_config()
        else:
            self.comic_name = comic_config[0]
            self.comic_config = comic_config

        if not self.comic_config:
            raise ValueError(f'Comic input {comic_config} is wrong.')

        self.comic_domain = self.comic_config[1]

        if self.comic_domain in ["utoon", "vortexscans", "mangafire"]:
            raise ValueError("Skipped domain")

        self.reso_w = 1284
        self.reso_h = 2778

        self.book = epub.EpubBook()

    def build(self):
        print(f"Building: {self.comic_name}")

        self._setup_paths()
        self._load_cover()
        self._load_comic_data()

        self._setup_book_metadata()
        self._add_css()

        self._process_all_chapters()

        self._finalise_book()
        self._write_book()
        self._cleanup()
        return
    
    def _setup_paths(self) -> None:
        self.base_path = Path.cwd()
        self.aeronaeum_dirpath: Path = self.base_path / "Aeronaeum"
        os.makedirs(self.aeronaeum_dirpath, exist_ok=True)

        self.bookshelf_dirpath: Path = self.base_path / "Bookshelf"
        self.comic_source_dirpath: Path = self.bookshelf_dirpath / self.comic_name
        self.aeronaeum_comic_dirpath: Path = self.aeronaeum_dirpath / self.comic_name

        if not self.aeronaeum_comic_dirpath.exists():
            shutil.copytree(self.comic_source_dirpath, self.aeronaeum_comic_dirpath)
        return
        
    def _load_cover(self) -> None:
        self.cover_images_dirpath: str = os.path.join(os.getcwd(), "cover_images")
        self.comic_cover_img_filepath: str = self.get_comic_cover_image()
        self.cover_image_content = open(self.comic_cover_img_filepath, "rb").read()
        print(self.comic_cover_img_filepath)
        return
    
    def _load_comic_data(self) -> None:
        self.aeronaeum_comic_data = self.get_comic_airplane_data()
        self.sorted_comic_data = sorted(self.aeronaeum_comic_data.items())
        return
    
    def _setup_book_metadata(self) -> None:
        self.book.set_title(self.comic_name)
        self.book.set_language("en")
        self.book.add_author(self.comic_domain)
        self.book.set_cover(self.comic_cover_img_filepath, self.cover_image_content)

        self.book.spine = ["nav"]
        self.book.toc = []
        return

    def _add_css(self) -> None:
        css = epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=self.generate_css()
        )
        self.book.add_item(css)

    def _process_all_chapters(self) -> None:
        with tqdm(total=len(self.sorted_comic_data), 
              desc=f"{self.comic_name}", 
              unit="chapter",
              bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} chapters"
        ) as pbar:
            for chapter_idx, chapter_images in self.sorted_comic_data:
                chunks = self.process_chapter_images((chapter_idx, chapter_images))
                first_page = self._add_chapter_to_book(chapter_idx, chunks)
                if first_page:
                    self.book.toc.append(
                        epub.Link(first_page, f'Chapter {chapter_idx}', f'ch{chapter_idx}')
                    )
                    pbar.set_postfix(current_chapter=chapter_idx, images=len(chunks))
                    pbar.update(1)
        return

    def _add_chapter_to_book(self, chapter_idx, chunks) -> str:
        first_page_filename = None

        for chunk_idx, chunk_img in enumerate(chunks, start=1):
            page_filename = self.process_chunk_to_xhtml_memory(
                chapter_idx, chunk_idx, chunk_img
            )

            if chunk_idx == 1:
                first_page_filename = page_filename

        return first_page_filename

    def _finalise_book(self) -> None:
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())

        self.book.toc = tuple(self.book.toc)
        self.book.spine = ['nav'] + self.book.spine
        return
    
    def _write_book(self) -> None:
        self.epub_filename = f"{self.comic_name}.epub"
        self.epub_filepath = os.path.join(self.aeronaeum_dirpath, self.epub_filename)
        epub.write_epub(self.epub_filepath, self.book)
        return
    
    def _cleanup(self) -> None:
        shutil.rmtree(self.aeronaeum_comic_dirpath)
        return
    
    def get_epub_filepath(self) -> str:
        return self.epub_filepath

    def process_chunk_to_xhtml_memory(self, chapter_idx: int, chunk_idx: int, image: Image.Image):
        img_filename = f"chapter_{chapter_idx}_c{chunk_idx}.jpg"

        img_bytes = io.BytesIO()
        image.save(img_bytes, format="JPEG", quality=95)

        page_filename = f"chapter_{chapter_idx}_page_{chunk_idx}.xhtml"

        xhtml_content = f"""<?xml version="1.0" encoding="utf-8"?>
    <!DOCTYPE html>
    <html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <title>{self.comic_name} - Chapter {chapter_idx} Page {chunk_idx}</title>
        <meta charset="utf-8"/>
    </head>
    <body style="margin:0; padding:0; background:black;">
        <img src="chunks/{img_filename}" style="width:100%; display:block;" />
    </body>
    </html>"""

        page_item = epub.EpubHtml(
            title=f'Chapter {chapter_idx} - Page {chunk_idx}',
            file_name=page_filename,
            lang='en'
        )
        page_item.content = xhtml_content.encode('utf-8')
        self.book.add_item(page_item)

        # Image item
        img_item = epub.EpubImage()
        img_item.file_name = f"chunks/{img_filename}"
        img_item.media_type = "image/jpeg"
        img_item.content = img_bytes.getvalue()

        self.book.add_item(img_item)

        # Spine
        self.book.spine.append(page_item)

        return page_filename
    
    def process_chapter_images(self, chapter_data):
        chapter_idx, chapter_img_filenames = chapter_data
        if not chapter_img_filenames:
            raise ValueError(f"Warning: Chapter {chapter_idx} has no image files")
        
        chapter_img_filepaths = [os.path.join(self.aeronaeum_comic_dirpath, f) for f in chapter_img_filenames]

        all_chunks = []
        for filepath in chapter_img_filepaths:
            try:
                img = Image.open(filepath)
                img = self.normalise_image_mode(img)
                chunks = self.process_image_to_chunks(img, self.reso_w, self.reso_h)
                all_chunks.extend(chunks)
            except Exception as e:
                raise ValueError(f"Error processing {filepath}: {e}")
            
        return all_chunks

    def get_comic_airplane_data(self) -> dict[int, list[str]]:
        data = {}
        for file in os.listdir(self.aeronaeum_comic_dirpath):
            match = self.chapter_regex.match(file)
            if match:
                chapter_num = int(match.group(1))
                data.setdefault(chapter_num, []).append(file)
        return data

    def generate_css(self) -> str: 
        return """
            body {
            margin: 0;
            padding: 0;
            background: black;
        }
        """

    def get_comic_config(self) -> list[str]:
        with open("catalogue.json") as c:
            catalogue_data: list[list[str]] = json.load(c)
        
        for comic_item in catalogue_data:
            if comic_item[0] == self.comic_name:
                return comic_item

    def unformat_to_camel_case(self, some_str: str) -> str:
        unformatted_string: str = re.sub(r"[+.,!?~:\{\}\(\)\[\]\'\u2019\u2013\u2026]", "", some_str.lower().strip())
        unformatted_string = re.sub(r"[ -]+", "_", unformatted_string)
        return unformatted_string
    
    def get_comic_cover_image(self) -> str:
        img_files = os.listdir(self.cover_images_dirpath)
        for img_filepath in img_files:
            img_filename: str = os.path.splitext(img_filepath)[0]
            unformatted_comic_name = self.unformat_to_camel_case(self.comic_name)
            if img_filename == unformatted_comic_name:
                return os.path.join(self.cover_images_dirpath, img_filepath)
        raise FileNotFoundError(f'Comic {unformatted_comic_name} ({self.comic_name}) was not found in self.cover_images_dirpath')

    def normalise_image_mode(self, img_object: Image) -> Image:
        img_mode = img_object.mode
        if img_mode == "RGBA":
            background = Image.new("RGB", img_object.size, (255, 255, 255))
            background.paste(img_object, mask=img_object.split()[-1])
            return background
        elif img_mode != "RGB":
            return img_object.convert("RGB")
        return img_object

    def process_image_to_chunks(self, img_object: Image, target_w: int, target_h: int) -> list[Image.Image]:
        img_w, img_h = img_object.size
        
        if img_w != target_w:
            ratio = target_w / img_w
            new_h = int(img_h * ratio)
            img_object = img_object.resize((target_w, new_h), Image.Resampling.LANCZOS)
            img_h = new_h
        
        chunks = []
        for y in range(0, img_h, target_h):
            chunk_bottom = min(y + target_h, img_h)
            chunk = img_object.crop((0, y, target_w, chunk_bottom))
            chunks.append(chunk)
        
        return chunks

def setup_aero_dir(aero_dir: str):
    os.makedirs(aero_dir, exist_ok=True)
    if os.path.exists("Aeronaeum"):
        files = os.listdir(os.path.join(os.getcwd(), "Aeronaeum"))
        for file in files: 
            full_path_filepath = os.path.join(os.getcwd(), "Aeronaeum", file)
            if os.path.isdir(full_path_filepath): 
                shutil.rmtree(full_path_filepath)
    print(f'Deleted Incomplete Epub Directories...\n\n')
    return

def main():
    aero_dirname: str = "Aeronaeum"
    setup_aero_dir(aero_dirname)
    selected_comics: list[str] = [
        # "Switch ON Season 2",
        # "SSS-Class Undercover Agent",
        # "CCTV",
        # "Cleaning Service",
        "1 Second",
        # "Eleceed",
        # "Astral Pet Store",
        "A World-Class Walkthrough",
        "My Wife Is a Heavenly Big Shot",
        "My Wife and I Dominate the Three Realms",
        # "Reality Quest",
        "Bug Player",
        "Superhuman Era",
        "Genius Martial Arts Trainer",
        "How I Became an SSS Rank Delivery Hunter",
        "Emperor of Solo Play",
        "Return of the Mount Hua Sect",
        "Solo Leveling: Ragnarok",
        # "Stockpiling Ten Thousand Tons of Pork During the Apocalypse",
    ]

    downloaded_epubs = [filename for filename in os.listdir(os.path.join(os.getcwd(), aero_dirname)) if filename.endswith(".epub")]
    ebooks = []
    for comic in selected_comics:
        check_filename = f"{comic}.epub"
        if check_filename in downloaded_epubs: 
            print(f'\n{check_filename} is already in the Aeronaeum. Skipping...\n--------------------------------')
            continue

        ebook = Ebook(comic)
        ebook.build()
        ebook_filepath = ebook.get_epub_filepath()
        print(f'Epub Written: {ebook_filepath}\n\n--------------------------------')
        ebooks.append(ebook_filepath)
    

    
    
if __name__ == "__main__":
    main()