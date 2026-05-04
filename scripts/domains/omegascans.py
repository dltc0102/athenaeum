from bs4 import BeautifulSoup
from typing import Optional
from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase

class OmegaScans(DomainBase):
    domain_key = "omegascans"
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.comic_name: str = comic_name
        self.given_config: list[str] = given_config

        self.protocol: str = "https://omegascans.org"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "omegascans")
        self.comic_url: str = f"{self.protocol}/series/{self.url_comic_name}"
        self.comic_template_url: str = f"{self.comic_url}/chapter-{{}}"

        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    def get_comic_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.find("div", id="content").find("h1", class_="text-xl md:text-3xl text-foreground font-bold text-center lg:text-left inline").text.strip()
    
    def get_comic_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        ele = soup.find("img", class_="w-full bg-muted/40 h-[500px] sm:h-[720px] md:h-[530px] lg:w-full lg:h-[320px] xl:h-[430px] 2xl:h-[450px] rounded")
        return self.handle_srcset(ele)
    
    def get_comic_details_status(self, soup: BeautifulSoup) -> str:
        comic_tags = [
            tag.get_text(strip=True).lower() 
            for tag in soup.find("div", class_="flex flex-row flex-wrap gap-2").find_all("span")
        ]
        if not "ongoing" in comic_tags:
            return "completed"
        else:
            return "ongoing"
        
    def get_comic_details_release_day(self, soup: BeautifulSoup) -> str:
        wrapper = soup.find("div", class_="flex items-center justify-center gap-1")
        if not wrapper:
            return "everyday"
        
        buttons_available = wrapper.find_all("button")
        active_button_idx: int = 0
        for idx, button in enumerate(buttons_available):
            if button.get("data-state") == "on":
                active_button_idx = idx
                break
        days_of_the_week = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
        return days_of_the_week[active_button_idx]
    
    async def get_comic_details_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        wrapper = soup.find("div", class_="max-h-[720px] overflow-y-auto pr-1")

        if not wrapper:
            soup = await self.get_dynamic_soup(self.comic_url, ".space-y-4", "omegascans")
            wrapper = soup.find("div", class_="max-h-[720px] overflow-y-auto pr-1")
            if not wrapper:
                raise ValueError("OmegaScans: chapter wrapper not found")
    
        chapters_list: list[str] = list(reversed([
            tag.find("span", class_="m-0 text-[1rem] line-clamp-1 lg:max-w-none").get_text(strip=True).lower().replace("chapter", "").strip().split(" - ")[0] 
            for tag in wrapper.find_all("a", class_="text-foreground visited:text-[rgb(79,0,225)]")
        ]))
        return chapters_list
    
    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if not comic_soup:
            await self.notify_error(f"Omegascans.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
    
        comic_soup_name: str = self.get_comic_details_soup_name(comic_soup)
        comic_cover_img_link: str = self.get_comic_details_cover_img_link(comic_soup)
        await self.process_cover_image(comic_cover_img_link)
        comic_status: str = self.get_comic_details_status(comic_soup)
        release_day: str = self.get_comic_details_release_day(comic_soup)
        chapters_list: list[str] = await self.get_comic_details_chapters_list(comic_soup)
        first_chapter, *_, latest_chapter = chapters_list

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter,
            'release_day': release_day
        }
    
    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        backup_url: str = ""
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        if not chapter_soup and backup_url:
            chapter_soup = await self.get_soup(backup_url)
        
        chapter_image_tags = [
            tag for tag in chapter_soup.find_all("img")
            if tag.has_attr("src") and tag["src"].startswith("https://media.omegascans.org/file/")
        ]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="omegascans", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)

