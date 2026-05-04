import os, httpx, re, asyncio, json, time
from typing import Optional
from scripts.core.bookshelf import Bookshelf
from scripts.utils.utils import color_msg, reset_dir

class ControlPanel:
    def __init__(self, headers: dict[str, str], async_client: httpx.AsyncClient, archivist_inst):
        self.headers = headers
        self.async_client = async_client
        self.archivist_inst = archivist_inst
        self.bookshelf = Bookshelf()
        self.comic_buffer_bypasses: list[str] = ["Eleceed"]
        self.cover_images_dirpath = os.path.join(os.getcwd(), "cover_images")
        self.possible_image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg'}
        self.cover_images: list[str] = []

        if not os.path.exists(self.cover_images_dirpath):
            os.makedirs(self.cover_images_dirpath, exist_ok=True)

        if os.path.exists(self.cover_images_dirpath):
            self.cover_images = [
                file for file in os.listdir(self.cover_images_dirpath) if os.path.splitext(file)[1].lower() in self.possible_image_exts
            ]
        self.dev_mode = 0
        self.configs_to_be_updated = []
        self.failed_fetches = []

    def catch_and_notify(self, func):
        """Decorator to catch errors and send to Discord"""
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                await self.notify_error(f"Error in {func.__name__}: {str(e)}", error=e)
                raise
        return wrapper
        
    async def notify_message(self, message: str):await self.archivist_inst.notify_message(message)

    async def notify_error(self, message: str, error: Exception=None):
        await self.archivist_inst.notify_error(message, error)
        await self.archivist_inst.mention()
        raise ValueError(message)

    def get_failed_fetches(self) -> list[str]: return self.failed_fetches

    def get_progress_comics(self) -> dict[str, str]: return self.bookshelf.progress_comics

    def cleanup_config(self) -> None:
        if self.configs_to_be_updated == []:
            self.panel_tag("No configs to update.")
            return
        self.panel_tag(f'cleanup_config has {len(self.configs_to_be_updated)} configs to be updated.')
        for config in self.configs_to_be_updated:
            self.panel_tag(config)

    def panel_tag(self, msg: str) -> None: print(color_msg("lightblue", f"[Control] {msg}"))

    def dev_tag(self, msg: str) -> None: print(color_msg("lightred", f"[DEV] {msg}"))

    async def validate_image_link(self, link: str) -> bool:
        # self.dev_tag(f'ControlPanel.validate_image_link(link): link = {link}')
        if not link.startswith("https://"): return False
        timeout = httpx.Timeout(connect=20.0, read=60.0, write=20.0, pool=20.0)
        try:
            async with self.async_client.stream("GET", link, follow_redirects=True, timeout=timeout, headers=self.headers) as response:
                if response.status_code != 200: return False
                content_type = response.headers.get("content-type", "").lower()
                if not content_type.startswith("image/"): return False
                async for chunk in response.aiter_bytes(chunk_size=1024):
                    return bool(chunk)

        except httpx.ReadTimeout:
            print(color_msg("yellow", f"Validation timeout: {link}"))
            await asyncio.sleep(1.5)

        except Exception as e:
            print(color_msg("yellow", f"Validation failed: {link} - {type(e).__name__}: {repr(e)}"))
            return False
        return False

    @staticmethod
    def get_url_comic_name(comic_name: str, domain_name=None) -> str:
        if domain_name == "manhwaread" and comic_name == "My Boyfriend's Dad's Fuck Examination": return "my-boyfriends-dads-fuck-examination" 
        if domain_name == "manhuaus" and comic_name == "Super God Card Maker": return "super-god-card-maker-1"
        if comic_name == "KinkFolder.ZIP": return "kinkfolder-zip"
        if comic_name == "Reality Quest": comic_name = "Reality Quest 2"
        if domain_name == "omegascans":
            if comic_name == "Mother and Daughter\u2019s Home": return "mother-and-daughters-home"
            if "I\u2019m " in comic_name: comic_name = comic_name.replace("I\u2019m ", "Im ")
        # if domain_name == "mangakatana": comic_name = comic_name.replace("\u2019", "").replace("'", "")

        res = comic_name.lower()
        if domain_name == "vortexscans":
            if comic_name == "Apocalyptic Chef Awakening":
                return "apocalyptic-chef-awakening4"
            res = res.replace(":", "%3A")
            
        chars_to_remove = ["(", ")", ":", "\u2013", "\u2026", "!", "?", "%", ".", "~", ",", "+", "/", "[", "]", "♂", "♀"]
        chars_to_replace = [" ", "'", "\u2019"]

        if domain_name in ["manga18", "manhuaus", "yakshascans", "manhwabuddy", "pornhwa", "kingofshojo", "ravenscans", "manhwaread"]:
            res = res.replace("\u2019", "")

        for char in chars_to_remove:
            res = res.replace(char, "")

        for char in chars_to_replace:
            res = res.replace(char, "-")
        res = re.sub(r'-+', '-', res)
        res = res.strip('-')
        return res.strip()

    async def get_url_response(self, url: str) -> Optional[httpx.Response]:
        res = await self.async_client.get(url)
        return res if res.status_code == 200 else None

    async def get_url_response_object(self, url: str) -> Optional[httpx.Response]:
        try:
            res = await self.async_client.get(url)
            return res
        except Exception as e:
            print(f"Request error: {e}")
            return None
        
    @staticmethod
    def get_cover_img_fname(comic_name: str, link: str) -> str:
        filename = comic_name.lower()
        filename = filename.replace(r"♂|♀", "")
        filename = re.sub(r'[^\w\s\-+]', '', filename)
        filename = filename.replace(' ', '_').replace('-', '_')
        filename = re.sub(r'_+', '_', filename)
        filename = filename.strip('_')
        
        extension = f'.{link.split("/")[-1].split(".")[-1]}'
        return f"{filename}{extension}"

    async def _cleanup_incomplete_chapter(self, temp_dir: str, comic_dirpath: str, chapter_num: str) -> None:
        try:
            await reset_dir(temp_dir)
            if isinstance(chapter_num, int): chapter_num = str(chapter_num)
            safer_chapter_num = chapter_num.replace('.', '-')
            try:
                if '.' in safer_chapter_num:
                    chapter_int = int(float(safer_chapter_num.split('-')[0]))
                else:
                    chapter_int = int(safer_chapter_num.split('-')[0])
            except (ValueError, IndexError):
                print(color_msg("yellow", f"Could not parse chapter number: {chapter_num}"))
                return
            
            patterns = []
            for idx in range(chapter_int-5, chapter_int):
                patterns.append(re.compile(rf"chapter-{re.escape(idx)}-p\d+\.jpg"))

            deleted_files = []
            if os.path.exists(comic_dirpath):
                for file_name in os.listdir(comic_dirpath):
                    for pattern in patterns:
                        if pattern.match(file_name):
                            file_path = os.path.join(comic_dirpath, file_name)
                            os.remove(file_path)
                            deleted_files.append(file_name)
            if deleted_files:
                print(color_msg("yellow", f"Deleted incomplete chapter files: {deleted_files}"))
            
        except Exception as cleanup_error:
            print(color_msg("red", f"Error during cleanup: {cleanup_error}"))

    def get_progress_of_comic(self, comic_name: str) -> int:
        with open("progress.json", 'r', encoding='utf-8') as p:
            progress_data = json.load(p)
        if comic_name in progress_data.keys():
            return progress_data[comic_name]
        else:
            return 1
    
    def get_comic_dirpath_data(self, chapter_list: list[str]) -> tuple[list[str], list[str]]:
        first_fragment_files = sorted([file for file in os.listdir(self.comic_dirpath) if file.endswith("p1.jpg")])

        def normalize_chapter(raw: str) -> str | None:
            raw = str(raw)
            if (m := re.match(r"^(\d+)x(\d+)$", raw)): return str(float(f"{m.group(1)}.{m.group(2)}"))
            if (m := re.match(r"^(\d+)-(\d+)$", raw)): return str(float(f"{m.group(1)}.{m.group(2)}"))
            if (m := re.match(r"^(\d+)\.(\d+)$", raw)): return f"{int(m.group(1))}.{int(m.group(2))}"
            if (m := re.match(r"^(\d+)", raw)): return str(int(m.group(1)))
            return None

        def extract_and_normalize(filename: str) -> str | None:
            return normalize_chapter(m.group(1)) if (m := re.search(r"chapter-(.+?)-p1\.jpg", filename)) else None

        downloaded_chapters = [ch for ch in (extract_and_normalize(file) for file in first_fragment_files) if ch is not None]
        downloaded_chapters = sorted(set(downloaded_chapters), key=float)

        chapter_list_normalized = [normalize_chapter(ch) for ch in chapter_list]

        chapters_left = [original for original, normalized in zip(chapter_list, chapter_list_normalized) if normalized not in downloaded_chapters]

        # print(f'downloaded_chapters: {downloaded_chapters}')
        # print(f'chapters_left: {chapters_left}')

        return downloaded_chapters, chapters_left

