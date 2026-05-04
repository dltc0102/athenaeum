from bs4 import BeautifulSoup
from typing import Optional
import datetime as dt

from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase

class KingOfShojo(DomainBase):
    domain_key = "kingofshojo"
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.comic_name: str = comic_name
        self.given_config: list[str] = given_config

        self.protocol: str = "https://kingofshojo.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "kingofshojo")
        self.comic_url: str = f"{self.protocol}/manga/{self.url_comic_name}/"
        self.comic_template_url: str = f"{self.protocol}/{self.url_comic_name}-chapter-{{}}"

        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    def get_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.select_one("h1.entry-title").get_text(strip=True)

    def get_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        return soup.find("img", class_="attachment- size- wp-post-image").get("src").strip()

    def get_details_comic_status(self, soup: BeautifulSoup) -> str:
        latest_updated_chapter_dtobj = dt.datetime.strptime(soup.find("div", id="chapterlist").find("li").find("span", class_="chapterdate").text.strip(), "%B %d, %Y").date()
        is_recent: bool = self.is_recently_updated(latest_updated_chapter_dtobj)
        if is_recent:
            return "ongoing"
        else:
            return "completed"

    def get_details_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        return list(reversed([
            tag.get("data-num") 
            for tag in soup.find("div", id="chapterlist").find_all("li")
        ]))
                
    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            await self.notify_error(f"Kingofshojo.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")

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
    
    def is_recently_updated(self, update_date: dt.date) -> bool:
        today = dt.datetime.now().date()
        days_ago = today - dt.timedelta(days=60)
        if days_ago <= update_date <= today:
            return True
        else:
            return False

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        # self.dev_tag(f'KingOfShojo.get_chapter_image_links(): ch_num = {ch_num}')
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        backup_url: str = ""
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        if chapter_soup is None and backup_url:
            chapter_soup = await self.get_soup(backup_url)

        decimal_ch_num = ch_num.replace("-", ".") if "-" in ch_num else ch_num
        chapter_image_tags = [
            tag for tag in chapter_soup.find_all("img") 
            if tag.has_attr("title") and tag["title"].strip().startswith(f"{self.comic_soup_name.strip()} Chapter {decimal_ch_num}") and tag.has_attr("src")
        ]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="kingofshojo", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)
