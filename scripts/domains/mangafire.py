import re
from bs4 import BeautifulSoup
from typing import Optional
from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase
from scripts.utils.persistence import PersistentPlaywright
from scripts.utils.vrf_generator import VRFGenerator

class MangaFire(DomainBase):
    domain_key = "mangafire"
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name

        self.protocol: str = "https://mangafire.to"
        self.series_url: str = ""
        self.persistent_instance = PersistentPlaywright(given_config)
        self.comic_language: str = "en"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "mangafire")

        self.comic_uid = self.given_config[2]
        self.release_day = self.given_config[3]
        self.is_completed = self.given_config[4]

    async def get_comic_url(self):
        search_url_name: str = self.comic_name.lower().strip()
        search_url: str = VRFGenerator(search_url_name).get_search_url()
        search_soup = await self.persistent_instance.run_persistence_for_soup(url=search_url) 
        first_result = search_soup.find("div", class_="original card-lg").find("div", class_="inner")
        comic_url: str = self.protocol + first_result.find("a", class_="poster").get("href").strip()
        return comic_url

    def get_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="info").find("h1").get_text(strip=True)

    def get_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="poster").find("img", alt=self.given_config[0]).get("src").strip()

    def get_details_comic_status(self, soup: BeautifulSoup) -> str:
        txt = soup.find("div", class_="info").find("p").get_text(strip=True).lower()
        if txt == "releasing":
            return "ongoing"
        else:
            return "completed"
    
    def get_details_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        return list(reversed([
            tag.find("span").get_text(strip=True).lower().split(": ")[0].replace("chapter", "").strip()
            for tag in soup.find("ul", class_="scroll-sm").find_all("a")
        ]))
    
    async def get_comic_details(self) -> dict:
        self.comic_url: str = await self.get_comic_url()
        self.comic_template_url: str = f"{self.comic_url.replace("/manga/", "/read/")}/{self.comic_language}/chapter-{{}}"

        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

        comic_soup: Optional[BeautifulSoup] = await self.persistent_instance.run_persistence_for_soup(self.comic_url)
        details_wrapper = comic_soup.find("div", class_="main-inner")

        comic_soup_name: str = self.get_details_soup_name(details_wrapper)
        comic_cover_img_link: str = self.get_details_cover_img_link(details_wrapper)
        await self.process_cover_image(comic_cover_img_link)
        comic_status: str = self.get_details_comic_status(details_wrapper)
        chapters_list: list[str] = self.get_details_chapters_list(comic_soup)
        first_chapter, *_, latest_chapter = chapters_list

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter
        }

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        chapter_soup: BeautifulSoup = await self.persistent_instance.run_persistence_for_soup(comic_chapter_url, filter="div.page.fit-w", scroll=True)
        url_pattern = r"mfcdn\d\.xyz\/mf"
        chapter_image_tags = [
            tag for tag in chapter_soup.select('div.img.loaded img.fit-w') 
            if tag.has_attr("src") and re.search(url_pattern, tag["src"])
        ]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="mangafire", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)
