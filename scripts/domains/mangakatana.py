import re
from bs4 import BeautifulSoup
from typing import Optional
from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase
from scripts.utils.persistence import PersistentPlaywright

class MangaKatana(DomainBase):
    domain_key = "mangakatana"
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name

        self.protocol: str = "https://mangakatana.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "mangakatana")
        self.comic_uid = self.given_config[2]
        self.persistent_instance = PersistentPlaywright(given_config)
        
        if self.comic_uid != 0 or self.comic_uid != "":
            self.comic_url: str = f"{self.protocol}/manga/{self.url_comic_name}.{self.comic_uid}"
        else:
            lowered_name = self.comic_namename.lower().replace("'", "").replace("\u2019", "")
            query_name = ' '.join(re.findall(r'[a-zA-Z\s]+', lowered_name)).strip()
            self.search_mangakatana(query_name)
        self.comic_template_url: str = f"{self.comic_url}/c{{}}"

        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    def get_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="info").find("h1", class_="heading").get_text(strip=True)

    def get_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="d-cell-medium media").find("img", alt="[Cover]").get("src").strip()

    def get_details_comic_status(self, soup: BeautifulSoup) -> str:
        return soup.find("div", class_="d-cell-small value status ongoing").get_text(strip=True).lower()

    def get_details_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        return list(reversed([
            tag.find("a").get("href").split("/")[-1].replace("c", "")
            for tag in soup.find("table", class_="uk-table uk-table-striped").find_all("div", class_="chapter")
        ]))

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            await self.notify_error(f"Mangakatana.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
        
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

    def search_mangakatana(self, query_name: str) -> dict:
        search_url: str = f"https://mangakatana.com/?search={{}}&search_by=m_name"
        search_soup = self.get_soup(search_url.format(query_name))
        comic_url = search_soup.find("div", class_="download").find("a", class_="fc_bt bt transition").get("href").strip().replace("/fc", "")
        return comic_url

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)

        script_tags = chapter_soup.find_all("script")

        img_url_array = None
        for script in script_tags:
            if not script.string: continue
            if not 'var thzq=' in script.string: continue
            match = re.search(r"var thzq=\[(.*?)\];", script.string, re.DOTALL)
            if not match: continue
            urls = re.findall(r"'([^']*)'", match.group(1))
            img_url_array = urls
            break
        return img_url_array
