import os, re, math, asyncio, urllib.parse, aiofiles, httpx, pillow_avif
from bs4 import BeautifulSoup
from PIL import Image
from typing import Optional
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from scripts.core.control_panel import ControlPanel
from scripts.utils.utils import color_msg, reset_dir

class Downloader(ControlPanel):
    def __init__(self, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
    
    async def get_soup(self, url: str) -> Optional[BeautifulSoup]:
        async def retry_soup(url: str, retries: int) -> httpx.Response | None:
            for idx in range(retries):
                res = await self.get_url_response(url)
                if res is not None:
                    return res
                await asyncio.sleep(2)
            return None
        
        res = await retry_soup(url, retries=5)
        if res is None:
            self.dev_tag(f"Failed to fetch {url}")
            self.failed_fetches.append(url)
            return None
        return BeautifulSoup(res.content, "html.parser")
    
    @staticmethod
    def get_extension(url: str):
        return f".{url.split('/')[-1].split('.')[-1]}"
    
    async def download_single_image(self, img_link: str, img_output_path: str) -> None:
        try:
            async with self.async_client.stream('GET', img_link) as response:
                response.raise_for_status()
                async with aiofiles.open(img_output_path, 'wb') as file:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        await file.write(chunk)
        except Exception as e:
            print(color_msg("yellow", f"Failed to download {img_link}: {e}"))
        return
    
    async def get_chapters_left(self, comic_dirpath: str, chapters: list[str]) -> list[str]:
        existing_files = os.listdir(comic_dirpath)
        existing_chapters = set()

        pattern = r"chapter-(.+?)-p\d+"
        for file in existing_files:
            match = re.search(pattern, file)
            if match:
                existing_chapters.add(match.group(1))

        chapters_left = [
            re.sub(r"-+", "-", str(chapter).strip().replace(" ", "-"))
            for chapter in chapters
            if str(chapter).strip() not in existing_chapters
        ]

        # print(f'get_chapters_left: chapters_left: {chapters_left}')

        def sort_key(chapter: str):
            # 14x5 -> sort as 14.5, but keep original "14x5"
            normalized = chapter.replace("x", ".").replace("-", ".")

            match = re.match(r"^(\d+(?:\.\d+)?)", normalized)
            if match:
                return float(match.group(1))

            return float("inf")

        return sorted(chapters_left, key=sort_key)
    
    def handle_srcset(self, element) -> str:
        srcset = element.get("srcset", "")
        cover_img_link = ""
        if srcset:
            cover_img_link = self.extract_url_from_srcset(srcset)
        
        if not cover_img_link:
            src = element.get("src", "")
            if src.startswith('/_next/image'):
                parsed = urllib.parse.urlparse(src)
                query_params = urllib.parse.parse_qs(parsed.query)
                if 'url' in query_params:
                    cover_img_link = urllib.parse.unquote(query_params['url'][0])
            else:
                cover_img_link = src
        return cover_img_link
    
    def extract_url_from_srcset(self, link: str):
        if link.startswith('/_next/image'):
            parsed = urllib.parse.urlparse(link)
            query_params = urllib.parse.parse_qs(parsed.query)
            if 'url' in query_params:
                return urllib.parse.unquote(query_params['url'][0])
            
    async def batch_process(self, links_list: list[str], temp_dirpath: str, chapter_number: str, comic_dirpath: str):
        img_paths = await self.batch_download(links_list, temp_dirpath, chapter_number)
        if len(img_paths) == 1:
            await self.split_image(img_paths, temp_dirpath, comic_dirpath, chapter_number)
        else:
            await self.stitch_images(img_paths, temp_dirpath, comic_dirpath, chapter_number)
        await reset_dir(temp_dirpath)

    async def batch_download(self, links_list: list[str], temp_dirpath: str, chapter_number: str):
        img_paths: list[str] = []
        download_tasks = []
        
        for idx, url in enumerate(links_list, 1):
            extension: str = self.get_extension(url)
            safer_chapter_number = chapter_number.replace('.', '-')
            chapter_filename = f"chapter-{safer_chapter_number}-f{idx}{extension}" # f for fragment
            img_paths.append(os.path.join(temp_dirpath, chapter_filename))
            download_tasks.append((url, os.path.join(temp_dirpath, chapter_filename)))
        
        semaphore = asyncio.Semaphore(10)
        
        async def download_with_semaphore(url, output_path):
            async with semaphore:
                await self.download_single_image(url, output_path)
        
        tasks = [download_with_semaphore(url, path) for url, path in download_tasks]
        
        for future in asyncio.as_completed(tasks):
            await future
        
        return img_paths

    def extract_fragment_number(self, path: str) -> int:
        filename = os.path.basename(path)
        match = re.search(r"f(\d+)\.", filename)
        return int(match.group(1)) if match else 0

    def get_image_object(self, path: str) -> Image:
        return Image.open(path)
    
    async def stitch_images(self, img_paths: list[str], temp_dirpath: str, comic_dirpath: str, chapter_number: str):
        os.makedirs(comic_dirpath, exist_ok=True)
        # # self.dev_tag(f'running stitch images\nlen img_paths: {len(img_paths)}: {img_paths}, chapter_number: {chapter_number}')
        
        img_paths.sort(key=self.extract_fragment_number)
        
        valid_img_paths = []
        for img_path in img_paths:
            try:
                # Test if image can be opened
                with Image.open(img_path) as test_img:
                    test_img.verify()
                valid_img_paths.append(img_path)
            except (IOError, OSError, SyntaxError, Image.UnidentifiedImageError, Exception) as e:
                print(color_msg("yellow", f"Skipping corrupted image: {img_path} - {e}"))
                continue
        
        if not valid_img_paths:
            print(color_msg("red", f"No valid images found for chapter {chapter_number}"))
            return
        
        image_dimensions = []
        for img_path in valid_img_paths:
            try:
                with Image.open(img_path) as img:
                    width, height = img.size
                    image_dimensions.append((width, height))
            except Exception as e:
                print(color_msg("yellow", f"Could not get dimensions for {img_path}: {e}"))
                continue
        
        min_width = min(width for width, height in image_dimensions)
        # print(f"Minimum width among all fragments: {min_width}px")
        
        MAX_HEIGHT = 65500
        page_groups = []
        current_group = []
        current_height = 0
        
        for img_path in valid_img_paths:
            with Image.open(img_path) as img:
                width, height = img.size
                if width <= 0 or height <= 0:
                    print(color_msg("yellow", f"Skipping image with invalid dimensions: {img_path} ({width}x{height})"))
                    continue
                
                if current_height + height > MAX_HEIGHT and current_group:
                    page_groups.append(current_group)
                    current_group = [img_path]
                    current_height = height
                else:
                    current_group.append(img_path)
                    current_height += height
        
        if current_group:
            page_groups.append(current_group)
        
        # print(f"Grouped {len(img_paths)} fragments into {len(page_groups)} pages")
        
        stitched_paths = []
        for chunk_idx, group in enumerate(page_groups, 1):
            if not group:
                continue
                
            images = []
            original_images = []
            
            for img_path in group:
                img = Image.open(img_path)
                original_images.append(img)
                
                width, height = img.size
                if width < 1 or height < 1:
                    await self.notify_error(f'Downloader.stitch_images():\n > width/height is less than 1. width: {width}, height: {height}, img_path: {img_path}')
                
                if width > min_width:
                    ratio = min_width / width
                    new_height = int(height * ratio)
                    resized_img = img.resize((min_width, new_height), Image.Resampling.LANCZOS)
                    images.append(resized_img)
                    # print(f"Resized {os.path.basename(img_path)} from {width}x{height} to {min_width}x{new_height}")
                else:
                    images.append(img.copy())
            
            widths, heights = zip(*(img.size for img in images))
            total_height = sum(heights)
            max_width = max(widths) # should be min_width
            
            new_img = Image.new('RGB', (max_width, total_height), color='white')
            
            y_offset = 0
            for img in images:
                new_img.paste(img, (0, y_offset))
                y_offset += img.size[1]
            
            stitch_ext = ".jpg"
            
            safer_chapter_number = chapter_number.replace('.', '-')
            stitched_filename = f"chapter-{safer_chapter_number}-p{chunk_idx}{stitch_ext}"
            stitched_filepath = os.path.join(comic_dirpath, stitched_filename)
            
            new_img.save(stitched_filepath, quality=95, optimize=True)
            
            stitched_paths.append(stitched_filepath)
            
            for img in images:
                if hasattr(img, 'close'):
                    img.close()
            
            for img in original_images:
                img.close()
            
            # print(f"Created page {chunk_idx}: {stitched_filename} ({len(group)} fragments, {total_height}px height)")
        
        # print(f"Stitched {len(stitched_paths)} pages to {comic_dirpath}")

    async def split_image(self, img_paths: list[str], temp_dirpath: str, comic_dirpath: str, chapter_number: str):
        os.makedirs(comic_dirpath, exist_ok=True)
        img_filepath: str = img_paths[0]
        img_filename: str = img_filepath.split("/")[-1]
        max_height: int = 65500
        img_object: Image = self.get_image_object(img_filepath)
        img_w, img_h = img_object.size
        img_mode = img_object.mode

        if img_object.mode == 'P':
            img_object = img_object.convert('RGB')
        elif img_mode == "RGBA":
            background = Image.new('RGB', img_object.size, (255, 255, 255))
            background.paste(img_object, mask=img_object.split()[-1])
            img_object = background
        elif img_mode not in ("RGB", "L"):
            img_object = img_object.convert("RGB")

        if img_h < max_height:
            part_filename = re.sub(r'f(\d+)\.', r'p\1.', img_filename)
            new_img_filepath = os.path.join(comic_dirpath, part_filename)

            img_object.save(new_img_filepath)
            img_object.close()
            return

        def get_filename_chnum(filename: str) -> tuple[int, int]:
            chapter_pattern = re.compile(r"^chapter\-(\d+)\-f\d+\.(jpg|png|webp|jpeg|gif)$")
            match = re.search(chapter_pattern, filename)
            if match:
                chapter_number = match.group(1)
                extension = match.group(2)
                return chapter_number, extension

        img_filename_attrs = get_filename_chnum(filename=img_filename)
        chapter_number: int = img_filename_attrs[0]
        filename_ext: str = img_filename_attrs[1]
        num_chunks: int = math.ceil(img_h / max_height)
        chunk_height: int = math.ceil(img_h / num_chunks)

        chunk_paths = []
        os.remove(img_filepath)
        for idx in range(num_chunks):
            top_coord = idx * chunk_height
            bot_coord = min((idx + 1) * chunk_height, img_h)
            cropped_img = img_object.crop((0, top_coord, img_w, bot_coord))
            chunk_filename = f'chapter-{chapter_number}-p{idx+1}.{filename_ext}'
            chunk_filepath = os.path.join(comic_dirpath, chunk_filename)
            cropped_img.save(chunk_filepath)
            chunk_paths.append(filename_ext)
        
        img_object.close()
        return

    def is_cloudflare_blocked(self, response: httpx.Response) -> bool:
        """Check if response indicates Cloudflare blocking/challenge"""
        if response is None:
            return False
        
        if response.status_code in [403, 503, 429]:
            if 'cf-ray' in response.headers or 'cf-cache-status' in response.headers:
                return True
            
            if 'text/html' in response.headers.get('content-type', ''):
                content = response.text.lower()
                cloudflare_patterns = [
                    'cloudflare',
                    'checking your browser',
                    'cf-browser-verification',
                    'cf-challenge',
                    'attention: required',
                    'ddos protection',
                    'ray id:',
                    'cf-duid'
                ]
                return any(pattern in content for pattern in cloudflare_patterns)
        return False

    async def process_cover_image(self, link: str):
        is_valid_cover: bool = await self.validate_image_link(link)
        if not is_valid_cover:
            await self.notify_error(color_msg("yellow", f"Downloader.process_cover_image():\n > Comic cover image link is not valid.\n > Link: {link}"))
        
        cover_img_filename: str = self.get_cover_img_fname(self.comic_name, link)
        cover_img_filepath: str = os.path.join(self.cover_images_dirpath, cover_img_filename)
        if cover_img_filename not in self.cover_images:
            await self.download_single_image(link, cover_img_filepath)
        return
    
    async def validate_with_playwright(self, page, chapter_url, img_url: str) -> bool:
        try:
            response = await page.request.get(
                img_url,
                headers={
                    "referer": chapter_url,
                    "user-agent": await page.evaluate("navigator.userAgent"),
                },
                timeout=30000,
            )
            content_type = response.headers.get("content-type", "").lower()
            # print(
            #     f"[PW VALIDATE] {response.status} "
            #     f"{content_type} "
            #     f"{img_url}"
            # )

            return response.ok and content_type.startswith("image/")

        except Exception as e:
            print(f"[PW VALIDATE FAILED] {img_url} - {type(e).__name__}: {e}")
            return False
        
    async def get_images_playwright_scroll(self, chapter_url: str, regex_filter: str, link_filter: str, img_element_filter: str, file_ext: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-dev-shm-usage', '--no-sandbox'],
            )

            page = await browser.new_page()
            page.set_default_timeout(30000)

            network_images = []
            seen = set()
            compiled_regex = re.compile(regex_filter)

            def clean_url(url: str): return url.split("?")[0]

            def add_image(url: str):
                clean = clean_url(url)
                filename = clean.split("/")[-1]

                if link_filter and link_filter not in clean:
                    return

                if file_ext and not clean.endswith(file_ext):
                    return

                if regex_filter and not compiled_regex.match(filename):
                    return

                if clean not in seen:
                    seen.add(clean)
                    network_images.append(clean)

            def handle_response(response): add_image(response.url)
                
            def handle_request(request):
                if request.resource_type == "image":
                    add_image(request.url)

            page.on("response", handle_response)
            page.on("request", handle_request)

            try:
                await page.goto(chapter_url, wait_until="networkidle", timeout=60000)
            except PlaywrightTimeoutError:
                await page.goto(chapter_url, wait_until="domcontentloaded", timeout=60000)

            await page.wait_for_timeout(3000)

            last_height = 0
            stable_rounds = 0

            while stable_rounds < 3:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)

                height = await page.evaluate("document.body.scrollHeight")

                if height == last_height:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                    last_height = height

            img_elements = await page.query_selector_all(
                f'img[src*="{img_element_filter}"], img[data-src*="{img_element_filter}"], img[data-lazy-src*="{img_element_filter}"]'
            )

            for img in img_elements:
                for attr in ["src", "data-src", "data-lazy-src"]:
                    src = await img.get_attribute(attr)
                    if src:
                        add_image(src)

            def get_page_num(url):
                filename = url.split("/")[-1]
                match = re.search(r'^(\d+)', filename)
                if match:
                    return int(match.group(1))
                return 999999

            network_images.sort(key=get_page_num)

            valid_images = []
            for img in network_images:
                if await self.validate_with_playwright(page, chapter_url, img):
                    valid_images.append(img)

            await browser.close()

        return valid_images

    async def download_single_image_playwright(self, page, chapter_url: str, img_link: str, img_output_path: str) -> None:
        try:
            response = await page.request.get(
                img_link,
                headers={
                    "referer": chapter_url,
                    "user-agent": await page.evaluate("navigator.userAgent"),
                },
                timeout=30000,
            )

            if not response.ok:
                print(f"Failed to download {img_link}: {response.status}")
                return

            content_type = response.headers.get("content-type", "").lower()
            if not content_type.startswith("image/"):
                print(f"Not an image: {img_link} ({content_type})")
                return

            async with aiofiles.open(img_output_path, "wb") as file:
                await file.write(await response.body())

        except Exception as e:
            print(f"Failed to download {img_link}: {type(e).__name__}: {e}")
            
    async def get_valid_image_links(self, tag_list: list[str], domain_name: str, src_value: str, comic_name: str, chapter_num: int,extra_attribute: str=None):
        # self.dev_tag(f'Downloader.get_valid_image_links()\ntag_list: {tag_list}\ndomain_name: {domain_name}\nsrc_value: {src_value}\ncomic_name: {comic_name}\nchapter_num: {chapter_num}\nextra_attribute: {extra_attribute}')
        valid_links: int = 0
        valid_links_list: list[str] = []
        for img_tag in tag_list:
            img_link = None
            if domain_name == "manga18.me":
                if img_tag.has_attr("alt") and img_tag["alt"].startswith(extra_attribute) and img_tag.has_attr("src"):
                    img_link = img_tag.get("src").strip()
                elif img_tag.has_attr("src") and "manga18.me/uploads" in img_tag["src"]:
                    img_link = img_tag.get("src").strip()

            elif domain_name == "hentai20":
                if extra_attribute == "kinkfolder-zip": extra_attribute = "kinkfolderzip"
                if img_tag.has_attr("src") and extra_attribute in img_tag.get("src"):
                    img_link = img_tag.get("src").strip()
            
            elif domain_name == "asuracomics":
                img_href: str = img_tag.get("href").strip()
                img_link: str = f"https://asurascans.com{img_href}"

            else:
                img_link: str = img_tag.get(src_value).strip()
            
            if img_link and not img_link.startswith("https://"): continue

            is_valid: bool = await self.validate_image_link(img_link)
            if is_valid:
                valid_links += 1
                valid_links_list.append(img_link)

        if len(valid_links_list) == len(tag_list) - 5:
            # self.dev_tag('one image is invalid, continuing')
            return valid_links_list
        else:
            # print(color_msg("lightgreen", f"Chapter Links Validated ({domain_name}): {valid_links}/{len(tag_list)}"))
            # await self.notify_message(f"({domain_name}) Downloading {comic_name} Ch {chapter_num}: {valid_links}/{len(tag_list)}")
            return valid_links_list

    async def batch_process_playwright(self, page, chapter_url: str, links_list: list[str], temp_dirpath: str, chapter_number: str, comic_dirpath: str):
        img_paths = []

        os.makedirs(temp_dirpath, exist_ok=True)

        for idx, url in enumerate(links_list, 1):
            extension = self.get_extension(url)
            safer_chapter_number = chapter_number.replace(".", "-")
            chapter_filename = f"chapter-{safer_chapter_number}-f{idx}{extension}"
            output_path = os.path.join(temp_dirpath, chapter_filename)

            await self.download_single_image_playwright(page, chapter_url, url, output_path)
            img_paths.append(output_path)

        if len(img_paths) == 1:
            await self.split_image(img_paths, temp_dirpath, comic_dirpath, chapter_number)
        else:
            await self.stitch_images(img_paths, temp_dirpath, comic_dirpath, chapter_number)

        await reset_dir(temp_dirpath)
    
    async def get_images_and_batch_process_playwright(self, chapter_url: str, regex_filter: str, link_filter: str, img_element_filter: str, file_ext: str, temp_dirpath: str, chapter_number: str, comic_dirpath: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--no-sandbox"],
            )

            page = await browser.new_page()
            page.set_default_timeout(30000)

            network_images = []
            seen = set()
            compiled_regex = re.compile(regex_filter)

            def clean_url(url: str): return url.split("?")[0]

            def add_image(url: str):
                clean = clean_url(url)
                filename = clean.split("/")[-1]

                if link_filter and link_filter not in clean:
                    return
                if file_ext and not clean.endswith(file_ext):
                    return
                if regex_filter and not compiled_regex.match(filename):
                    return
                if clean not in seen:
                    seen.add(clean)
                    network_images.append(clean)

            def handle_response(response): add_image(response.url)

            def handle_request(request):
                if request.resource_type == "image":
                    add_image(request.url)

            page.on("response", handle_response)
            page.on("request", handle_request)

            try:
                await page.goto(chapter_url, wait_until="networkidle", timeout=60000)
            except PlaywrightTimeoutError:
                await page.goto(chapter_url, wait_until="domcontentloaded", timeout=60000)

            await page.wait_for_timeout(3000)

            last_height = 0
            stable_rounds = 0

            while stable_rounds < 3:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)

                height = await page.evaluate("document.body.scrollHeight")

                if height == last_height:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                    last_height = height

            img_elements = await page.query_selector_all(
                f'img[src*="{img_element_filter}"], img[data-src*="{img_element_filter}"], img[data-lazy-src*="{img_element_filter}"]'
            )

            for img in img_elements:
                for attr in ["src", "data-src", "data-lazy-src"]:
                    src = await img.get_attribute(attr)
                    if src:
                        add_image(src)

            def get_page_num(url):
                filename = url.split("/")[-1]
                match = re.search(r"mr_(\d+)", filename)
                if match:
                    return int(match.group(1))
                match = re.search(r"^(\d+)", filename)
                if match:
                    return int(match.group(1))
                return 999999

            network_images.sort(key=get_page_num)

            valid_images = []
            for img in network_images:
                if await self.validate_with_playwright(page, chapter_url, img):
                    valid_images.append(img)

            if not valid_images:
                await browser.close()
                return False

            await self.batch_process_playwright(page, chapter_url, valid_images, temp_dirpath, chapter_number, comic_dirpath)

            await browser.close()
            return True
        
    async def get_dynamic_soup(self, url: str, selector: str, domain: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector(selector, timeout=30000)
            except Exception as e:
                self.dev_tag(color_msg("yellow", f"wait_for_selector('{selector}') timed out, falling back to waiting for images..."))
            
            if domain == "hentai20":
                try:
                    await page.wait_for_function(
                        """() => {
                            const images = document.querySelectorAll('img.ts-main-image');
                            return images.length > 0;
                        }""",
                        timeout=30000
                    )
                except Exception as img_error:
                    print(color_msg("red", f"Also failed to find images: {img_error}"))
            content = await page.content()
            await browser.close()
            return BeautifulSoup(content, 'html.parser')

    async def get_pwsoup_buttons(self, comic_url: str, domain_name=None):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(comic_url, wait_until="networkidle", timeout=5000)
            except PlaywrightTimeoutError:
                print("networkidle failed, retrying once...")
                try:
                    await page.goto(comic_url, wait_until="networkidle", timeout=5000)
                except PlaywrightTimeoutError:
                    print("networkidle failed again, falling back to domcontentloaded...")
                    await page.goto(comic_url, wait_until="domcontentloaded", timeout=5000)

            while True:
                if domain_name == "manhwaread":
                    show_more_btn = page.locator("chapterListToggleBtn")
                else:
                    show_more_btn = page.get_by_role("button", name="Show more")
                if await show_more_btn.count() == 0: break
                await show_more_btn.first.click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(500)
            html = await page.content()
            await browser.close()
            return BeautifulSoup(html, 'html.parser')
    
    async def get_soup_images_from_wrapper_after_scroll(self, chapter_url: str, wrapper_selector: str, not_in_src_word: str) -> list[str]:
        headless: bool = True
        timeout: int = 30000
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless, args=["--disable-dev-shm-usage", "--no-sandbox"])
            page = await browser.new_page()
            page.set_default_timeout(30000)

            try:
                await page.goto(chapter_url, wait_until="networkidle", timeout=timeout)
            except PlaywrightTimeoutError:
                await page.goto(chapter_url, wait_until="domcontentloaded", timeout=timeout)

            await page.wait_for_selector(wrapper_selector, timeout=timeout)
            await page.wait_for_timeout(3000)

            for i in range(5):
                await page.evaluate(f"window.scrollTo(0, {i * 800})")
                await page.wait_for_timeout(1500)

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

            await page.wait_for_function(
                """({wrapperSelector, notInSrcWord}) => {
                    const wrapper = document.querySelector(wrapperSelector);
                    if (!wrapper) return false;
                    const imgs = [...wrapper.querySelectorAll("img")];
                    if (!imgs.length) return false;
                    return imgs.every(img => {
                        const src = img.getAttribute("src");
                        return src && !src.includes(notInSrcWord);
                    });
                }""",
                arg={"wrapperSelector": wrapper_selector, "notInSrcWord": not_in_src_word},
                timeout=timeout,
            )

            src_links = await page.eval_on_selector_all(
                f"{wrapper_selector} img",
                "imgs => imgs.map(img => img.getAttribute('src')).filter(Boolean)"
            )

            await browser.close()
            return list(dict.fromkeys(src_links))
    
    def get_style_url(self, tag) -> Optional[str]:
        style = tag.get("style", "")
        if style == "": return None
        url = re.search(r"--photoURL:url\((.*?)\)", style).group(1)
        return url

