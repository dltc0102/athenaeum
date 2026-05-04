import os, re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urlparse

class PersistentPlaywright:
    def __init__(self, config: list[str, str]):
        self.extensions_dirpath = os.path.join(os.getcwd(), "extensions")
        self.path_to_anti_debug_extension = os.path.join(self.extensions_dirpath, "anti_anti_debug_chrome")
        self.path_to_user_data = os.path.join(self.extensions_dirpath, "profile")

    def _mangafire_page_num(self, url: str) -> int:
        filename = urlparse(url).path.split("/")[-1]
        match = re.search(r"(\d+)\.jpg$", filename)
        return int(match.group(1)) if match else 999999
    
    def _is_mangafire_page_image(self, url: str) -> bool:
        return (
            re.search(r"mfcdn\d\.xyz/mf", url) is not None
            and re.search(r"/\d+\.jpg(?:$|\?)", url) is not None
        )
    
    async def scroller_html(self, my_page, my_filter: str, increment_scroll=False, link_filter: str=None):
        expected_number_of_images = await my_page.evaluate('''(selector) => {
            return document.querySelectorAll(selector).length;
        }''', my_filter)

        if increment_scroll and link_filter:
            total_height = await my_page.evaluate('document.body.scrollHeight')

            for idx in range(0, total_height, 800):
                await my_page.evaluate(f'window.scrollTo(0, {idx})')
                await my_page.wait_for_timeout(1000)

            await my_page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await my_page.wait_for_timeout(3000)
            return
        else:
            for idx in range(expected_number_of_images):
                await my_page.evaluate('''(data) => {
                    const pageDivs = document.querySelectorAll(data.selector);
                    if (pageDivs[data.index]) {
                        pageDivs[data.index].scrollIntoView({behavior: 'smooth', block: 'center'});
                    }
                }''', {"selector": my_filter, "index": idx})
                await my_page.wait_for_timeout(500)
            await my_page.wait_for_timeout(2000)
            return
    
    async def run_persistence_for_soup(self, url: str, filter: str="", scroll=False, increment_scroll=False, link_filter: str=None) -> BeautifulSoup:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                self.path_to_user_data,
                channel="chromium",
                headless=True,
                args=[
                    f"--disable-extensions-except={self.path_to_anti_debug_extension}",
                    f"--load-extension={self.path_to_anti_debug_extension}",
                    "--no-sandbox",
                ],
            )
            
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(8000)
            
            if scroll: 
                if increment_scroll and link_filter:
                    await self.scroller_html(my_page=page, my_filter=filter, increment_scroll=increment_scroll, link_filter=link_filter)
                else:
                    await self.scroller_html(my_page=page, my_filter=filter)
            
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            await context.close()
            return soup

    async def get_mangafire_network_images(self, url: str) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()

        def add_url(raw_url: str):
            clean_url = raw_url.split("?")[0]

            if self._is_mangafire_page_image(clean_url) and clean_url not in seen:
                seen.add(clean_url)
                found.append(clean_url)

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                self.path_to_user_data,
                channel="chromium",
                headless=True,
                args=[
                    f"--disable-extensions-except={self.path_to_anti_debug_extension}",
                    f"--load-extension={self.path_to_anti_debug_extension}",
                    "--no-sandbox",
                ],
            )

            page = await context.new_page()

            page.on("request", lambda request: add_url(request.url))
            page.on("response", lambda response: add_url(response.url))

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(8000)

            last_height = 0
            stable_rounds = 0

            while stable_rounds < 4:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)

                height = await page.evaluate("document.body.scrollHeight")

                if height == last_height:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                    last_height = height

            await page.wait_for_timeout(3000)

            # Also inspect current DOM, just in case some URLs never appeared as image requests.
            dom_urls = await page.evaluate("""
                () => Array.from(document.images)
                    .map(img => img.currentSrc || img.src)
                    .filter(Boolean)
            """)

            for img_url in dom_urls:
                add_url(img_url)

            await context.close()

        return sorted(found, key=self._mangafire_page_num)
  
