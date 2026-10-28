from bs4 import BeautifulSoup
from urllib.parse import quote
from typing import Optional
from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase

class Kagane(DomainBase):
    domain_key = "kagane"
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name

        self.protocol: str = "https://kagane.org"
        self.search_query: str = self.get_search_query()
        self.search_protocol: str = f"{self.protocol}/search?q={self.search_query}"

        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, domain_name="kagane")

    def get_search_query(self) -> str:
        return quote(self.comic_name.lower()).strip()
    
    async def search_comic_for_uid(self) -> str:
        search_soup: Optional[BeautifulSoup] = await self.get_soup(self.search_protocol)
        comic_uid: str = [
            tag.get("href").split("/")[-1]
            for tag in search_soup.find("div", class_="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-7 xl:grid-cols-8 gap-3 sm:gap-4").find_all("a", class_="absolute inset-0 z-10")
        ][0]
        return comic_uid

    def get_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.find("h1", class_="text-2xl md:text-3xl lg:text-4xl font-bold text-foreground leading-tight hover:text-primary transition-colors").get_text(strip=True)
    
    def get_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        return soup.find("img", class_="absolute inset-0 w-full h-full object-cover transition-transform group-hover:scale-105").get("src").strip()

    def get_details_comic_status(self, soup: BeautifulSoup) -> str:
        comic_tags: list[str] = [
            tag.get_text(strip=True).lower()
            for tag in soup.find("div", class_="flex flex-wrap items-center gap-2").find_all("span")
        ]
        if "ongoing" in comic_tags:
            return "ongoing"
        else:
            return "completed"

    def get_details_chapters_link_list(self, soup: BeautifulSoup) -> list[str]:
        return list(reversed([
            tag
            for tag in soup
        ]))
    def get_details_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        return list(reversed([
            tag
            for tag in soup
        ]))
    
    async def get_comic_details(self) -> dict:
        self.comic_uid: str = await self.search_comic_for_uid()
        self.comic_url: str = f"{self.protocol}/series/{self.comic_uid}"

        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')

        comic_soup: Optional[BeautifulSoup] = await self.get_pwsoup_buttons(self.comic_url, domain_name="kagane")

        comic_soup_name: str = self.get_details_soup_name(comic_soup)
        comic_cover_img_link: str = self.get_details_cover_img_link(comic_soup)
        await self.process_cover_image(comic_cover_img_link)
        comic_status: str = self.get_details_comic_status(comic_soup)

        chapter_wrapper = comic_soup.find("div", class_="grid gap-2")
        chapters_link_list: list[str] = self.get_details_chapters_link_list(chapter_wrapper)
        chapters_list: list[str] = self.get_details_chapters_list(chapter_wrapper)
        first_chapter, *_, latest_chapter = chapters_list

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_link_list': chapters_link_list,
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter
        }
    
    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        chapter_url = self.comic_template_url.format(ch_num)
        chapter_soup = await self.get_soup(chapter_url)
        chapter_image_tags = []
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="mangabuddy", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)
