import requests
from bs4 import BeautifulSoup
from typing import Optional
from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase

class AsuraComics(DomainBase):
    domain_key = "asuracomics"

    def __init__(self, given_config: list[str], comic_name: str, series_url: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.given_config: list[str] = given_config
        self.generated_config: list[str] = []
        self.comic_name: str = comic_name
        self.protocol: str = "https://asurascans.com/"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "asuracomics")
        self.series_url = series_url
        self.comic_url = None

    async def initialize(self):
        if self.series_url == "":
            self.comic_search_result: list[str] = await self.search_asura(self.comic_name)
            self.comic_name = self.comic_search_result[0]
            self.comic_url = self.comic_search_result[1]
        else:
            self.comic_url = self.series_url

        await super().initialize()

    def get_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.find("h1", class_="text-xl lg:text-[32px] font-semibold leading-tight").get_text(strip=True)

    def get_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="rounded-xl z-0 w-full h-full absolute top-0 left-0").find("img").get("src").strip()

    def get_details_comic_status(self, soup: BeautifulSoup) -> str:
        return soup.find("span", class_="text-base font-bold text-[#A78BFA] capitalize").get_text(strip=True).lower().strip()

    def get_details_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        chapter_wrapper = soup.find("div", class_="max-h-[500px] overflow-y-auto")
        premium_chapter: str = chapter_wrapper.find("div", class_="flex items-center gap-3 min-w-0 flex-1").find("span", class_="font-medium transition-colors text-white group-hover:text-[#913FE2]").get_text().lower().replace("chapter", "").strip()
        non_premium_chapters = list(reversed([
            tag.find("span", class_="font-medium transition-colors text-white group-hover:text-[#913FE2]").get_text(strip=True).lower().replace("chapter", "").strip() 
            for tag in chapter_wrapper.find("div", class_="divide-y divide-white/5").find_all("a", class_="group flex items-center justify-between px-4 py-4 transition-colors hover:bg-white/5")
        ]))
        chapters_list = [ch for ch in non_premium_chapters if ch != premium_chapter]
        return chapters_list

    async def get_comic_details(self) -> dict:
        self.comic_uid: str = self.extract_comic_uid_asura(self.series_url)
        self.comic_template_url: str = f"{self.comic_url}/chapter/{{}}/"

        self.panel_tag(f"{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}")
        self.panel_tag(f"{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}")
        self.panel_tag(f"{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}")

        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            await self.notify_error(f"Asuracomics.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
        
        comic_soup_name: str = self.get_details_soup_name(comic_soup)
        comic_cover_img_link: str = self.get_details_cover_img_link(comic_soup)
        await self.process_cover_image(comic_cover_img_link)
        comic_status: str = self.get_details_comic_status(comic_soup)
        chapters_list = self.get_details_chapters_list(comic_soup)
        first_chapter, *_, latest_chapter = chapters_list

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter,
        }

    def has_unicode(self, giv_str: str) -> bool:
        return True if "\u2019" in giv_str or "\u2026" in giv_str else False

    def find_query_part(self, query: str) -> str:
        query_parts = query.split(' ')
        len_parts = len(query_parts)
        unicode_idx = -1
        for idx, part in enumerate(query_parts, 0):
            if self.has_unicode(part):
                unicode_idx = idx

        if unicode_idx > -1:
            if unicode_idx == 0:
                return '%20'.join(query_parts[1:])
            elif unicode_idx == len_parts:
                return '%20'.join(query_parts[:-1])
            else:
                before_unicode = query_parts[:unicode_idx]
                after_unicode = query_parts[unicode_idx+1:]
                if len(before_unicode) > len(after_unicode):
                    return '%20'.join(before_unicode)
                else:
                    return '%20'.join(after_unicode)

    async def search_asura(self, query_comic_name: str) -> dict: 
        lowered_query = query_comic_name.lower().strip()
        clean_query = query_comic_name.replace("'", "\u2019")
        domain_protocol: str = "https://asurascans.com"
        search_protocol: str = "https://asurascans.com/browse?search={}"
        has_unicode_element: bool = self.has_unicode(clean_query)
        self.dev_tag(f'has_unicode_element: {has_unicode_element}')
        search_query = query_comic_name.replace(" ", "%20")
        if has_unicode_element:
            search_query = self.find_query_part(clean_query)

        search_url = search_protocol.format(search_query.lower().strip())
        search_results_soup = await self.get_soup(search_url)
        results_wrapper = search_results_soup.find("div", id="series-grid-container")
        first_result = results_wrapper.find("div", class_="series-card group bg-[#1f1a2e] rounded-lg overflow-hidden transition-all duration-200 hover:ring-2 hover:ring-[#913FE2] hover:shadow-lg hover:shadow-[#913FE2]/20")

        comic_title: str = first_result.find("h3", class_="text-sm font-semibold text-white line-clamp-1 group-hover:text-[#913FE2] transition-colors").get_text(strip=True)
        comic_series_link: str = f"{self.protocol}{first_result.find('a', class_='block relative aspect-[3/4] overflow-hidden').get('href').strip()}"
        return [comic_title, comic_series_link]

    def extract_comic_uid_asura(self, link: str) -> str:
        last_part_of_link = link.split("/")[-1]
        link_uid = last_part_of_link.split("-")[-1]
        return link_uid

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)

        img_links = await self.get_images_playwright_scroll(
            chapter_url=comic_chapter_url,
            regex_filter=r'^(0{2,5}|0\d\d|00\d|0\d{1,4}|\d{2,5}|0\d|\d{2}|[A-Za-z0-9]{6})\.webp$',
            link_filter="/chapters/",
            img_element_filter="cdn.asurascans.com",
            file_ext=".webp"
        )
        return img_links