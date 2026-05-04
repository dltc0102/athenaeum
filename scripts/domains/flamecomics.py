from bs4 import BeautifulSoup
from typing import Optional
from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase

class FlameComics(DomainBase):
    domain_key = "flamecomics"
    def __init__(self, given_config: list[str], comic_name: str, comic_id: int, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.comic_name: str = comic_name
        self.given_config: list[str] = given_config
        self.comic_id: int = comic_id
        self.chapter_links_list = []

        self.protocol: str = "https://flamecomics.xyz"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "flamecomics")
        self.comic_url: str = f"{self.protocol}/series/{self.comic_id}"
        
        self.panel_tag(f'{color_msg('yellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('yellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
    
    def get_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.select_one(
            "div.SeriesPage_paper__MMnBx.m_1b7284a3.mantine-Paper-root[style]"
        ).find("h1", class_="m_8a5d1357 mantine-Title-root").text.strip()

    def get_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        return self.handle_srcset(soup.find("img", class_="SeriesPage_cover__cEjW-"))

    def get_details_comic_status(self, soup: BeautifulSoup) -> str:
        return soup.select_one(
            "div.SeriesPage_paper__MMnBx.m_1b7284a3.mantine-Paper-root[style]"
        ).find("span", class_="m_5add502a mantine-Badge-label").get_text(strip=True).lower()

    def get_details_chapter_links_list(self, soup: BeautifulSoup) -> list[str]:
        return list(reversed([
            f"{self.protocol}{tag.get("href").strip()}" 
            for tag in soup.select_one("div.SeriesPage_paper__MMnBx.m_1b7284a3.mantine-Paper-root:not([style])").find_all("a", class_="ChapterCard_chapterWrapper__NIPp5 mantine-focus-auto")
        ]))
    
    def get_details_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        return list(reversed([
            tag.find("p", class_="mantine-focus-auto m_b6d8b162 mantine-Text-root").get_text(strip=True).lower().replace("chapter", "").strip() 
            for tag in soup.find("div", class_="m_c0783ff9 mantine-ScrollArea-viewport").find_all("a", class_="ChapterCard_chapterWrapper__NIPp5 mantine-focus-auto")
        ]))
            
    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            await self.notify_error(f"Flamecomics.get_comic_details():\n > Failed to fetch this comic page: {self.comic_url}")
        
        comic_soup_name: str = self.get_details_soup_name(comic_soup)
        comic_cover_img_link: str = self.get_details_cover_img_link(comic_soup)
        await self.process_cover_image(comic_cover_img_link)
        comic_status: str = self.get_details_comic_status(comic_soup)
        chapter_links_list: list[str] = self.get_details_chapter_links_list(comic_soup)
        chapters_list: list[str] = self.get_details_chapters_list(comic_soup)
        first_chapter, *_, latest_chapter = chapters_list

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_link_list': chapter_links_list,
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter
        }

    async def get_chapter_image_links(self, ch_num: int, chapter_url: str) -> list[str]:
        chapter_soup: Optional[BeautifulSoup] = await self.get_soup(chapter_url)
        chapter_image_tags = [
            tag for tag in chapter_soup.find_all("img")
            if tag and tag.has_attr("src") and tag["src"].startswith("https://cdn.flamecomics.xyz/uploads/images/series")
        ]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="flamecomics", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)

