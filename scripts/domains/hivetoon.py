from bs4 import BeautifulSoup
from typing import Optional
from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase
from scripts.utils.persistence import PersistentPlaywright

class HiveToon(DomainBase):
    domain_key = "hivetoon"
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name

        self.protocol: str = "https://hivetoons.org"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "hivetoon")
        self.persistent_instance = PersistentPlaywright(given_config)
        self.comic_url: str = f"{self.protocol}/series/{self.url_comic_name}"
        self.comic_template_url: str = f"{self.comic_url}/chapter-{{}}"

        self.comic_uid = self.given_config[2]
        self.release_day = self.given_config[3]
        self.is_completed = self.given_config[4]

        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    def get_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.find("h1", class_="text-2xl font-bold text-foreground leading-[1.5rem]").get_text(strip=True)

    def get_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        return soup.find("img", class_="w-full rounded-lg object-cover object-bottom sm:max-h-[400px] h-auto").get("src").strip()

    def get_details_comic_status(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="flex w-full h-auto shrink-0 flex-col gap-3 rounded-lg sm:w-[17rem] xl:p-0 lg:p-0 md:p-0 px-2 sm:p-0").find("p", class_="font-normal text-xs inline ml-1 text-foreground").get_text(strip=True).lower()

    def get_details_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        return list(reversed([
            tag.text.replace("Chapter", "").strip() 
            for tag in soup.find("div", class_="flex w-full flex-col gap-3 px-4 py-4").find_all("h3", class_="text-gray-900 dark:text-white font-medium text-lg")
        ]))

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            await self.notify_error(f"HiveToon.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
    
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
        comic_chapter_url: str      = self.comic_template_url.format(ch_num)
        chapter_soup: BeautifulSoup = await self.persistent_instance.run_persistence_for_soup(
            comic_chapter_url, 
            filter="div.image-container", 
            scroll=True,
            increment_scroll=True,
            link_filter="storage.hivetoon.com/public/upload/"
        )
        img_tags = chapter_soup.select('div.image-container img[src*="storage.hivetoon.com/public/upload/"]')
        chapter_image_tags = [tag for tag in img_tags if "logo" not in tag.get("src").lower().strip()]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="hivetoon", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)
