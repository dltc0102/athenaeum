import os, time
import datetime as dt
import scripts.domains
from scripts.utils.chapter_progress import ChapterProgressBar
from scripts.core.control_panel import ControlPanel
from scripts.domains.base import DomainBase
from scripts.utils.utils import color_msg


class ComicRouter(ControlPanel):
    async def comic_redirect(self, config: list[str]) -> bool:
        comic_name, comic_domain, comic_id, release_day, is_completed = config
        self.panel_tag(color_msg("lightblack", "--------------------------------------"))
        self.panel_tag(color_msg("red", f"Working on: {comic_name}, {comic_domain}"))

        try:
            domain_class = DomainBase.registry[comic_domain]
        except KeyError:
            await self.notify_error(f"Unknown comic domain: {comic_domain}")
            return False

        if comic_domain == "asuracomics":
            series_url = "" if isinstance(comic_id, int) else comic_id
            domain_instance = domain_class(given_config=config, comic_name=comic_name, series_url=series_url, headers=self.headers, async_client=self.async_client, archivist_inst=self.archivist_inst)
        
        elif comic_domain == "flamecomics":
            domain_instance = domain_class(given_config=config, comic_name=comic_name, comic_id=comic_id, headers=self.headers, async_client=self.async_client, archivist_inst=self.archivist_inst)

        else:
            domain_instance = domain_class(given_config=config, comic_name=comic_name, headers=self.headers, async_client=self.async_client, archivist_inst=self.archivist_inst)
        await domain_instance.initialize()

        accurate_comic_name: str = comic_name
        comic_soup_name: str = domain_instance.get_comic_soup_name()
        if accurate_comic_name != comic_soup_name:
            accurate_comic_name = comic_soup_name

        self.comic_progress: int = self.get_progress_of_comic(comic_name)
        self.comic_dirpath: str = self.bookshelf.setup_comic(accurate_comic_name)
        self.dev_tag(self.comic_dirpath)
        start_ch: str = domain_instance.get_first_chapter()
        latest_ch: str = domain_instance.get_latest_chapter()
        if '-' in latest_ch:
            temp_latest_ch = latest_ch.replace(" ", "").split("-")[0]
            latest_ch = temp_latest_ch
            
        chapters_list: list[str] = domain_instance.get_chapters_list()
        if chapters_list == []:
            self.panel_tag(color_msg("lightyellow", f"This comic does not have chapters yet. Skipping."))
            return
        # self.dev_tag(f'chapters_list: {chapters_list}')

        self.panel_tag(color_msg("lightyellow", f"Start CH #: {start_ch}"))
        self.panel_tag(color_msg("lightyellow", f"Latest CH #: {latest_ch}"))

        TEMP_DIR: str = os.path.join(os.getcwd(), "temp")

        # optimize chapters here.
        # if progress of comic is less than 10, keep minimal reading buffer of as much as possible, high limit of this for 100
        # if progress of comic == latest_chapter or near the latest chapter (like say 35%), and comic status is ongoing, try for next possible chapter
        
        minimum_reading_buffer: int = 300
        comic_dirpath_data: tuple[list[str], list[str]] = self.get_comic_dirpath_data(chapters_list)
        downloaded_chapters: list[str] = comic_dirpath_data[0]
        chapters_left: list[str] = comic_dirpath_data[1]
        if len(chapters_left) < 15: 
            self.panel_tag(f'chapters_left: {chapters_left}')
        downloaded_chapters_num: int = len(downloaded_chapters)
        remaining_chapters: int = len(chapters_left)

        # self.dev_tag(f'chapters_list: {chapters_list}')
        # self.dev_tag(f'chapters_left: {chapters_left}')
        # self.dev_tag(f'downloaded_chapters: {downloaded_chapters}')
        # self.dev_tag(f'downloaded_chapters_num: {downloaded_chapters_num}')

        if downloaded_chapters_num >= minimum_reading_buffer and remaining_chapters >= 100:
            continue_downloading_point: int = downloaded_chapters[-20]
            if self.comic_progress != continue_downloading_point:
                self.panel_tag(color_msg("lightyellow", f"This comic has minimum_reading_buffer (300) chapters downloaded and there are more than 100 remaining chapters. Skipping..."))
                return

        if len(chapters_list) > 300 and downloaded_chapters_num < 1:
            if accurate_comic_name not in self.comic_buffer_bypasses: # if comic name is in bypass list, skip this
                self.panel_tag(color_msg('lightblue', f'Comic has too many chapters left ({len(chapters_left)} left), only downloading a suitable amount.'))
                if self.comic_progress == minimum_reading_buffer and len(chapters_left) != 0:
                    pass
                elif downloaded_chapters_num > 100:
                    chapters_left = chapters_left[:minimum_reading_buffer]
                    return
                if downloaded_chapters_num < minimum_reading_buffer:
                    self.panel_tag(color_msg('lightyellow', 'Comic has too little chapters, downloading enough for minimum reading buffer.'))
                    chapters_left = chapters_left[:minimum_reading_buffer]
                    pass

        if downloaded_chapters_num < 0: downloaded_chapters_num = 0
        self.panel_tag(color_msg("yellow", f"Downloaded Chapters: {downloaded_chapters_num}"))
        if len(chapters_left) == 0 or chapters_left == []:
            self.panel_tag("All chapters have been downloaded for this comic.")
            return
        
        progress = ChapterProgressBar(len(chapters_left))
        progress.start()

        self.panel_tag(color_msg("lightyellow", f"Starting at chapter: {chapters_left[0] if chapters_left else 'None'}"))


        if str(downloaded_chapters_num) == latest_ch:
            today_day = dt.datetime.now().strftime("%A").lower()
            try:
                release_day = domain_instance.get_release_day()
            except AttributeError:
                release_day = "everyday"

            if today_day != release_day:
                self.panel_tag(f"Today is not release day, and this comic is up to date!")
                return
            
            if is_completed != "ongoing":
                self.panel_tag(f"{accurate_comic_name} is now {is_completed}, not ongoing. Comic is also up to date, skipping.")
                return
                
        # Main processing loop with detailed progress tracking
        # test for now, making chapters_left: 1
        chapter_image_links = None

        # self.dev_tag(f'chapters_left: {chapters_left}')
        if domain_instance.chapters_link_list:
            chapter_links = domain_instance.chapters_link_list[-len(chapters_left):]
            chapter_items = list(zip(chapters_left, chapter_links))
        else:
            chapter_items = [(ch_num, None) for ch_num in chapters_left]
        
        if len(chapter_items) > 550 and accurate_comic_name not in self.comic_buffer_bypasses:
            print(f"chapter items are over 550, there are {len(chapter_items)} chapter items")
            return
        
        from_chapter = chapter_items[0][0]
        to_chapter = chapter_items[-1][0]
        show_chapter_str = f"{from_chapter}-{to_chapter}"
        if from_chapter == to_chapter:
            show_chapter_str = from_chapter
        await self.notify_message(f"> {comic_name} ({comic_domain}): Downloading Chapters... {show_chapter_str}")

        for chapter_num, chapter_link in chapter_items:
            link_start = time.time()

            if chapter_link:
                chapter_image_links = await domain_instance.get_chapter_image_links(ch_num=chapter_num, chapter_url=chapter_link)
            else:
                if comic_domain != "asuracomics":
                    chapter_num = chapter_num.replace(".", "-")

                if comic_domain == "manhwaread":
                    chapter_image_links = ["playwright"]
                else:
                    chapter_image_links = await domain_instance.get_chapter_image_links(ch_num=chapter_num)
            
            link_time = time.time() - link_start
            progress.log_step("Get links", link_time)
            
            if not chapter_image_links:
                progress.update_chapter(chapter_num)
                await self.notify_error(
                    color_msg("yellow", f"ComicRouter.comic_redirect():\n > Domain: {comic_domain}\n > Comic: {comic_soup_name}\n > No images for chapter {chapter_num}")
                )
        
            if chapter_link:
                await domain_instance.batch_process(
                    chapter_image_links,
                    TEMP_DIR,
                    str(chapter_num),
                    self.comic_dirpath
                )
                progress.update_chapter(chapter_num)

            elif comic_domain == "manhwaread":
                chapter_url = domain_instance.comic_template_url.format(chapter_num)
                success = await domain_instance.get_images_and_batch_process_playwright(
                    chapter_url=chapter_url,
                    regex_filter=r"^mr_\d\d\d\.(jpg|jpeg)$",
                    link_filter="manread.xyz",
                    img_element_filter="manread.xyz",
                    file_ext=".jpg",
                    temp_dirpath=TEMP_DIR,
                    chapter_number=chapter_num,
                    comic_dirpath=self.comic_dirpath
                )

                if not success:
                    await self.notify_error(color_msg("yellow", f"ManhwaRead: No images downloaded for chapter {chapter_num}"))

                progress.update_chapter(chapter_num)

            else:
                await domain_instance.batch_process(
                    chapter_image_links,
                    TEMP_DIR,
                    chapter_num,
                    self.comic_dirpath
                )
                progress.update_chapter(chapter_num)
                
        progress.close()
        return True