from bs4 import BeautifulSoup
from typing import Optional
from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase

class GenZToons(DomainBase):
    domain_key = "genztoons"
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name

        self.protocol: str = "https://genzupdates.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "genztoons")
        self.comic_url: str = f"{self.protocol}/series/{self.url_comic_name}/"

        self.comic_uid = self.given_config[2]
        self.release_day = self.given_config[3]
        self.is_completed = self.given_config[4]

        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')

    def get_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.select_one("h1.text-2xl.font-semibold").get_text(strip=True)

    def get_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        return self.get_style_url(soup.find("div", class_="rounded-lg w-full bg-[image:--photoURL] aspect-[0.75/1] bg-cover bg-center bg-white/10 relative overflow-hidden"))

    def get_details_comic_status(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="w-full flex gap-3 flex-wrap").find_all("div", class_="grid gap-2 h-fit")[-1].find("div", class_="min-h-8 py-1 px-3 flex justify-center items-center bg-white/10 hover:bg-white/20 transition-all rounded-lg w-fit uppercase").get_text(strip=True).lower()

    def get_details_non_premium_chapters(self, soup: BeautifulSoup) -> list[str]:
        return list(reversed([
            tag for tag in soup.find("div", id="chapters").find_all("a", class_="group cursor-pointer relative overflow-hidden grid sm:gap-4 gap-[4vw] hover:bg-white/20 bg-white/10 rounded-2xl sm:p-2 p-[2vw] transition-all")
            if not tag.find("div", class_="flex gap-1 justify-center items-center w-fit bg-yellow-200 text-yellow-600 border-yellow-200 pl-1 pr-1.5 h-5 bg-opacity-90 rounded-full")
        ]))
    
    def get_details_chapter_links_list(self, npchapters: list[str]) -> list[str]:
        return [
            f"{self.protocol}{tag.get("href")}" 
            for tag in npchapters
        ]

    def get_details_chapters_list(self, npchapters: list[str]) -> list[str]:
        return [
            tag.select_one("span.text-sm.truncate").get_text(strip=True).lower().replace("chapter", "").strip() 
            for tag in npchapters
        ]
    
    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            await self.notify_error(f"GenZToons.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
    
        comic_soup_name: str = self.get_details_soup_name(comic_soup)
        comic_cover_img_link: str | None = self.get_details_cover_img_link(comic_soup)
        await self.process_cover_image(comic_cover_img_link)
        comic_status: str = self.get_details_comic_status(comic_soup)
        non_premium_chapters: list[str] = self.get_details_non_premium_chapters(comic_soup)
        chapters_link_list: list[str] = self.get_details_chapter_links_list(non_premium_chapters)
        chapters_list: list[str] = self.get_details_chapters_list(non_premium_chapters)
        first_chapter, *_, latest_chapter = chapters_list

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': chapters_list,
            'chapters_link_list': chapters_link_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter
        }
    
    async def get_chapter_image_links(self, ch_num: int, chapter_url: str) -> list[str]:
        chapter_image_links = await self.get_soup_images_from_wrapper_after_scroll(
            chapter_url=chapter_url, 
            wrapper_selector="#pages_panel", 
            not_in_src_word="placeholder"
        )
        return chapter_image_links
