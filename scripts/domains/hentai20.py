from bs4 import BeautifulSoup
from typing import Optional
from scripts.utils.utils import color_msg
from scripts.domains.base import DomainBase

class Hentai20(DomainBase):
    domain_key = "hentai20"
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.comic_name: str = comic_name
        self.given_config: list[str] = given_config

        self.protocol: str = "https://hentai20.io"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "hentai20").replace("teacher-s-", "teachers-")
        self.comic_url: str = f"https://hentai20.io/manga/{self.url_comic_name}/"
        self.comic_template_url: str = f"https://hentai20.io/{self.url_comic_name}-chapter-{{}}/"

        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    def get_details_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.select_one("h1.entry-title").get_text(strip=True)
    
    def get_details_cover_img_link(self, soup: BeautifulSoup) -> str:
        return soup.find("img", class_="attachment- size- wp-post-image").get("src").strip()
    
    def get_details_comic_status(self, soup: BeautifulSoup) -> str:
        return soup.find("table", class_="infotable").find_all("tr")[0].find_all("td")[1].text.lower().strip()
    
    def get_details_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        return list(reversed([
            tag.text.lower().replace("chapter", "").strip()
            for tag in soup.find("div", id="chapterlist").find_all("span", class_="chapternum")
        ]))
    
    async def get_comic_details(self) -> dict[str, str | list[str]]:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            await self.notify_error(f"Hentai20.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")

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
        # print('running Hentai20.get_chapter_image_links()')
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        chapter_soup = await self.get_soup(comic_chapter_url)
        if not chapter_soup:
            if ch_num == "0":
                ch_num = "0-prologue"
                comic_chapter_url = self.comic_template_url.format(ch_num)
                chapter_soup = await self.get_soup(comic_chapter_url)

            if not chapter_soup:
                chapter_soup = await self.get_dynamic_soup(
                    url=comic_chapter_url,
                    selector="#readerarea",
                    domain="hentai20"
                )
        # # self.dev_tag(f"chapter_soup?: {"True" if chapter_soup else "False"}")
        # special subs in hentai20
        special_subs = {
            '-s-': 's-',
            '-m-': 'm-',
            '-official-uncensored': '-uncensored',
            '-1-hs-': '-1-h-s-',
            '-t-': 't-',
            'but-you-re-the-': 'but-youre-the-',
            'until-youre-pregnant': 'until-you-re-pregnant',
        }
        temp_url_name = self.url_comic_name
        for k, v in special_subs.items():
            temp_url_name = temp_url_name.replace(k, v)
        # self.dev_tag(f'temp_url_name: {temp_url_name}')

        chapter_image_tags: list[str] = chapter_soup.find("div", id="readerarea").find_all("img")
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="hentai20", src_value="src", extra_attribute=temp_url_name, comic_name=self.comic_soup_name, chapter_num=ch_num)
