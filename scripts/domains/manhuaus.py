from bs4 import BeautifulSoup
from typing import Optional
from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase

class Manhuaus(DomainBase):
    domain_key = "manhuaus"
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.comic_name: str = comic_name
        self.given_config: list[str] = given_config

        self.protocol: str = "https://manhuaus.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "manhuaus")
        self.comic_url: str = f"https://manhuaus.com/manga/{self.url_comic_name}/"
        self.comic_template_url: str = f"https://manhuaus.com/manga/{self.url_comic_name}/chapter-{{}}/"
        
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    def get_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="post-title").select_one("h1").text.strip()

    def get_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="summary_image").select_one("img").get("data-src").strip()

    def get_details_comic_status(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="post-status").find("div", class_="summary-content").get_text(strip=True).lower()

    def get_details_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        return list(reversed([
            tag.find("a").get_text().lower().replace("chapter", "").strip()
            for tag in soup.find_all("li", class_="wp-manga-chapter")
        ]))

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            await self.notify_error(f"Manhuaus.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")

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
            'latest_chapter': latest_chapter,
        }

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        chapter_image_tags: list[str] = [
            tag for tag in chapter_soup.find("div", class_="reading-content").find_all("img") 
            if tag.has_attr("id") and tag["id"].startswith("image-")
        ]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="yakshascans", src_value="data-src", comic_name=self.comic_soup_name, chapter_num=ch_num)

