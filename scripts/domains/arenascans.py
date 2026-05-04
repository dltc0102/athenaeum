from bs4 import BeautifulSoup
from typing import Optional
from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase

class ArenaScans(DomainBase):
    domain_key = "arenascans"
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name

        self.protocol: str = "https://arenascan.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "arenascans")
        self.comic_url: str = f"{self.protocol}/manga/{self.url_comic_name}/"
        self.comic_template_url: str = f"{self.protocol}/{self.url_comic_name}-{{}}/"
        self.backup_template_url: str = f"{self.protocol}/{self.url_comic_name}-chapter-{{}}"

        self.comic_uid = self.given_config[2]
        self.release_day = self.given_config[3]
        self.is_completed = self.given_config[4]

        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    def get_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.find("h1", class_="entry-title").get_text(strip=True)

    def get_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        return soup.find("img", class_="attachment- size- wp-post-image").get("src").strip()

    def get_details_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        return list(reversed([
            tag.get_text(strip=True).lower().replace("chapter", "").strip() 
            for tag in soup.find("div", id="chapterlist").find_all("span", class_="chapternum")
        ]))

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            await self.notify_error(f"ArenaScans.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
    
        comic_soup_name: str = self.get_details_soup_name(comic_soup)
        comic_cover_img_link: str = self.get_details_cover_img_link(comic_soup)
        await self.process_cover_image(comic_cover_img_link)
        comic_status: str = "everyday"
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
        backup_chapter_url: str = self.backup_template_url.format(ch_num)
        
        chapter_image_wrappers = None
        
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        if chapter_soup:
            chapter_image_wrappers = chapter_soup.find("div", id="readerarea")
        
        if not chapter_image_wrappers:
            dynamic_soup = await self.get_dynamic_soup(
                url=comic_chapter_url, 
                selector="#readerarea", 
                domain="arenascans"
            )
            if dynamic_soup: 
                chapter_image_wrappers = dynamic_soup.find("div", id="readerarea")
                    
        if not chapter_image_wrappers:
            backup_soup = await self.get_soup(backup_chapter_url)
            if backup_soup:
                chapter_image_wrappers = backup_soup.find("div", id="readerarea")
        
        if not chapter_image_wrappers:
            backup_dynamic_soup = await self.get_dynamic_soup(
                url=backup_chapter_url, 
                selector="#readerarea", 
                domain="arenascans"
            )
            if backup_dynamic_soup:
                chapter_image_wrappers = backup_dynamic_soup.find("div", id="readerarea")
        
        if not chapter_image_wrappers:
            self.dev_tag(f"Failed to find readerarea for chapter {ch_num}")
            return []
        
        chapter_image_tags = chapter_image_wrappers.find_all("img")
        return await self.get_valid_image_links(
            tag_list=chapter_image_tags, 
            domain_name="arenascans", 
            src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num
        )
