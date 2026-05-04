from bs4 import BeautifulSoup
from typing import Optional
from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase

class Mgeko(DomainBase):
    domain_key = "mgeko"
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.comic_name: str = comic_name
        self.given_config: list[str] = given_config

        self.protocol: str = "https://www.mgeko.cc"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "mgeko")
        self.comic_url: str = f"https://www.mgeko.cc/manga/{self.url_comic_name}/"
        self.comic_template_url: str = f"https://www.mgeko.cc/reader/en/{self.url_comic_name}-chapter-{{}}-eng-li/"

        self.backup_template_url: str = ""
        if self.url_comic_name == "leviathan":
            self.comic_url: str = f"https://www.mgeko.cc/manga/leviathansdads/"
            self.backup_template_url: str = f"https://www.mgeko.cc/reader/en/leviathansdads-chapter-{{}}-eng-li"
            
        self.comic_all_chaps_url: str = f"{self.comic_url}all-chapters/"
        self.panel_tag(f'{color_msg('yellow', 'self.comic_all_chaps_url:')} {color_msg('white', self.comic_all_chaps_url)}')
        self.panel_tag(f'{color_msg('yellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('yellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('yellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    def get_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.find("h1", class_="novel-title text2row").get_text(strip=True)

    def get_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="fixed-img").find("figure", class_="cover").select_one("img").get("data-src").strip()

    def get_details_comic_status(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="header-stats").find_all("span")[3].select_one("strong").get_text(strip=True).lower()

    def get_details_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        return list(reversed([
            tag.get_text(strip=True).split("-")[0].strip()
            for tag in soup.find("ul", class_="chapter-list").find_all("strong", class_="chapter-title")
        ]))
    
    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            await self.notify_error(f"Mgeko.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
        
        comic_soup_name: str = self.get_details_soup_name(comic_soup)
        comic_cover_img_link: str = self.get_details_cover_img_link(comic_soup)
        await self.process_cover_image(comic_cover_img_link)
        comic_status: str = self.get_details_comic_status(comic_soup)

        all_chapter_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_all_chaps_url)
        if all_chapter_soup is None:
            await self.notify_error(f"Mgeko.get_comic_details():\n > Failed to fetch all-chapters page: {self.comic_all_chaps_url}")

        chapters_list: list[str] = self.get_details_chapters_list(all_chapter_soup)
        first_chapter, *_, latest_chapter = chapters_list
        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter,
            'chapters_list': chapters_list,
        }

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        primary_url = self.comic_template_url.format(ch_num)
        backup_url = (
            self.backup_template_url.format(ch_num)
            if self.backup_template_url
            else None
        )

        chapter_soup: BeautifulSoup = await self.get_soup(primary_url)
        if not chapter_soup and backup_url:
            chapter_soup = await self.get_soup(backup_url)

        chapter_image_tags: list[str] = [
            tag for tag in chapter_soup.find("div", id="chapter-reader").find_all("img") 
            if tag.has_attr("id") and tag["id"].startswith("image-")
        ]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="mgeko", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)
