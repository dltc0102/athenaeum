from bs4 import BeautifulSoup
from typing import Optional
from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase

class VortexScans(DomainBase):
    domain_key = "vortexscans"
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name

        self.protocol: str = "https://vortexscans.org"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "vortexscans")
        self.weird_url_comic_name: str = self.url_comic_name.replace("%3A", ":")
        self.comic_url: str = f"{self.protocol}/series/{self.url_comic_name}"
        self.comic_template_url: str = f"{self.protocol}/series/{self.weird_url_comic_name}/chapter-{{}}"

        self.comic_uid = self.given_config[2]
        self.release_day = self.given_config[3]
        self.is_completed = self.given_config[4]

        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    def get_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.find("h1", class_="text-2xl font-bold leading-[1.5rem] text-foreground").get_text(strip=True)

    def get_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        return soup.find("img", class_="w-full rounded-lg object-cover object-bottom sm:max-h-[400px] h-auto transition-transform duration-300 group-hover:scale-105").get("src").strip()

    def get_details_comic_status(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="text-foreground").find_all("div", class_="flex sm:justify-between justify-start items-center gap-2")[0].find("p", class_="font-normal text-xs inline ml-1 text-foreground").get_text(strip=True).lower()

    def get_details_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        non_premium_chapters_found = [
            div_tag 
            for div_tag in soup.find("div", "mt-4 space-y-2").find_all("div", class_="w-full h-full flex items-center justify-between gap-2 sm:gap-3") 
            if not div_tag.find("div", class_="flex items-center gap-1.5 text-yellow-600 dark:text-yellow-500")
        ]
        return list(reversed([
            tag.find("span", class_="text-xs sm:text-sm font-medium").get_text().lower().replace("chapter", "").strip() 
            for tag in non_premium_chapters_found
        ]))

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup]  = await self.get_pwsoup_buttons(self.comic_url)
        if comic_soup is None:
            await self.notify_error(f"Vortexscans.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
    
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
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        chapter_image_tags = chapter_soup.find("div", class_="comic-images-wrapper reader-mode-strip").find_all("img", class_="h-auto w-full object-contain")
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="vortexscans", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)
 
