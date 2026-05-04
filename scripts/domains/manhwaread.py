import re
from bs4 import BeautifulSoup
from typing import Optional
from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase

class ManhwaRead(DomainBase):
    domain_key = "manhwaread"
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name

        self.protocol: str = "https://manhwaread.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "manhwaread")
        self.comic_url: str = f"{self.protocol}/manhwa/{self.url_comic_name}/"
        self.comic_template_url: str = f"{self.comic_url}chapter-{{}}/"

        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    def get_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="manga-titles grow").find("h1").get_text(strip=True)

    def get_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="flex justify-center sm:max-w-sm w-full xl:max-w-full").find("img").get("src").strip()

    def get_details_comic_status(self, soup: BeautifulSoup) -> str:
        return soup.find("span", class_="manga-status flex items-center gap-2").get("data-status").lower().strip()

    def get_details_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        return list(reversed([
            re.sub(
                r'-+', '-',
                tag.find("span", class_="text-gray-50 chapter-item__name").get_text().lower().replace("chapter", "").strip().replace(" ", "-"))
            for tag in soup.find("div", id="groupChapterList").find_all("a", class_="chapter-item")
        ]))

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_pwsoup_buttons(self.comic_url, domain_name="manhwaread")
    
        comic_soup_name: str = self.get_details_soup_name(comic_soup)
        comic_cover_img_link: str = self.get_details_cover_img_link(comic_soup)
        await self.process_cover_image(comic_cover_img_link)
        comic_status: str = self.get_details_comic_status(comic_soup)
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
        chapter_url = self.comic_template_url.foramt(ch_num)
        chapter_soup = await self.get_soup(chapter_url)
        pass