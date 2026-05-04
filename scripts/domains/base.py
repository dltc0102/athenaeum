
from scripts.core.downloader import Downloader

class DomainBase(Downloader):
    registry = {}

    domain_key: str | None = None
    release_day: str = "everyday"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if cls.domain_key:
            DomainBase.registry[cls.domain_key] = cls

    async def initialize(self):
        details = await self.get_comic_details()

        self.comic_soup_name = details["soup_name"]
        self.comic_cover_img_link = details["cover_img_link"]
        self.comic_status = details["status"]
        self.chapters_list = details["chapters_list"]
        self.first_chapter = details["first_chapter"]
        self.latest_chapter = details["latest_chapter"]
        self.chapters_link_list = details.get("chapters_link_list", [])
        self.release_day = details.get("release_day", "everyday")
        self.comic_uid = details.get("comic_uid", 0)

        self.generated_config = [
            self.comic_soup_name,
            self.domain_key,
            0,
            self.release_day,
            self.comic_status != "ongoing",
        ]

        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list

    def get_cover_img_link(self) -> str:
        return self.comic_cover_img_link

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    