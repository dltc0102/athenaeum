import os, time, requests, json, re, shutil, bs4, urllib, math
import datetime as dt
from tqdm import tqdm
from bs4 import BeautifulSoup
from PIL import Image, ImageFile
from colorama import Fore as CFore
from colorama import Style as CStyle
import datetime as dt
from typing import *
import asyncio, httpx, aiofiles
import aiofiles.os as aios
from tqdm import tqdm
from playwright.async_api import async_playwright
from urllib.parse import quote
from sentence_transformers import SentenceTransformer
import binascii, discord, datetime, sys
from discord.ext import commands



"""
FILENAME MEANINGS:
o main.py -> scraping
o catalogue.json -> configs
o progress.json -> progress read per comic
o api.py -> FastAPI
o svelte -> svelteJS
o supabase -> auth
o supabase -> db for progress

"""


""" DONE """
# o config fixed for extra attributes: comic_uid, release_day, is_completed
# o collect configs that need to be changed with 
# o search_mangakatana added
# o Domain asuracomics added
# o Domain flamecomics added
# o Domain omegacomics addded
# o Domain kingofshojo added
# o Domain mangakatana added, removed due to captcha on chapter urls, readded due to finding the urls just nested in a script tag in soup on init of goto url.
# o Domain toonily added
# o Domain mangafire added
# o fixed Synopsis.remove_duplicates() from not actually removing dupes
# o Added VRFGenerator for mangafire search function
# o resouped asurascans
# o fixed premium chapters being asked to be downloaded
# o Domain vortexscans fixedd
# o added minimal reading buffer if comic has lots of chapters (over 250, eleceed excused)
# o Domain hivetoon removed
# o Domain arenascans added
# yakshascans no images loading, changed to ravenscans
# o Domain ravenscans addded
# o fixed stitch_images decoder error

""" Doing """
# deal with configs to be updated after operation

""" TODO CATALOG.PY """
# smart downloads
# progress.json garbage collector
# check that if cover image filename is already in cover images, doesnt need to redownload again
# decimal chapters should be downloaded


""" TODO PAGE.PY """
# categories: Pinned, recently read, recently updated, comics
# connect page.py to new catalog.py
# improve page.py with targeted comic request ('refresh' button?), or when reading certain comic, an async function will detect comic being read, and download according to chapters read per minute/day/hour
# download for iphone with comic selection
# make images draggable=False

def color_msg(color: str, msg: str) -> str:
    colors = {
        'black': CFore.BLACK,
        'blue': CFore.BLUE,
        'cyan': CFore.CYAN,
        'green': CFore.GREEN,
        'white': CFore.WHITE,
        'red': CFore.RED,
        'magenta': CFore.MAGENTA,
        'yellow': CFore.YELLOW,
        'lightblack': CFore.LIGHTBLACK_EX,
        'lightblue': CFore.LIGHTBLUE_EX,
        'lightcyan': CFore.LIGHTCYAN_EX,
        'lightgreen': CFore.LIGHTGREEN_EX,
        'lightmagenta': CFore.LIGHTMAGENTA_EX,
        'lightred': CFore.LIGHTRED_EX,
        'lightwhite': CFore.LIGHTWHITE_EX,
        'lightyellow': CFore.LIGHTYELLOW_EX,
    }
    return f"{colors[color.lower()]}{msg}{CStyle.RESET_ALL}"

class Comparer:
    def __init__(self, list_of_configs: list[list[str]]):
        self.list_of_configs = list_of_configs
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.standard_threshold: float = 0.92
        self.english_threshold: float = 0.98
        self.dupes_to_delete_by_basename = self.get_dupes_by_base_name(self.list_of_configs)
        self.dupes_to_delete_by_model, self.manual_review = self.get_dupes_by_model(self.list_of_configs)

        self.all_dupes = self.dupes_to_delete_by_basename + self.dupes_to_delete_by_model
        

    def get_all_dupes(self):
        return self.all_dupes
    
    def get_dupes_to_be_reviewed(self):
        return self.manual_review
    
    def model_compare(self, t1: str, t2: str) -> float:
        e1 = self.model.encode(t1)
        e2 = self.model.encode(t2)
        sim = self.model.similarity(e1, e2).item()
        return sim

    def has_parentheses(self, name: str) -> bool:
        return bool(re.search(r"\(.+\)", name))

    def get_dupes_by_base_name(self, config_list) -> list[list[str]]: 
        pattern = r'\s*\([^)]+\)\s*$'
        comics_by_base_name = {}
        dupes = []
        for sublist in self.list_of_configs:
            comic_name = sublist[0]
            base_name = re.sub(pattern, '', comic_name).strip()
            if base_name not in comics_by_base_name:
                comics_by_base_name[base_name] = []
            comics_by_base_name[base_name].append(sublist)

        for base_name, comics in comics_by_base_name.items():
            if len(comics) > 1:
                comic1, comic2 = comics
                name1 = comic1[0]
                name2 = comic2[0]
                check1 = self.has_parentheses(name1)
                check2 = self.has_parentheses(name2)
                if check1 and not check2:
                    dupes.append(comic2)
                elif check2 and not check1:
                    dupes.append(comic1)
        return dupes

    def get_dupes_by_model(self, config_list) -> list[list[str]]:
        similar_matches = []
        for idx in range(len(config_list) - 1):
            curr_list = config_list[idx]
            next_list = config_list[idx+1]
            curr_name = curr_list[0]
            next_name = next_list[0]
            similarity = self.model_compare(curr_name, next_name)
            if similarity > self.standard_threshold:
                similar_matches.append([curr_list, next_list])
        
        model_dupes = []
        manual_review = []
        for dupe_pair in similar_matches:
            sublist1, sublist2 = dupe_pair
            title1, domain1, *_ = sublist1
            title2, domain2, *_ = sublist2
            has_dash1 = '-' in title1
            has_dash2 = '-' in title2
            symbols = '?!.,:;'
            
            has_symbols1 = any(s in title1 for s in symbols)
            has_symbols2 = any(s in title2 for s in symbols)
            sim = self.model_compare(title1, title2)

            if has_dash1 and not has_dash2:
                model_dupes.append(sublist2)
            elif has_dash2 and not has_dash1:
                model_dupes.append(sublist1)
            elif has_symbols1 and not has_symbols2:
                model_dupes.append(sublist2)
            elif has_symbols2 and not has_symbols1:
                model_dupes.append(sublist1)
            elif sim > self.english_threshold:
                manual_review.append(dupe_pair)
            elif domain1 == 'hentai20':
                if 'high school' in title1.lower() and 'highschool' in title2.lower():
                    model_dupes.append(sublist2)
                elif 'high school' in title2.lower() and 'highschool' in title1.lower():
                    model_dupes.append(sublist1)
            else:
                manual_review.append(dupe_pair)

        return model_dupes, manual_review

class Synopsis:
    def __init__(self, current_config_path: str, merger_filepath: str = None):
        self.current_config_path = current_config_path
        self.temp_config_path = os.path.join(os.getcwd(), "temp_config.json")
        self.current_config = self.load_config(self.current_config_path)
        self.config_changes: list[list[str, str]] = []

        self.needs_conversion: bool = True if isinstance(self.current_config, dict) else False

        self.merger_filepath: str | None = merger_filepath
        self.merger_config = None
        self.needs_merge: bool = True if (merger_filepath and os.path.exists(merger_filepath)) else False
        if self.needs_merge and os.path.exists(self.merger_filepath):
            self.merger_config = self.load_config(self.merger_filepath)

        self.merge_tag = color_msg("red", "[><]")
        len_current = len(self.current_config)
        len_merger = 0
        if self.merger_filepath and self.merger_config:
            len_merger = len(self.merger_config)
        self.synopsis_merge_tag(f"current_config: {len_current}")
        self.synopsis_merge_tag(f"merger_config: {len_merger}")
        self.synopsis_merge_tag(f"raw combined config: {len_current + len_merger }")

        if self.needs_conversion:
            self.synopsis_tag('Config format is incorrect, restucturing config.')
            self.convert_config()
        else:
            self.synopsis_tag("Config format is correct, skipping conversion.")
            # create temp_config.json with current_config because its already converted but temp_config.json is empty
            self.save_config(self.current_config, self.temp_config_path)

        self.sorted_config: List[str] = self.sort_temp_config()

        self.save_config(self.sorted_config, self.temp_config_path)
        # remove current config path after saving merged process data to the temp_file
        if os.path.exists(self.current_config_path): os.remove(self.current_config_path) 

        if self.needs_merge:
            self.synopsis_tag("Merge file detected, merging...")
            self.merge_configs()
        else:
            self.synopsis_tag("No merge files detected, skipping merging.")

        self.rename_config(self.temp_config_path, self.current_config_path)
        self.regulate_domains()
        self.remove_duplicates()
        self.synopsis_tag("Sorted config alphabetically.")
        self.synopsis_tag("Config is ready for scraping.")
    
    def remove_duplicates(self) -> None:
        current_config = self.load_config(self.current_config_path)
        instance = Comparer(current_config)
        dupes = instance.get_all_dupes()
        review_dupes = instance.get_dupes_to_be_reviewed()
        if dupes == [] and review_dupes == []:
            self.synopsis_tag(f"No dupes found. No review dupes to be dealt with.")
            return
        
        # clean_config_list = []
        # for config in current_config:
            # if config in dupes:
            #   comic_name = config[0]
            #   if comic_name in self.config_changes, remove that comic_name item and then add [comic_name, ""]
            
            # if config not in dupes:
            #     clean_config_list.append(config)
            
        self.synopsis_tag(color_msg("red", f"{len(dupes)} duplicates without parentheses have been deleted. "))

        for dupe in review_dupes:
            opt1, opt2 = dupe
            clean_config_list = [config for config in clean_config_list if config not in [opt1, opt2]]
            print(f"1. {opt1}")
            print(f"2. {opt2}")
            choice = int(input("Please input which to keep (1/2?): "))
            while choice != 1 and choice != 2 and isinstance(choice, int):
                choice = int(input("Please input which to keep (1/2?): "))
            chosen_to_keep = dupe[int(choice)-1]
            self.synopsis_tag(f"Choice {choice} has been chosen to keep: {chosen_to_keep}, adding back to current_configs")
            clean_config_list.append(chosen_to_keep)
        
        sorted_config_list = sorted(clean_config_list, key=lambda x: x[0].lower())
        self.save_config(sorted_config_list, self.current_config_path)
        self.synopsis_tag(f'Saved {self.current_config_path} with removed duplicates.')
        return

    def regulate_domains(self) -> None:
        """ regulates domains"""
        config = self.load_config(self.current_config_path)
        regulated_config = {}
        for comic in config:
            name, domain, comic_id, release_day, status = comic

            if domain == "pornhwa":
                domain = "pornhwa.me"
            if domain == "manga18":
                domain = "manga18.me"
            if name not in regulated_config:
                regulated_config[name] = [name, domain, comic_id, release_day, status]
            else:
                continue
                
        regulated_config_list = list(regulated_config.values())
        self.save_config(regulated_config_list, self.current_config_path)
        self.synopsis_tag(f"Domains regulated.")
        return
    
    def synopsis_tag(self, msg) -> None:
        print(color_msg("yellow", f"[Synopsis] {msg}"))
    
    def synopsis_merge_tag(self, msg) -> None:
        self.synopsis_tag(f"{self.merge_tag} {msg}")

    def load_config(self, path: str) -> dict:
        """ loads config into a dict """
        with open(path, "r") as f:
            config_data = json.load(f)
        return config_data

    def save_config(self, input_data: list, save_path: str) -> None:
        """ saves config with param of input_data as a list of items """
        with open(save_path, "w") as f:
            json.dump(input_data, f, ensure_ascii=True, indent=2)

    def sort_temp_config(self, giv_config: list = None) -> list[str]:
        """ sorts config alphabetically """
        comic_list: list[list[str]] = []
        config = self.load_config(self.temp_config_path)
        if giv_config:
            config = giv_config
        for item in config:
            name = item[0].strip()
            domain = item[1].strip()
            if len(item) >= 5:
                comic_id = item[2]
                release_day = item[3].strip()
                is_completed = item[4]
            elif len(item) == 2 and not len(item) == 5:
                comic_id = 0
                release_day = "everyday"
                is_completed = False
            comic_list.append([name, domain, comic_id, release_day, is_completed])
        return sorted(comic_list, key=lambda x: x[0].lower())

    def get_config_comics(self) -> Dict['comic_name': 'domain_name']:
        """returns a dict of comic_name: domain_name"""
        return self.load_config(self.current_config_path)
    
    def convert_config(self) -> None:
        config_data = self.current_config["queue"]
        comic_infos: list[list[str]] = []
        
        for config in config_data:
            comic_name: str = config.get("comic_dir_name", "")
            domain_name: str = config.get("domain_name", "")
            release_day: str = config.get("release_day", "everyday")
            comic_id: int =  config.get("comic_id", 0)
            is_completed_boolnum: int = config.get("is_completed", 0)
            is_completed: bool = True if is_completed_boolnum == 1 else False
            comic_infos.append([comic_name, domain_name, comic_id, release_day, is_completed])
            self.config_changes.append([comic_name, None])
        self.save_config(comic_infos, self.temp_config_path)
        self.synopsis_tag("Config restructured.")
        return

    def merge_configs(self) -> None:
        main_list = self.load_config(self.temp_config_path)
        list_to_be_merged = self.merger_config

        result_dict = {}
        def normalize_name(name):
            normalized = re.sub(r'[^\w\s]', '', name.lower())
            normalized = re.sub(r'\s+', ' ', normalized).strip()
            return normalized
        
        for item in main_list:
            comic_name = item[0]
            domain_name = item[1]
            comic_id = item[2]
            release_day = item[3]
            is_completed = item[4]

            key = normalize_name(comic_name)
            if "'" in comic_name:
                continue
            else:
                result_dict[key] = [comic_name, domain_name, comic_id, release_day, is_completed]
        
        comics_added = 0
        comics_updated = 0
        
        for item in list_to_be_merged:
            comic_name = item[0]
            domain_name = item[1]
            default_comic_id = 0
            default_release_day = "everyday"
            default_is_completed = False
            
            key = normalize_name(comic_name)

            if key not in result_dict:
                result_dict[key] = [comic_name, domain_name, default_comic_id, default_release_day, default_is_completed]
                comics_added += 1
            else:

                existing_info = result_dict[key]
                existing_name = existing_info[0]
                if normalize_name(existing_name) == key:
                    result_dict[existing_name] = existing_info
                else:
                    if "'" in existing_name and "\u2019" in comic_name:
                            result_dict[key] = [comic_name, domain_name, default_comic_id, default_release_day, default_is_completed]
                    elif "'" in comic_name and "\u2019" in existing_name:
                            result_dict[existing_name] = existing_info
                    else:
                            result_dict[key] = [comic_name, domain_name, default_comic_id, default_release_day, default_is_completed]
                comics_updated += 1
        
        result = list(result_dict.values())

        self.synopsis_merge_tag(f"combined_config: {len(result)}")
        self.synopsis_merge_tag(f"{color_msg('green', f'[+] {comics_added} comics added.')}")
        if comics_updated > 0:
            self.synopsis_merge_tag(f"{color_msg('blue', f'[~] {comics_updated} comics updated.')}")
        
        os.remove(self.merger_filepath)
        self.synopsis_merge_tag(f"merger_file deleted.")
        self.save_config(result, self.temp_config_path)
        return

    def rename_config(self, input_filename: str, output_filename: str) -> None:
        if not os.path.exists(input_filename):
            self.synopsis_tag(color_msg("red", f"{input_filename} input file does not exist for renaming."))
            return
        
        if os.path.exists(output_filename):
            os.remove(output_filename)
        
        os.rename(input_filename, output_filename)
        self.synopsis_tag(f"Renamed {input_filename} to {output_filename}")
        return
    
class ControlPanel:
    def __init__(self, headers: dict[str, str], async_client: httpx.AsyncClient):
        self.headers = headers
        self.async_client = async_client
        self.bookshelf = Bookshelf()
        self.comic_buffer_bypasses: list[str] = ["Eleceed"]
        self.cover_images_dirpath = os.path.join(os.getcwd(), "cover_images_test")
        self.possible_image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg'}
        self.cover_images: list[str] = []

        if not os.path.exists(self.cover_images_dirpath):
            os.makedirs(self.cover_images_dirpath, exist_ok=True)

        if os.path.exists(self.cover_images_dirpath):
            self.cover_images = [
                file for file in os.listdir(self.cover_images_dirpath) if os.path.splitext(file)[1].lower() in self.possible_image_exts
            ]
        self.dev_mode = 0
        self.configs_to_be_updated = []
        self.failed_fetches = []

    def get_failed_fetches(self) -> list[str]:
        return self.failed_fetches

    def get_progress_comics(self) -> dict[str, str]:
        return self.bookshelf.progress_comics

    def cleanup_config(self) -> None:
        if self.configs_to_be_updated == []:
            self.panel_tag("No configs to update.")
            return
        self.panel_tag(f'cleanup_config has {len(self.configs_to_be_updated)} configs to be updated.')
        for config in self.configs_to_be_updated:
            self.panel_tag(config)

    def panel_tag(self, msg: str) -> None:
        print(color_msg("lightblue", f"[Control] {msg}"))

    def dev_tag(self, msg: str) -> None:
        print(color_msg("lightred", f"[DEV] {msg}"))

    async def validate_image_link(self, link: str) -> bool:
        if not link.startswith("https://"): return False
        head_response = await self.async_client.head(link, follow_redirects=True, timeout=30.0)
        content_type = head_response.headers.get("content-type", "").lower()
        content_length_value = head_response.headers.get("content-length", "").lower()
        if content_length_value == "":
            content_length_value = 0
        content_length = float(content_length_value)
        if content_length < 1 or content_length == 0:
            return False
        
        if content_type and content_type.startswith("image/"):
            return True
        else:
            return False

    @staticmethod
    def get_url_comic_name(comic_name: str, domain_name=None) -> str:
        if comic_name == "Reality Quest":
            comic_name = "Reality Quest 2"

        # if domain_name == "mangakatana": comic_name = comic_name.replace("\u2019", "").replace("'", "")

        res = comic_name.lower()
        if domain_name == "vortexscans":
            res = res.replace(":", "%3A")
            
        chars_to_remove = ["(", ")", ":", "\u2013", "\u2026", "!", "?", "%", ".", "~", ",", "+"]
        chars_to_replace = [" ", "'", "\u2019"]

        if domain_name in ["manga18", "manhuaus", "yakshascans", "manhwabuddy", "pornhwa", "kingofshojo", "ravenscans"]:
            res = res.replace("\u2019", "")

        for char in chars_to_remove:
            res = res.replace(char, "")

        for char in chars_to_replace:
            res = res.replace(char, "-")
        res = re.sub(r'-+', '-', res)
        res = res.strip('-')
        return res.strip()

    async def get_url_response(self, url: str) -> Optional[httpx.Response]:
        res = await self.async_client.get(url)
        return res if res.status_code == 200 else None

    async def get_url_response_object(self, url: str) -> Optional[httpx.Response]:
        try:
            res = await self.async_client.get(url)
            return res
        except Exception as e:
            print(f"Request error: {e}")
            return None
        
    @staticmethod
    def get_cover_img_fname(comic_name: str, link: str) -> str:
        filename = comic_name.lower()
        filename = re.sub(r'[^\w\s\-+]', '', filename)
        filename = filename.replace(' ', '_').replace('-', '_')
        filename = re.sub(r'_+', '_', filename)
        filename = filename.strip('_')
        
        extension = f'.{link.split("/")[-1].split(".")[-1]}'
        return f"{filename}{extension}"

    async def _cleanup_incomplete_chapter(self, temp_dir: str, comic_dirpath: str, chapter_num: str) -> None:
        try:
            await reset_dir(temp_dir)
            if isinstance(chapter_num, int): chapter_num = str(chapter_num)
            safer_chapter_num = chapter_num.replace('.', '-')
            try:
                if '.' in safer_chapter_num:
                    chapter_int = int(float(safer_chapter_num.split('-')[0]))
                else:
                    chapter_int = int(safer_chapter_num.split('-')[0])
            except (ValueError, IndexError):
                print(color_msg("yellow", f"Could not parse chapter number: {chapter_num}"))
                return
            
            patterns = []
            for idx in range(chapter_int-5, chapter_int):
                patterns.append(re.compile(rf"chapter-{re.escape(idx)}-p\d+\.jpg"))

            deleted_files = []
            if os.path.exists(comic_dirpath):
                for file_name in os.listdir(comic_dirpath):
                    for pattern in patterns:
                        if pattern.match(file_name):
                            file_path = os.path.join(comic_dirpath, file_name)
                            os.remove(file_path)
                            deleted_files.append(file_name)
            if deleted_files:
                print(color_msg("yellow", f"Deleted incomplete chapter files: {deleted_files}"))
            
        except Exception as cleanup_error:
            print(color_msg("red", f"Error during cleanup: {cleanup_error}"))

    def get_progress_of_comic(self, comic_name: str) -> int:
        with open("progress_bup.json", 'r', encoding='utf-8') as p:
            progress_data = json.load(p)
        if comic_name in progress_data.keys():
            return progress_data[comic_name]
        else:
            return 1
        
    async def comic_redirect(self, config: list[str, str]) -> bool:
        comic_name, comic_domain, comic_id, release_day, is_completed = config
        self.panel_tag(color_msg("lightblack", "--------------------------------------"))
        self.panel_tag(color_msg("red", f"Working on: {comic_name}, {comic_domain}"))

        domain_class = {
            "manga18.me": Manga18,
            "mgeko": Mgeko,
            "manhuaus": Manhuaus,
            "yakshascans": Yakshascans,
            "manhwabuddy": Manhwabuddy,
            "pornhwa.me": Pornhwa,
            "hentai20": Hentai20,
            "asuracomics": AsuraComics,
            "flamecomics": FlameComics,
            "omegascans": OmegaScans,
            "kingofshojo": KingOfShojo,
            "toonily": Toonily,
            "mangafire": MangaFire,
            "vortexscans": VortexScans,
            "utoon": UToon,
            "hivetoon": HiveToon,
            "mangakatana": MangaKatana,
            "arenascans": ArenaScans,
            "ravenscans": Ravenscans,
        }[comic_domain]

        if comic_domain == "asuracomics":
            series_url = "" if isinstance(comic_id, int) else comic_id
            domain_instance = domain_class(given_config=config, comic_name=comic_name, series_url=series_url, headers=self.headers, async_client=self.async_client)
        
        elif comic_domain == "flamecomics":
            domain_instance = domain_class(given_config=config, comic_name=comic_name, comic_id=comic_id, headers=self.headers, async_client=self.async_client)

        else:
            domain_instance = domain_class(given_config=config, comic_name=comic_name, headers=self.headers, async_client=self.async_client)
        await domain_instance.initialize()

        accurate_comic_name: str = comic_name
        comic_soup_name: str = domain_instance.get_comic_soup_name()
        if accurate_comic_name != comic_soup_name:
            accurate_comic_name = comic_soup_name

        comic_dirpath: str = self.bookshelf.setup_comic(accurate_comic_name)
        start_ch: str = domain_instance.get_first_chapter()
        latest_ch: str = domain_instance.get_latest_chapter()
        chapters_list: list[str] = domain_instance.get_chapters_list()
                

        self.panel_tag(color_msg("lightyellow", f"Start CH #: {start_ch}"))
        self.panel_tag(color_msg("lightyellow", f"Latest CH #: {latest_ch}"))

        TEMP_DIR: str = os.path.join(os.getcwd(), "temp")

        # optimize chapters here.
        # if progress of comic is less than 10, keep minimal reading buffer of as much as possible, high limit of this for 100
        # if progress of comic == latest_chapter or near the latest chapter (like say 35%), and comic status is ongoing, try for next possible chapter
        
        minimum_reading_buffer: int = 100
        chapters_left: list[str] = await domain_instance.get_chapters_left(comic_dirpath, chapters_list)
        downloaded_chapters: int = int(math.floor(float(latest_ch))) - len(chapters_left)
        # use_buffer = False
        # if len(chapters_list) > 250 and downloaded_chapters == 0:
        #     if accurate_comic_name not in self.comic_buffer_bypasses: # if comic name is in bypass list, skip this
        #         self.panel_tag(color_msg('lightblue', f'Comic has too many chapters left ({len(chapters_left)} left), only downloading a suitable amount.'))
        #         if self.get_progress_of_comic(comic_name) == minimum_reading_buffer and len(chapters_left) != 0:
        #             pass
        #         elif downloaded_chapters > 100:
        #             chapters_left = chapters_left[:minimum_reading_buffer]
        #             return
        #         if downloaded_chapters < minimum_reading_buffer:
        #             self.panel_tag(color_msg('lightyellow', 'Comic has too little chapters, downloading enough for minimum reading buffer.'))
        #             chapters_left = chapters_left[:minimum_reading_buffer]
        #             pass

        if downloaded_chapters < 0: downloaded_chapters = 0
        self.panel_tag(color_msg("yellow", f"Downloaded Chapters: {downloaded_chapters}"))
        if len(chapters_left) == 0 or chapters_left == []:
            self.panel_tag("All chapters have been downloaded for this comic.")
            return
        
        progress = ChapterProgressBar(len(chapters_left))
        progress.start()

        self.panel_tag(color_msg("lightyellow", f"Starting at chapter: {chapters_left[0] if chapters_left else "None"}"))

        if downloaded_chapters == latest_ch:
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

        if comic_domain == "flamecomics" or comic_domain == "vortexscans":
            chapter_to_start_on = int(chapters_left[0])
            chapter_links = await domain_instance.get_chapter_links_list()
            chapter_items = list(enumerate(chapter_links, chapter_to_start_on-1))
        else:
            chapter_items = [(i, ch) for i, ch in enumerate(chapters_left, 1)]
        
        # if len(chapter_items) > 250 and accurate_comic_name not in self.comic_buffer_bypasses:
        #     return
        # self.dev_tag(f'chapter_items: {chapter_items}')
        
        # flamecomics uses idx for ints because the chapter url formation are made of unique id links
        for idx, chapter_num in chapter_items:
            if comic_domain != "flamecomics":
                chapter_num = chapter_num.replace(".", "-")
            link_start = time.time()
            if comic_domain == "flamecomics":
                chapter_image_links = await domain_instance.get_chapter_image_links(ch_num=idx)
            else:
                chapter_image_links = await domain_instance.get_chapter_image_links(ch_num=chapter_num)
            
            link_time = time.time() - link_start
            progress.log_step("Get links", link_time)
            
            if not chapter_image_links:
                if comic_domain == "flamecomics" or comic_domain == "vortexscans":
                    progress.update_chapter(idx)
                else:
                    progress.update_chapter(chapter_num)
                raise ValueError(color_msg("yellow", f"No images for chapter {chapter_num}"))
        
            process_start = time.time()
            if comic_domain == "flamecomics" or comic_domain == "vortexscans":
                await domain_instance.batch_process(chapter_image_links, TEMP_DIR, str(idx), comic_dirpath)
            else:
                await domain_instance.batch_process(chapter_image_links, TEMP_DIR, chapter_num, comic_dirpath)
            process_time = time.time() - process_start
            progress.log_step("Process", process_time)
            
            if comic_domain == "flamecomics" or comic_domain == "vortexscans":
                progress.update_chapter(idx)
            else:
                progress.update_chapter(chapter_num)  
                
        progress.close()
        return True
    
class ChapterProgressBar:
    def __init__(self, total_chapters: int):
        self.total_chapters = total_chapters
        self.current_chapter = 0
        self.pbar = None
        
    def start(self):
        self.pbar = tqdm(total=self.total_chapters, desc="Processing chapters", bar_format="{l_bar}{bar}{r_bar}", leave=False)
        
    def update_chapter(self, chapter_num: str):
        self.current_chapter += 1
        self.pbar.set_description(f"Ch {chapter_num}")
        self.pbar.update(1)
        
    def log_step(self, step: str, time_taken: float):
        self.pbar.set_postfix_str(f"{step}: {time_taken:.1f}s")
        
    def close(self):
        if self.pbar:
            self.pbar.close()

class Bookshelf:
    def __init__(self):
        self.bookshelf_dirpath = os.path.join(os.getcwd(), "Bookshelf_test")
        self._ensure_bookshelf_dir()
        self.progress_comics: dict[str, str] = {}

    def bookshelf_tag(self, msg: str) -> None:
        print(color_msg("lightgreen", f"[Bookshelf] {msg}"))

    def _ensure_bookshelf_dir(self) -> None:
        """ ensures bookshelf directory exists """
        os.makedirs(self.bookshelf_dirpath, exist_ok=True)

    def _normalise_comic_name(self, giv_name: str) -> str:
        return giv_name.replace("\u2019", "'").replace("\u2026", "...").replace("\u2013", "-").strip()

    def get_all_comics_downloaded(self):
        if not os.path.exists(self.bookshelf_dirpath):
            return []

        comics = []
        for item in os.listdir(self.bookshelf_dirpath):
            item_path = os.path.join(self.bookshelf_dirpath, item)
            if os.path.isdir(item_path):
                comics.append(item)

        return comics

    def register_comic(self, normalised_name: str) -> str:
        self.bookshelf_tag(f"Running Bookshelf.register_comic")
        comic_dirpath: str = os.path.join(self.bookshelf_dirpath, normalised_name)
        os.makedirs(comic_dirpath, exist_ok=True)
        self.bookshelf_tag(f"[+Dir] Created {normalised_name} comic dir.")
        return comic_dirpath

    def setup_comic(self, comic_name: str) -> str:
        self.bookshelf_tag(f"Running Bookshelf.setup_comic")
        comics_in_bookshelf: list[str] = self.get_all_comics_downloaded()
        normalised_name: str = self._normalise_comic_name(comic_name)
        if normalised_name not in self.progress_comics.keys():
            self.progress_comics[normalised_name] = 1
        else:
            pass

        if normalised_name in comics_in_bookshelf:
            comic_dirpath = os.path.join(self.bookshelf_dirpath, normalised_name)
            return comic_dirpath
        else:
            return self.register_comic(normalised_name)

class Downloader(ControlPanel):
    def __init__(self, headers=None, async_client=None):
        super().__init__(headers, async_client)
    
    async def get_soup(self, url: str) -> Optional[BeautifulSoup]:
        res = await self.get_url_response(url)
        if res is None:
            print(color_msg("red", f"Failed to fetch {url}"))
            self.failed_fetches.append(url)
            return None
        return BeautifulSoup(res.content, "html.parser")
    
    @staticmethod
    def get_extension(url: str):
        return f".{url.split('/')[-1].split('.')[-1]}"
    
    async def download_single_image(self, img_link: str, img_output_path: str) -> None:
        try:
            async with self.async_client.stream('GET', img_link) as response:
                response.raise_for_status()
                async with aiofiles.open(img_output_path, 'wb') as file:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        await file.write(chunk)
        except Exception as e:
            print(color_msg("yellow", f"Failed to download {img_link}: {e}"))
        return
    
    async def get_chapters_left(self, comic_dirpath: str, chapters: list[str]) -> list[str]:
        existing_files = os.listdir(comic_dirpath)
        existing_chapters = set()
        pattern = r"chapter-(\d+(?:[\.-]\d+)*)-p\d+"
        for file in existing_files:
            match = re.search(pattern, file)
            if match:
                chapter_str = match.group(1)
                if '-' in chapter_str:
                    chapter_str = chapter_str.replace('-', '.')
                existing_chapters.add(chapter_str)
        
        chapters_left = [chapter for chapter in chapters if chapter not in existing_chapters]
        return chapters_left
    
    def handle_srcset(self, element) -> str:
        srcset = element.get("srcset", "")
        cover_img_link = ""
        if srcset:
            cover_img_link = self.extract_url_from_srcset(srcset)
        
        if not cover_img_link:
            src = element.get("src", "")
            if src.startswith('/_next/image'):
                parsed = urllib.parse.urlparse(src)
                query_params = urllib.parse.parse_qs(parsed.query)
                if 'url' in query_params:
                    cover_img_link = urllib.parse.unquote(query_params['url'][0])
            else:
                cover_img_link = src
        return cover_img_link
    
    def extract_url_from_srcset(self, link: str):
        if link.startswith('/_next/image'):
            parsed = urllib.parse.urlparse(link)
            query_params = urllib.parse.parse_qs(parsed.query)
            if 'url' in query_params:
                return urllib.parse.unquote(query_params['url'][0])
            
    async def batch_process(self, links_list: list[str], temp_dirpath: str, chapter_number: str, comic_dirpath: str):
        img_paths = await self.batch_download(links_list, temp_dirpath, chapter_number)
        await self.stitch_images(img_paths, temp_dirpath, comic_dirpath, chapter_number)
        await reset_dir(temp_dirpath)

    async def batch_download(self, links_list: list[str], temp_dirpath: str, chapter_number: str):
        img_paths: list[str] = []
        download_tasks = []
        
        for idx, url in enumerate(links_list, 1):
            extension: str = self.get_extension(url)
            safer_chapter_number = chapter_number.replace('.', '-')
            chapter_filename = f"chapter-{safer_chapter_number}-f{idx}{extension}" # f for fragment
            img_paths.append(os.path.join(temp_dirpath, chapter_filename))
            download_tasks.append((url, os.path.join(temp_dirpath, chapter_filename)))
        
        semaphore = asyncio.Semaphore(10)
        
        async def download_with_semaphore(url, output_path):
            async with semaphore:
                await self.download_single_image(url, output_path)
        
        tasks = [download_with_semaphore(url, path) for url, path in download_tasks]
        
        for future in asyncio.as_completed(tasks):
            await future
        
        return img_paths

    async def stitch_images(self, img_paths: list[str], temp_dirpath: str, comic_dirpath: str, chapter_number: str):
        os.makedirs(comic_dirpath, exist_ok=True)
        
        def extract_fragment_number(path: str) -> int:
            filename = os.path.basename(path)
            match = re.search(r"f(\d+)\.", filename)
            return int(match.group(1)) if match else 0
        
        img_paths.sort(key=extract_fragment_number)
        
        valid_img_paths = []
        for img_path in img_paths:
            try:
                # Test if image can be opened
                with Image.open(img_path) as test_img:
                    test_img.verify()
                valid_img_paths.append(img_path)
            except (IOError, OSError, SyntaxError, Image.UnidentifiedImageError, Exception) as e:
                print(color_msg("yellow", f"Skipping corrupted image: {img_path} - {e}"))
                continue
        
        if not valid_img_paths:
            print(color_msg("red", f"No valid images found for chapter {chapter_number}"))
            return
        
        image_dimensions = []
        for img_path in valid_img_paths:
            try:
                with Image.open(img_path) as img:
                    width, height = img.size
                    image_dimensions.append((width, height))
            except Exception as e:
                print(color_msg("yellow", f"Could not get dimensions for {img_path}: {e}"))
                continue
        
        min_width = min(width for width, height in image_dimensions)
        # print(f"Minimum width among all fragments: {min_width}px")
        
        MAX_HEIGHT = 65500
        page_groups = []
        current_group = []
        current_height = 0
        
        for img_path in valid_img_paths:
            with Image.open(img_path) as img:
                width, height = img.size
                if width <= 0 or height <= 0:
                    print(color_msg("yellow", f"Skipping image with invalid dimensions: {img_path} ({width}x{height})"))
                    continue
                
                if current_height + height > MAX_HEIGHT and current_group:
                    page_groups.append(current_group)
                    current_group = [img_path]
                    current_height = height
                else:
                    current_group.append(img_path)
                    current_height += height
        
        if current_group:
            page_groups.append(current_group)
        
        # print(f"Grouped {len(img_paths)} fragments into {len(page_groups)} pages")
        
        stitched_paths = []
        for chunk_idx, group in enumerate(page_groups, 1):
            if not group:
                continue
                
            images = []
            original_images = []
            
            for img_path in group:
                img = Image.open(img_path)
                original_images.append(img)
                
                width, height = img.size
                
                if width > min_width:
                    ratio = min_width / width
                    new_height = int(height * ratio)
                    resized_img = img.resize((min_width, new_height), Image.Resampling.LANCZOS)
                    images.append(resized_img)
                    # print(f"Resized {os.path.basename(img_path)} from {width}x{height} to {min_width}x{new_height}")
                else:
                    images.append(img.copy())
            
            widths, heights = zip(*(img.size for img in images))
            total_height = sum(heights)
            max_width = max(widths) # should be min_width
            
            new_img = Image.new('RGB', (max_width, total_height), color='white')
            
            y_offset = 0
            for img in images:
                new_img.paste(img, (0, y_offset))
                y_offset += img.size[1]
            
            stitch_ext = ".jpg"
            
            safer_chapter_number = chapter_number.replace('.', '-')
            stitched_filename = f"chapter-{safer_chapter_number}-p{chunk_idx}{stitch_ext}"
            stitched_filepath = os.path.join(comic_dirpath, stitched_filename)
            
            new_img.save(stitched_filepath, quality=95, optimize=True)
            
            stitched_paths.append(stitched_filepath)
            
            for img in images:
                if hasattr(img, 'close'):
                    img.close()
            
            for img in original_images:
                img.close()
            
            # print(f"Created page {chunk_idx}: {stitched_filename} ({len(group)} fragments, {total_height}px height)")
        
        # print(f"Stitched {len(stitched_paths)} pages to {comic_dirpath}")

    def is_cloudflare_blocked(self, response: httpx.Response) -> bool:
        """Check if response indicates Cloudflare blocking/challenge"""
        if response is None:
            return False
        
        if response.status_code in [403, 503, 429]:
            if 'cf-ray' in response.headers or 'cf-cache-status' in response.headers:
                return True
            
            if 'text/html' in response.headers.get('content-type', ''):
                content = response.text.lower()
                cloudflare_patterns = [
                    'cloudflare',
                    'checking your browser',
                    'cf-browser-verification',
                    'cf-challenge',
                    'attention: required',
                    'ddos protection',
                    'ray id:',
                    'cf-duid'
                ]
                return any(pattern in content for pattern in cloudflare_patterns)
        return False

    async def process_cover_image(self, link: str):

        is_valid_cover: bool = await self.validate_image_link(link)
        if not is_valid_cover:
            raise ValueError(color_msg("yellow", "Comic cover image link is not valid."))
        
        cover_img_filename: str = self.get_cover_img_fname(self.comic_name, link)
        cover_img_filepath: str = os.path.join(self.cover_images_dirpath, cover_img_filename)
        if cover_img_filename not in self.cover_images:
            await self.download_single_image(link, cover_img_filepath)
        return
    
    async def get_images_playwright_scroll(self, chapter_url: str, regex_filter: str, link_filter: str, img_element_filter: str, file_ext: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-dev-shm-usage', '--no-sandbox'],
            )
            page = await browser.new_page()
            page.set_default_timeout(30000)
            network_images = []

            def handle_response(response):
                url = response.url
                if url.endswith(file_ext):
                    filename = url.split("/")[-1]
                    if re.match(re.compile(regex_filter), filename):
                        if url not in network_images:
                            network_images.append(url)

            def handle_request(request):
                url = request.url
                if request.resource_type == "image" and link_filter in url and url.endswith(file_ext):
                    filename = url.split("/")[-1]
                    if re.match(re.compile(regex_filter), filename):
                        if url not in network_images:
                            network_images.append(url)

            page.on("response", handle_response)
            page.on("request", handle_request)

            await page.goto(chapter_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            for i in range(5):
                await page.evaluate(f"window.scrollTo(0, {i * 800})")
                await page.wait_for_timeout(1500)
            
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

            img_elements = await page.query_selector_all(f'img[src*="{img_element_filter}"]')
            for img in img_elements:
                src = await img.get_attribute('src')
                if src:
                    filename = src.split("/")[-1]
                    if re.match(re.compile(regex_filter), filename):
                        if src not in network_images:
                            network_images.append(src)
            await browser.close()

        def get_page_num(url):
            filename = url.split('/')[-1]
            match = re.search(r'^(\d+)', filename)
            if match:
                num_str = match.group(1)
                if num_str == '00000':
                    return 0
                return int(num_str)
            return 999
        
        chapter_images = [url for url in network_images if link_filter in url and url.endswith(file_ext)]
        chapter_images.sort(key=get_page_num)
        src_links = []
        for img in chapter_images:
            is_valid = await self.validate_image_link(img)
            if is_valid:
                src_links.append(img)

        return src_links

    async def get_valid_image_links(self, tag_list: list[str], domain_name: str, src_value: str, extra_attribute: str=None):
        valid_links: int = 0
        valid_links_list: list[str] = []
        for img_tag in tag_list:
            if domain_name == "manga18.me":
                if img_tag.has_attr("alt") and img_tag["alt"].startswith(extra_attribute) and img_tag.has_attr("src"):
                    img_link = img_tag.get("src").strip()
                elif img_tag.has_attr("src") and "manga18.me/uploads" in img_tag["src"]:
                    img_link = img_tag.get("src").strip()

            elif domain_name == "hentai20":
                if img_tag.has_attr("src") and extra_attribute in img_tag.get("src"):
                    img_link = img_tag.get("src").strip()
            
            elif domain_name == "asuracomics":
                img_href: str = img_tag.get("href").strip()
                img_link: str = f"https://asurascans.com{img_href}"

            else:
                img_link: str = img_tag.get(src_value).strip()
            
            if not img_link.startswith("https://"): continue

            is_valid: bool = await self.validate_image_link(img_link)
            if is_valid:
                valid_links += 1
                valid_links_list.append(img_link)

        if len(valid_links_list) == len(tag_list) - 5:
            self.dev_tag('one image is invalid, continuing')
            return valid_links_list
        else:
            print(color_msg("lightgreen", f"Chapter Links Validated ({domain_name}): {valid_links}/{len(tag_list)}"))
            return valid_links_list

    async def get_dynamic_soup(self, url: str, selector: str, domain: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector(selector)
            except Exception as e:
                self.dev_tag(color_msg("yellow", f"wait_for_selector('{selector}') timed out, falling back to waiting for images..."))
            
            if domain == "hentai20":
                try:
                    await page.wait_for_function(
                        """() => {
                            const images = document.querySelectorAll('img.ts-main-image');
                            return images.length > 0;
                        }""",
                        timeout=30000
                    )
                except Exception as img_error:
                    print(color_msg("red", f"Also failed to find images: {img_error}"))
            content = await page.content()
            await browser.close()
            return BeautifulSoup(content, 'html.parser')
       
class PersistentPlaywright:
    def __init__(self, config: list[str, str]):
        self.extensions_dirpath = os.path.join(os.getcwd(), "extensions")
        self.path_to_anti_debug_extension = os.path.join(self.extensions_dirpath, "anti_anti_debug_chrome")
        self.path_to_user_data = os.path.join(self.extensions_dirpath, "profile")

    async def scroller_html(self, my_page, my_filter: str, increment_scroll=False, link_filter: str=None):
        expected_number_of_images = await my_page.evaluate('''(selector) => {
            return document.querySelectorAll(selector).length;
        }''', my_filter)

        if increment_scroll and link_filter:
            total_height = await my_page.evaluate('document.body.scrollHeight')

            for idx in range(0, total_height, 800):
                await my_page.evaluate(f'window.scrollTo(0, {idx})')
                await my_page.wait_for_timeout(1000)

            await my_page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await my_page.wait_for_timeout(3000)
            return
        else:
            for idx in range(expected_number_of_images):
                await my_page.evaluate('''(data) => {
                    const pageDivs = document.querySelectorAll(data.selector);
                    if (pageDivs[data.index]) {
                        pageDivs[data.index].scrollIntoView({behavior: 'smooth', block: 'center'});
                    }
                }''', {"selector": filter, "index": idx})
                await my_page.wait_for_timeout(500)
            await my_page.wait_for_timeout(2000)
            return
    
    async def run_persistence_for_soup(self, url: str, filter: str="", scroll=False, increment_scroll=False, link_filter: str=None) -> BeautifulSoup:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                self.path_to_user_data,
                channel="chromium",
                headless=True,
                args=[
                    f"--disable-extensions-except={self.path_to_anti_debug_extension}",
                    f"--load-extension={self.path_to_anti_debug_extension}",
                    "--no-sandbox",
                ],
            )
            
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(8000)
            
            if scroll: 
                if increment_scroll and link_filter:
                    await self.scroller_html(my_page=page, my_filter=filter, increment_scroll=increment_scroll, link_filter=link_filter)
                else:
                    await self.scroller_html(my_page=page, my_filter=filter)
            
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            await context.close()
            return soup
        
class VRFGenerator:
    def __init__(self, keyword: str):
        self.keyword = keyword
        self.key_l = "FgxyJUQDPUGSzwbAq/ToWn4/e8jYzvabE+dLMb1XU1o="
        self.key_g = "CQx3CLwswJAnM1VxOqX+y+f3eUns03ulxv8Z+0gUyik="
        self.key_B = "fAS+otFLkKsKAJzu3yU+rGOlbbFVq+u+LaS6+s1eCJs="
        self.key_m = "Oy45fQVK9kq9019+VysXVlz1F9S1YwYKgXyzGlZrijo="
        self.key_F = "aoDIdXezm2l3HrcnQdkPJTDT8+W6mcl2/02ewBHfPzg="

        self.seed_A = "yH6MXnMEcDVWO/9a6P9W92BAh1eRLVFxFlWTHUqQ474="
        self.seed_V = "RK7y4dZ0azs9Uqz+bbFB46Bx2K9EHg74ndxknY9uknA="
        self.seed_N = "rqr9HeTQOg8TlFiIGZpJaxcvAaKHwMwrkqojJCpcvoc="
        self.seed_P = "/4GPpmZXYpn5RpkP7FC/dt8SXz7W30nUZTe8wb+3xmU="
        self.seed_k = "wsSGSBXKWA9q1oDJpjtJddVxH+evCfL5SO9HZnUDFU8="

        self.prefix_O = "l9PavRg="
        self.prefix_v = "Ml2v7ag1Jg=="
        self.prefix_L = "i/Va0UxrbMo="
        self.prefix_p = "WFjKAHGEkQM="
        self.prefix_W = "5Rr27rWd"

        self.schedule_c = (
            self.sub8(223), self.rotr8(4), self.rotr8(4), self.add8(234), self.rotr8(7),
            self.rotr8(2), self.rotr8(7), self.sub8(223), self.rotr8(7), self.rotr8(6),
        )
        self.schedule_y = (
            self.add8(19), self.rotr8(7), self.add8(19), self.rotr8(6), self.add8(19),
            self.rotr8(1), self.add8(19), self.rotr8(6), self.rotr8(7), self.rotr8(4),
        )
        self.schedule_b = (
            self.sub8(223), self.rotr8(1), self.add8(19), self.sub8(223), self.rotl8(2),
            self.sub8(223), self.add8(19), self.rotl8(1), self.rotl8(2), self.rotl8(1),
        )
        self.schedule_j = (
            self.add8(19), self.rotl8(1), self.rotl8(1), self.rotr8(1), self.add8(234),
            self.rotl8(1), self.sub8(223), self.rotl8(6), self.rotl8(4), self.rotl8(1),
        )
        self.schedule_e = (
            self.rotr8(1), self.rotl8(1), self.rotl8(6), self.rotr8(1), self.rotl8(2),
            self.rotr8(4), self.rotl8(1), self.rotl8(1), self.sub8(223), self.rotl8(2),
        )

        self.vrf_token = self.generate_VRF()
        self.search_url = f"https://mangafire.to/filter?keyword={quote(self.keyword)}&vrf={self.vrf_token}"
        
    def get_search_url(self) -> str:
        return self.search_url

    def transform(self, input, seed, prefix, schedule):
        prefix_len = len(prefix)

        out = []
        for idx, c in enumerate(input):
            if idx < prefix_len:
                out.append(prefix[idx] or 0)
            out.append(schedule[idx % 10]((c ^ seed[idx % 32]) & 255) & 255)
        return out

    def rc4(self, key, input):
        lkey = len(key)

        j = 0
        s = list(range(256))
        for i in range(256):
            j = (j + s[i] + key[i % lkey]) & 255
            s[i], s[j] = s[j], s[i]

        out = []
        i = j = 0
        for c in input:
            i = (i + 1) & 255
            j = (j + s[i]) & 255
            s[i], s[j] = s[j], s[i]
            k = s[(s[i] + s[j]) & 255]
            out.append(c ^ k)
        return out

    def add8(self, n): return lambda c: (c + n) & 255

    def sub8(self, n): return lambda c: (c - n + 256) & 255

    def xor8(self, n): return lambda c: (c ^ n) & 255

    def rotl8(self, n): return lambda c: ((c << n) | (c >> (8 - n))) & 255

    def rotr8(self, n): return lambda c: ((c >> n) | (c << (8 - n))) & 255

    def generate_VRF(self):
        input = quote(self.keyword).encode()
        
        for key_b64, seed_b64, prefix_b64, schedule in (
            (self.key_l, self.seed_A, self.prefix_O, self.schedule_c),
            (self.key_g, self.seed_V, self.prefix_v, self.schedule_y),
            (self.key_B, self.seed_N, self.prefix_L, self.schedule_b),
            (self.key_m, self.seed_P, self.prefix_p, self.schedule_j),
            (self.key_F, self.seed_k, self.prefix_W, self.schedule_e),
        ):
            input = self.transform(
                self.rc4(binascii.a2b_base64(key_b64), input),
                binascii.a2b_base64(seed_b64),
                binascii.a2b_base64(prefix_b64),
                schedule,
            )
        
        return binascii.b2a_base64(bytes(input), newline=False).rstrip(
            b"=").replace(b"+", b"-").replace(b"/", b"_").decode()

class Archivist:
    def __init__(self, webhook_url: str):
        self.webhook_url: str = webhook_url
        self.intents = discord.Intents.default()
        self.intents.message_content = True
        self.intents.messages = True
        self.bot = commands.Bot(command_prefix="!", intents=self.intents)
        self.bot_channel = "comic-scraper"
    
    async def run_main_file(self, ctx):
        self.output_channel = ctx.channel
        await ctx.send("Starting main.py")
        process = await asyncio.create_subprocess_exec(
            sys.executable, "main.py", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=os.path.dirname(os.path.abspath(__file__))
        )
        self.current_process = process
        async def read_output(pipe):
            while True:
                line = await pipe.readline()
                if not line:
                    break
                line = line.decode().strip()
                if line:
                    if len(line) > 1900:
                        line = line[:1900] + "..."
                    await ctx.send(f"```\n{line}\n```")
                    
        await asyncio.gather(
            read_output(process.stdout),
            read_output(process.stderr)
        )
        return_code = await process.wait()
        if return_code == 0:
            await ctx.send("✅ Comic downloader completed successfully!")
        else:
            await ctx.send(f"❌ Comic downloader failed with exit code: {return_code}")
        
    
    def notify_new_chapter(self, message: str):
        embed = {
            "title": "New Chapter",
            "description": message,
            "color": 0x00ff00,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Archivist Updating..."
            }
        }
        data = {
            "embeds": [embed]
        }
        response = requests.post(self.webhook_url, data=json.dumps(data), headers={ "Content Type": "application/json" })
        response.raise_for_status()
        return True

    def notify(self, content):
        response = requests.post(
            self.webhook_url,
            data=json.dumps({"content": content}),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return True


""" Domains """
class Template(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name
        self.protocol: str = "https://protocol.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "template_domain")
        # if needed
        self.comic_uid = self.given_config[2]
        self.release_day = self.given_config[3]
        self.is_completed = self.given_config[4]

        self.comic_url: str = f""
        self.comic_template_url: str = f""
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"]
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "template_domain", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")
    
        comic_soup_name: str = ""

        comic_cover_img_link: str = ""
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = "ongoing"

        chapters_list: list[str] = []
        first_chapter: str = ""
        latest_chapter: str = ""

        print(comic_soup_name)
        print(comic_cover_img_link)
        print(comic_status)
        print(chapters_list)
        print(first_chapter)
        print(latest_chapter)

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list
    
    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        backup_url: str = ""
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        if chapter_soup is None and backup_url:
            chapter_soup = await self.get_soup(backup_url)
        
        validated_chapter_links: list[str] = []
        img_tags = chapter_soup.find_all("img")
        for img_tag in img_tags:
            if img_tag.has_attr("alt") and img_tag.has_attr("src"):
                img_link = img_tag.get("src").strip()
                is_valid: bool = await self.validate_image_link(img_link)
                if is_valid:
                    validated_chapter_links.append(img_link)
        return validated_chapter_links

class Manga18(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.comic_name = comic_name
        self.protocol: str = "https://manga18.me"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "manga18")
        self.comic_url: str = f"https://manga18.me/manga/{self.url_comic_name}"
        self.comic_template_url: str = f"https://manga18.me/manga/{self.url_comic_name}/chapter-{{}}"
        self.given_config: list[str] = given_config
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"] # ongoing or completed
        self.chapters_list: list[str]   = details["chapters_list"] #reversed list
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "manga18.me", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")
        
        comic_soup_name: str = comic_soup.find("div", class_="post-title wleft").select_one("h1").text.strip()
        comic_cover_img_link: str = comic_soup.find("div", class_="summary_image").select_one("img").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="post_status").find_all("div", class_="post-content_item wleft")[1].find("div", class_="summary-content").text.lower().strip()
        chapters_list: list[str] = [tag.text.replace("Chapter", "").strip() for tag in comic_soup.find("ul", class_="row-content-chapter wleft").find_all("a", class_="chapter-name text-nowrap")]

        chapter_number_regex = re.compile(r'Chapter (\d+)')
        first_chapter: str = chapter_number_regex.search(
            comic_soup.find("a", class_="rfirst").get("title")
        ).group(1)

        latest_chapter: str = chapter_number_regex.search(
            comic_soup.find("a", class_="rlast").get("title")
        ).group(1)

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status, # ongoing or completed
            'chapters_list': list(reversed(chapters_list)),
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter
        }

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

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        # print(f'chapter_url: {comic_chapter_url}')
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        # print(color_msg("red", f"konsole
        # Running get_chapter_image_links (manga18.me): comic_soup_name: {self.comic_soup_name}"))
        chapter_alt_check: str = f"{self.comic_soup_name} - Chapter {ch_num}"
        chapter_image_tags: list[str] = chapter_soup.find("div", class_="read-content wleft").find_all('img')
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="manga18.me", src_value="src", extra_attribute=chapter_alt_check)

class Mgeko(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.comic_name: str = comic_name
        self.protocol: str = "https://www.mgeko.cc"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "mgeko")
        self.comic_url: str = f"https://www.mgeko.cc/manga/{self.url_comic_name}/"
        self.comic_template_url: str = f"https://www.mgeko.cc/reader/en/{self.url_comic_name}-chapter-{{}}-eng-li/"

        self.backup_template_url: str = ""
        # extras
        if self.url_comic_name == "leviathan":
            self.comic_url: str = f"https://www.mgeko.cc/manga/leviathansdads/"
            self.backup_template_url: str = f"https://www.mgeko.cc/reader/en/leviathansdads-chapter-{{}}-eng-li"
            
        self.comic_all_chaps_url: str = f"{self.comic_url}all-chapters/"
        self.given_config: list[str] = given_config
        self.panel_tag(f'{color_msg('yellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('yellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        print(f'self.comic_all_chaps_url: {self.comic_all_chaps_url}')
        self.panel_tag(f'{color_msg('yellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.chapters_list: list[str] = await self.find_chapters_list() #reversed list
        self.generated_config: list[str] = [self.comic_soup_name, "mgeko", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)


        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')
            print(f'chapters_list: {self.chapters_list}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")
        
        comic_soup_name: str = comic_soup.find("h1", class_="novel-title text2row").text.strip()
        comic_cover_img_link: str = comic_soup.find("div", class_="fixed-img").find("figure", class_="cover").select_one("img").get("data-src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="header-stats").find_all("span")[3].select_one("strong").text.lower().strip()
        chapter_number_regex = re.compile(r'Chapter (\d+)-eng-li')
        first_chapter: str = chapter_number_regex.search(comic_soup.find("a", id="readchapterbtn").get("title")).group(1)
        latest_chapter: str = comic_soup.find("div", class_="header-stats").find_all("span")[0].select_one("strong").get_text().replace("book", "").replace("-eng-li", "").strip()

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter,
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    async def find_chapters_list(self) -> list[str]:
        all_chaps_soup = await self.get_soup(self.comic_all_chaps_url)
        print(f'all chaps url: {self.comic_all_chaps_url}')

        chapters_list: list[str] = [tag.get_text().replace("-eng-li", "").strip() for tag in all_chaps_soup.find("ul", class_="chapter-list").find_all("strong", class_="chapter-title")]
        return list(reversed(chapters_list))

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list

    def get_cover_img_link(self) -> str:
        return self.comic_cover_img_link

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        primary_url = self.comic_template_url.format(ch_num)
        backup_url = (
            self.backup_template_url.format(ch_num)
            if self.backup_template_url
            else None
        )

        chapter_soup: BeautifulSoup = await self.get_soup(primary_url)
        if chapter_soup is None and backup_url:
            chapter_soup = await self.get_soup(backup_url)

        chapter_image_tags: list[str] = [tag for tag in chapter_soup.find("div", id="chapter-reader").find_all("img") if tag.has_attr("id") and tag["id"].startswith("image-")]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="mgeko", src_value="src")

class Manhuaus(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.comic_name: str = comic_name
        self.protocol: str = "https://manhuaus.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "manhuaus")
        if self.comic_name == "Super God Card Maker":
            self.url_comic_name = "super-god-card-maker-1"
        self.comic_url: str = f"https://manhuaus.com/manga/{self.url_comic_name}/"
        self.comic_template_url: str = f"https://manhuaus.com/manga/{self.url_comic_name}/chapter-{{}}/"
        self.given_config: list[str] = given_config
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"] #reversed list
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "manhuaus", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")

        comic_soup_name: str = comic_soup.find("div", class_="post-title").select_one("h1").text.strip()
        comic_cover_img_link: str = comic_soup.find("div", class_="summary_image").select_one("img").get("data-src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="post-status").find("div", class_="summary-content").text.lower().strip()
        chapters_found: list[str] = [atag.find("a").get_text().lower().replace("chapter", "").strip() for atag in comic_soup.find_all("li", class_="wp-manga-chapter")]
        first_chapter: str = chapters_found[-1]
        latest_chapter: str = chapters_found[0]

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': list(reversed(chapters_found)),
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter,
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list

    def get_cover_img_link(self) -> str:
        return self.comic_cover_img_link

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        chapter_image_tags: list[str] = [tag for tag in chapter_soup.find("div", class_="reading-content").find_all("img") if tag.has_attr("id") and tag["id"].startswith("image-")]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="yakshascans", src_value="data-src")

class Yakshascans(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.comic_name: str = comic_name
        self.protocol: str = "https://yakshascans.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "yakshascans")
        self.comic_url: str = f"https://yakshascans.com/manga/{self.url_comic_name}/"
        self.comic_template_url: str = f"https://yakshascans.com/manga/{self.url_comic_name}/chapter-{{}}/"
        self.given_config: list[str] = given_config
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"] #reversed list
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "yakshascans", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")

        comic_soup_name: str = comic_soup.find("div", class_="post-title").select_one("h1").text.strip()
        comic_cover_img_link: str = comic_soup.find("div", class_="summary_image").find("img").get("data-src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="summary_content").find("div", class_="post-status").find("div", class_="summary-content").text.lower().strip()
        chapters_found: list[str] = [tag.find("a").text.replace("Chapter", "").strip() for tag in comic_soup.find_all("li", class_="wp-manga-chapter")]
        first_chapter: str = chapters_found[-1]
        latest_chapter: str = chapters_found[0]

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': list(reversed(chapters_found)),
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter,
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list

    def get_cover_img_link(self) -> str:
        return self.comic_cover_img_link

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        # print(f'chapter_url: {comic_chapter_url}')
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        chapter_image_tags: list[str] = [tag for tag in chapter_soup.find("div", class_="reading-content").find_all("img") if tag.has_attr("id") and tag["id"].startswith("image-")]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="yakshascans", src_value="data-src")

class Ravenscans(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.comic_name: str = comic_name
        self.protocol: str = "https://ravenscans.org"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "ravenscans")
        self.comic_url: str = f"{self.protocol}/manga/{self.url_comic_name}/"
        self.comic_template_url: str = f"{self.protocol}/{self.url_comic_name}-chapter-{{}}/"
        self.given_config: list[str] = given_config
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"]
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "ravenscans", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")

        comic_soup_name: str = comic_soup.find("h1", class_="entry-title").get_text(strip=True)
        comic_cover_img_link: str = comic_soup.find("img", class_="attachment- size- wp-post-image").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="imptdt").find("i").get_text(strip=True).lower()

        chapters_list: list[str] = list(reversed([tag.get_text(strip=True).lower().replace("chapter", "").strip() for tag in comic_soup.find("div", id="chapterlist").find_all("span", class_="chapternum")]))
        first_chapter: str = chapters_list[0]
        latest_chapter: str = chapters_list[-1]

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter,
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list

    def get_cover_img_link(self) -> str:
        return self.comic_cover_img_link

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        if not chapter_soup: chapter_soup = await self.get_dynamic_soup(url=comic_chapter_url, selector="#readerarea", domain="ravenscans")
        chapter_image_tags: list[str] = [tag for tag in chapter_soup.find("div", id="readerarea").find_all("img")]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="ravenscans", src_value="src")

class Manhwabuddy(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.comic_name: str = comic_name
        self.protocol: str = "https://manhwabuddy.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "manhwabuddy")
        self.comic_url: str = f"https://manhwabuddy.com/manhwa/{self.url_comic_name}/"
        self.comic_template_url: str = f"https://manhwabuddy.com/manhwa/{self.url_comic_name}/chapter-{{}}/"
        self.given_config: list[str] = given_config
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"] #reversed list
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "manhwabuddy", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)
            
        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")

        comic_soup_name: str = comic_soup.find("h1", class_="main-info-title title-bigger").text.strip()
        comic_cover_img_link: str = comic_soup.find("img", class_="img-cover").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="post-status").find_all("li")[1].find("span").get_text().lower().strip()
        chapters_list: list[str] = [tag.find("span", class_="chapter-name").text.replace("Chapter", "").strip() for tag in comic_soup.find("ul", class_="chapter-list").find_all("li", class_="myfut")]
        first_chapter: str = chapters_list[-1]
        latest_chapter: str = chapters_list[0]

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': list(reversed(chapters_list)),
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter,
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list

    def get_cover_img_link(self) -> str:
        return self.comic_cover_img_link

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        # print(f'chapter_url: {comic_chapter_url}')
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        chapter_image_tags: list[str] = chapter_soup.find("div", class_="reading-content").find_all("img")
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="manhwabuddy", src_value="data-src")

class Pornhwa(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.comic_name: str = comic_name
        self.protocol: str = "https://pornhwa.me"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "pornhwa")
        self.comic_url: str = f"https://pornhwa.me/read/{self.url_comic_name}/"
        self.comic_template_url: str = f"https://pornhwa.me/read/{self.url_comic_name}/chapter-{{}}/"
        self.given_config: list[str] = given_config
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"] #reversed list
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "pornhwa.me", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')
    
    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")

        comic_soup_name: str = comic_soup.find("h1", class_="px-1 text-2xl text-left font-bold mb-5").text.strip()
        comic_cover_img_link: str = comic_soup.find("img", class_="w-32 h-full mx-auto border-4 border-solid border-slate-800 dark:border-white unset md:w-full md:border-8").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="overflow-hidden grid grid-cols-1 gap-4 text-left leading-7 mb-6").find_all("span")[1].get_text().lower().strip()
        chapters_list: list[str] = [tag.text.replace("Chapter", "").strip() for tag in comic_soup.find("ul", id="chapter-list", class_="overflow-hidden pl-1 pr-1.5 grid md:grid-cols-2 gap-2").find_all("span") if "Chapter" in tag.text]
        first_chapter: str = chapters_list[-1]
        latest_chapter: str = chapters_list[0]

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': list(reversed(chapters_list)),
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter,
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list

    def get_cover_img_link(self) -> str:
        return self.comic_cover_img_link

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        chapter_image_tags: list[str] = [tag for tag in chapter_soup.find("div", id="bacaArea").find_all("img", class_="mx-auto") if tag.get("src") != "/banner.jpg"]
        valid_links = await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="pornhwa.me", src_value="src")
        # self.dev_tag(f'len(valid_links): {len(valid_links)}')
        return valid_links

class Hentai20(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.comic_name: str = comic_name
        self.protocol: str = "https://hentai20.io"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "hentai20")
        self.url_comic_name = self.url_comic_name.replace("teacher-s-", "teachers-")
        self.comic_url: str = f"https://hentai20.io/manga/{self.url_comic_name}/"
        self.comic_template_url: str = f"https://hentai20.io/{self.url_comic_name}-chapter-{{}}/"
        self.given_config: list[str] = given_config
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"] #reversed list
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "hentai20", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')
        
    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")

        comic_soup_name: str = comic_soup.find("h1", class_="entry-title").get_text().strip()

        comic_cover_img_link: str = comic_soup.find("img", class_="attachment- size- wp-post-image").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("table", class_="infotable").find_all("tr")[0].find_all("td")[1].text.lower().strip()
        chapters_list: list[str] = [tag.text.replace("Chapter", "").strip() for tag in comic_soup.find("div", id="chapterlist").find_all("span", class_="chapternum")]
        first_chapter: str = chapters_list[-1]
        latest_chapter: str = chapters_list[0]

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': list(reversed(chapters_list)),
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter,
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list

    def get_cover_img_link(self) -> str:
        return self.comic_cover_img_link

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        # print('running Hentai20.get_chapter_image_links()')
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        if ch_num == "0" and self.comic_name.lower().strip() != "ground and pound":
            ch_num = "0-prologue"
            comic_chapter_url = self.comic_template_url.format(ch_num)

        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        if not chapter_soup:
            self.dev_tag('used dynamic soup')
            chapter_soup = await self.get_dynamic_soup(url=comic_chapter_url, selector="#readerarea", domain="hentai20")

        # self.dev_tag(f"chapter_soup?: {"True" if chapter_soup else "False"}")
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
        valid_links = await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="hentai20", src_value="src", extra_attribute=temp_url_name)
        return valid_links

class AsuraComics(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, series_url: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.given_config: list[str] = given_config
        self.generated_config: list[str] = []
        self.comic_name: str = comic_name
        self.protocol: str = "https://asurascans.com/"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "asuracomics")
        self.series_url = series_url
        if self.series_url == "":
            self.comic_search_result: list[str] = self.search_asura(comic_name)
            self.comic_name: str = self.comic_search_result[0]
            self.comic_url: str = self.comic_search_result[1]
        else:
            self.comic_url: str = self.series_url
        self.comic_uid: str = self.extract_comic_uid_asura(self.series_url)
        self.comic_template_url: str = f"{self.comic_url}/chapter/{{}}/"
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str = details["soup_name"]
        self.comic_cover_img_link: str = details["cover_img_link"]
        self.comic_status: str = details["status"]
        self.chapters_list: list[str] = details["chapters_list"]
        self.first_chapter: str = details["first_chapter"]
        self.latest_chapter: str = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "asuracomics", self.comic_uid, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")
        
        comic_soup_name: str = comic_soup.find("h1", class_="text-xl lg:text-[32px] font-semibold leading-tight").text.strip()

        comic_cover_img_link: str = comic_soup.find("div", class_="rounded-xl z-0 w-full h-full absolute top-0 left-0").find("img").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("span", class_="text-base font-bold text-[#A78BFA] capitalize").get_text(strip=True).lower().strip()
        
        chapter_wrapper = comic_soup.find("div", class_="max-h-[500px] overflow-y-auto")
        premium_chapter: str = chapter_wrapper.find("div", class_="flex items-center gap-3 min-w-0 flex-1").find("span", class_="font-medium transition-colors text-white group-hover:text-[#913FE2]").get_text().lower().replace("chapter", "").strip()
        non_premium_chapters = list(reversed([tag.find("span", class_="font-medium transition-colors text-white group-hover:text-[#913FE2]").get_text(strip=True).lower().replace("chapter", "").strip() for tag in chapter_wrapper.find("div", class_="divide-y divide-white/5").find_all("a", class_="group flex items-center justify-between px-4 py-4 transition-colors hover:bg-white/5")]))
        chapters_list = [ch for ch in non_premium_chapters if ch != premium_chapter]
        first_chapter: str = chapters_list[0]
        latest_chapter: str = chapters_list[-1]

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter,
        }

    def has_unicode(self, giv_str: str) -> bool:
        return True if "\u2019" in giv_str or "\u2026" in giv_str else False

    def find_query_part(self, query: str) -> str:
        query_parts = query.split(' ')
        len_parts = len(query_parts)
        unicode_idx = -1
        for idx, part in enumerate(query_parts, 0):
            if self.has_unicode(part):
                unicode_idx = idx

        if unicode_idx > -1:
            if unicode_idx == 0:
                return '%20'.join(query_parts[1:])
            elif unicode_idx == len_parts:
                return '%20'.join(query_parts[:-1])
            else:
                before_unicode = query_parts[:unicode_idx]
                after_unicode = query_parts[unicode_idx+1:]
                if len(before_unicode) > len(after_unicode):
                    return '%20'.join(before_unicode)
                else:
                    return '%20'.join(after_unicode)

    def search_asura(self, query_comic_name: str) -> dict: 
        lowered_query = query_comic_name.lower().strip()
        clean_query = query_comic_name.replace("'", "\u2019")
        domain_protocol: str = "https://asurascans.com"
        search_protocol: str = "https://asurascans.com/browse?search={}"
        has_unicode_element: bool = self.has_unicode(clean_query)
        search_query = query_comic_name.replace(" ", "%20")
        if has_unicode_element:
            search_query = self.find_query_part(clean_query)
        
        self.dev_tag(f'search asura query: {search_query}')
        self.dev_tag(f'search url: {search_protocol.format(search_query.lower().strip())}')
        response = requests.get(search_protocol.format(search_query.lower().strip()), headers=self.headers)
        if response.status_code != 200:
            self.dev_tag('not 200')
            return
        
        search_results_soup = BeautifulSoup(response.content, 'html.parser')
        results_wrapper = search_results_soup.find("div", id="series-grid-container")
        first_result = results_wrapper.find("div", class_="series-card group bg-[#1f1a2e] rounded-lg overflow-hidden transition-all duration-200 hover:ring-2 hover:ring-[#913FE2] hover:shadow-lg hover:shadow-[#913FE2]/20")

        comic_title: str = first_result.find("h3", class_="text-sm font-semibold text-white line-clamp-1 group-hover:text-[#913FE2] transition-colors").get_text(strip=True)
        comic_series_link: str = f"{self.protocol}{first_result.find("a", class_="block relative aspect-[3/4] overflow-hidden").get('href').strip()}"
        return [comic_title, comic_series_link]

    def extract_comic_uid_asura(self, link: str) -> str:
        last_part_of_link = link.split("/")[-1]
        link_uid = last_part_of_link.split("-")[-1]
        return link_uid

    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list

    def get_cover_img_link(self) -> str:
        return self.comic_cover_img_link

    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)

        img_links = await self.get_images_playwright_scroll(
            chapter_url=comic_chapter_url,
            regex_filter=r'^(0{2,5}|0\d\d|00\d|0\d{1,4}|\d{2,5}|0\d|\d{2}|[A-Za-z0-9]{6})\.webp$',
            link_filter="/chapters/",
            img_element_filter="cdn.asurascans.com",
            file_ext=".webp"
        )
        return img_links

class FlameComics(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, comic_id: int, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.comic_name: str = comic_name
        self.protocol: str = "https://flamecomics.xyz"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "flamecomics")
        self.comic_id: int = comic_id
        self.comic_url: str = f"{self.protocol}/series/{self.comic_id}"
        self.chapter_links_list = []
        self.given_config: list[str] = given_config
        self.panel_tag(f'{color_msg('yellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('yellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
    
    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.chapters_links_list: list[str]   = details["chapters_link_list"] #reversed list
        self.chapters_list: list[str] = details['chapters_list']
        self.generated_config: list[str] = [self.comic_soup_name, "flamecomics", self.comic_id, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)
            
    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch this comic page: {self.comic_url}")
        
        comic_info_div = comic_soup.select_one(
            "div.SeriesPage_paper__MMnBx.m_1b7284a3.mantine-Paper-root[style]"
        )
        comic_soup_name: str = comic_info_div.find("h1", class_="m_8a5d1357 mantine-Title-root").text.strip()
        comic_cover_img_element = comic_soup.find("img", class_="SeriesPage_cover__cEjW-")
        comic_cover_img_link: str = self.handle_srcset(comic_cover_img_element)
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_info_div.find("span", class_="m_5add502a mantine-Badge-label").text.lower().strip()

        chapters_list_wrapper = comic_soup.select_one(
            "div.SeriesPage_paper__MMnBx.m_1b7284a3.mantine-Paper-root:not([style])"
        )
        chapters_found = chapters_list_wrapper.find_all("a", class_="ChapterCard_chapterWrapper__NIPp5 mantine-focus-auto")
        chapter_links_uid = [f"{self.protocol}{tag['href']}" for tag in chapters_found]

        chapters_list = list(reversed([tag.find("p", class_="mantine-focus-auto m_b6d8b162 mantine-Text-root").get_text(strip=True).lower().replace("chapter", "").strip() for tag in comic_soup.find("div", class_="m_c0783ff9 mantine-ScrollArea-viewport").find_all("a", class_="ChapterCard_chapterWrapper__NIPp5 mantine-focus-auto")]))
        first_chapter: str = chapters_list[0]
        latest_chapter: str = chapters_list[-1]

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_link_list': list(reversed(chapter_links_uid)),
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list

    def get_cover_img_link(self) -> str:
        return self.comic_cover_img_link
    
    async def get_chapter_links_list(self) -> list[str]:
        return self.chapters_links_list

    async def get_chapter_image_links(self, ch_num: int) -> list[str]:
        comic_chapter_url: str = ""
        if ch_num == 0:
            comic_chapter_url: str = self.chapters_links_list[ch_num]
        else:
            comic_chapter_url: str = self.chapters_links_list[ch_num-1]

        comic_chapter_soup: Optional[BeautifulSoup] = await self.get_soup(comic_chapter_url)
        img_tags = comic_chapter_soup.find_all("img")
        chapter_image_tags = [tag for tag in img_tags if tag and tag.has_attr("src") and tag["src"].startswith("https://cdn.flamecomics.xyz/uploads/images/series")]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="flamecomics", src_value="src")

class OmegaScans(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.comic_name: str = comic_name
        self.protocol: str = "https://omegascans.org"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "omegascans")
        self.comic_url: str = f"{self.protocol}/series/{self.url_comic_name}"
        self.comic_template_url: str = f"{self.comic_url}/chapter-{{}}"
        self.given_config: list[str] = given_config
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')
    
    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"] #reversed list
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.release_day: str = details["release_day"]
        self.generated_config: list[str] = [self.comic_soup_name, "omegascans", 0, self.release_day, True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            if not comic_soup:
                raise ValueError(f"Failed to fetch comic page: {self.comic_url}")
    
        comic_soup_name: str = comic_soup.find("div", id="content").find("h1", class_="text-xl md:text-3xl text-foreground font-bold text-center lg:text-left inline").text.strip()

        comic_cover_img_element = comic_soup.find("img", class_="w-full bg-muted/40 h-[500px] sm:h-[720px] md:h-[530px] lg:w-full lg:h-[320px] xl:h-[430px] 2xl:h-[450px] rounded")
        comic_cover_img_link: str = self.handle_srcset(comic_cover_img_element)
        await self.process_cover_image(comic_cover_img_link)

        comic_tags_wrapper = comic_soup.find("div", class_="flex flex-row flex-wrap gap-2")
        comic_tags: list[str] = [tag.text.lower().strip() for tag in comic_tags_wrapper.find_all("span")]
        comic_status: str = "ongoing"
        if not "ongoing" in comic_tags:
            comic_status = "completed"

        release_day_wrapper = comic_soup.find("div", class_="flex items-center justify-center gap-1")
        if not release_day_wrapper:
            release_day: str = "everyday"
        else:
            buttons_available = release_day_wrapper.find_all("button")
            active_button_idx = 0
            for i, button in enumerate(buttons_available):
                if button.get('data-state') == 'on':
                    active_button_idx = i
                    break
            days_of_the_week = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
            release_day: str = days_of_the_week[active_button_idx]

        comic_soup = await self.get_dynamic_soup(self.comic_url, selector=".space-y-4", domain="omegascans")
        chapter_wrapper = comic_soup.find("ul", class_="grid grid-cols-1 gap-y-3")
        if not chapter_wrapper:
            print('not chapter_wrapper')
            return
        chapters_list = list(reversed([tag.find("span", class_="m-0 text-[1rem] line-clamp-1 lg:max-w-none").get_text(strip=True).lower().replace("chapter", "").strip() for tag in chapter_wrapper.find_all("a", class_="text-foreground visited:text-[rgb(79,0,225)]")]))
        first_chapter: str = chapters_list[0]
        latest_chapter: str = chapters_list[-1]

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter,
            'release_day': release_day
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list

    def get_cover_img_link(self) -> str:
        return self.comic_cover_img_link

    def get_release_day(self) -> str:
        return self.release_day
    
    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        backup_url: str = ""
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        if chapter_soup is None and backup_url:
            chapter_soup = await self.get_soup(backup_url)
        
        img_tags = chapter_soup.find_all("img")
        chapter_image_tags = [tag for tag in img_tags if tag.has_attr("src") and tag["src"].startswith("https://media.omegascans.org/file/")]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="omegascans", src_value="src")

class KingOfShojo(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.comic_name: str = comic_name
        self.protocol: str = "https://kingofshojo.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "kingofshojo")
        self.comic_url: str = f"{self.protocol}/manga/{self.url_comic_name}/"
        self.comic_template_url: str = f"{self.protocol}/{self.url_comic_name}-chapter-{{}}"
        self.given_config: list[str] = given_config
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"]
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "kingofshojo", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')
                
    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")

        comic_soup_name: str = comic_soup.find("h1", class_="entry-title").text.strip()
        
        comic_cover_img_link: str = comic_soup.find("img", class_="attachment- size- wp-post-image").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        latest_updated_chapter_dtobj = dt.datetime.strptime(comic_soup.find("div", id="chapterlist").find("li").find("span", class_="chapterdate").text.strip(), "%B %d, %Y").date()
        is_recent: bool = self.is_recently_updated(latest_updated_chapter_dtobj)
        if is_recent:
            comic_status: str = "ongoing"
        else:
            comic_status: str = "completed"
        comic_status = "ongoing"
        
        chapters_list: list[str] = list(reversed([li_tag.get("data-num") for li_tag in comic_soup.find("div", id="chapterlist").find_all("li")]))
        first_chapter: str = chapters_list[0]
        latest_chapter: str = chapters_list[-1]

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

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list
 
    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        backup_url: str = ""
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        if chapter_soup is None and backup_url:
            chapter_soup = await self.get_soup(backup_url)

        img_tags = chapter_soup.find_all("img")
        chapter_image_tags = [tag for tag in img_tags if tag.has_attr("title") and tag["title"].strip().startswith(f"{self.comic_soup_name.strip()} Chapter {ch_num}") and tag.has_attr("src")]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="kingofshojo", src_value="src")

class MangaKatana(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
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

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"]
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "mangakatana", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")
        
        comic_soup_name: str = comic_soup.find("div", class_="info").find("h1", class_="heading").text.strip()

        comic_cover_img_link: str = comic_soup.find("div", class_="d-cell-medium media").find("img", alt="[Cover]").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="d-cell-small value status ongoing").get_text(strip=True).lower()

        chapters_list_wrapper = comic_soup.find("table", class_="uk-table uk-table-striped").find_all("div", class_="chapter")
        chapters_list = list(reversed([tag.find("a").get("href").split("/")[-1].replace("c", "") for tag in chapters_list_wrapper]))
        first_chapter: str = chapters_list[0]
        latest_chapter: str = chapters_list[-1]

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

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list
    
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
        
class Toonily(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name
        self.protocol: str = "https://toonily.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "toonily")

        self.comic_url: str = f"{self.protocol}/serie/{self.url_comic_name}"
        self.comic_template_url: str = ""
        self.panel_tag(f'{color_msg('yellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('yellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.comic_uid: str             = details["comic_uid"]
        self.chapters_list: list[str]   = details["chapters_list"]
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        
        self.comic_url: str = f"{self.protocol}/serie/{self.url_comic_name}-{self.comic_uid}"
        self.comic_template_url: str = f"{self.protocol}/serie/{self.url_comic_name}-{self.comic_uid}/chapter-{{}}/"
        
        self.generated_config: list[str] = [self.comic_soup_name, "toonily", self.comic_uid, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        print(f'Updated comic_url: {self.comic_url}')
        print(f'comic_template_url: {self.comic_template_url}')
        
        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")
    
        comic_soup_name: str = comic_soup.find("div", class_="post-title").find("h1").get_text(strip=True)

        comic_cover_img_link: str = comic_soup.find("div", class_="summary_image").find("img").get("src").strip()

        comic_real_link: str = comic_soup.find("div", class_="summary_image").find("a").get("href").strip()
        comic_uid: str = comic_real_link[:-1].split("/")[-1].split("-")[-1].strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="post-status").find_all("div", class_="summary-content")[-1].text.lower().strip()

        chapters_list_wrapper = comic_soup.find("ul", class_="main version-chap no-volumn").find_all("a")
        chapters_list: list[str] = list(reversed([tag.text.lower().replace("chapter", "").strip() for tag in chapters_list_wrapper]))
        first_chapter: str = chapters_list[0]
        latest_chapter: str = chapters_list[-1]

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'comic_uid': comic_uid,
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list
    
    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        print('running toonily get_chapter_image_links()')
        print(self.comic_uid)
        print(f'chapter_number: {ch_num}')
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        print(f'comic_chapter_url: {comic_chapter_url}')

        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        
        img_tags = chapter_soup.find_all("img")
        chapter_image_tags = [tag for tag in img_tags if tag.has_attr("id") and tag["id"].startswith("image-") and tag.has_attr("src") and "data.tnlycdn.com" in tag["src"]]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="toonily", src_value="src")

class MangaFire(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name
        self.protocol: str = "https://mangafire.to"
        self.series_url: str = ""
        self.persistent_instance = PersistentPlaywright(given_config)
        self.comic_language: str = "en"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "mangafire")
        # if needed
        self.comic_uid = self.given_config[2]
        self.release_day = self.given_config[3]
        self.is_completed = self.given_config[4]

    async def get_comic_url(self):
        search_url_name: str = self.comic_name.lower().strip()
        search_url: str = VRFGenerator(search_url_name).get_search_url()
        search_soup = await self.persistent_instance.run_persistence_for_soup(url=search_url) 
        first_result = search_soup.find("div", class_="original card-lg").find("div", class_="inner")
        comic_url: str = self.protocol + first_result.find("a", class_="poster").get("href").strip()
        return comic_url

    async def initialize(self):
        self.comic_url: str = await self.get_comic_url()

        self.comic_template_url: str = f"{self.comic_url.replace("/manga/", "/read/")}/{self.comic_language}/chapter-{{}}"
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"]
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "mangafire", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.persistent_instance.run_persistence_for_soup(self.comic_url)

        details_wrapper = comic_soup.find("div", class_="main-inner")

        comic_soup_name: str = details_wrapper.find("div", class_="info").find("h1").text.strip()

        comic_cover_img_link: str = details_wrapper.find("div", class_="poster").find("img", alt=self.given_config[0]).get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status_text: str = details_wrapper.find("div", class_="info").find("p").text.lower().strip()
        comic_status: str = "ongoing" if comic_status_text == "releasing" else "completed"

        chapters_list_tags: list[str] = comic_soup.find("ul", class_="scroll-sm").find_all("a")
        unreversed_chapters_list: list[str] = []
        for tag in chapters_list_tags:
            tag_title = tag.get("title")
            num_search = re.search(r"Chap (\d+)", tag_title)
            if num_search:
                unreversed_chapters_list.append(num_search.group(1))

        chapters_list = list(reversed(unreversed_chapters_list))
        
        first_chapter: str = chapters_list[0]
        latest_chapter: str = chapters_list[-1]

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list
    
    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        chapter_soup: BeautifulSoup = await self.persistent_instance.run_persistence_for_soup(comic_chapter_url, filter="div.page.fit-w", scroll=True)
        
        img_tags = chapter_soup.select('div.img.loaded img.fit-w')
        chapter_image_tags = [tag for tag in img_tags if tag.has_attr("src") and "mfcdn1.xyz/mf" in tag["src"]]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="mangafire", src_value="src")

class VortexScans(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name
        self.protocol: str = "https://vortexscans.org"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "vortexscans")
        self.weird_url_comic_name: str = self.url_comic_name.replace("%3A", ":")
        # if needed
        self.comic_uid = self.given_config[2]
        self.release_day = self.given_config[3]
        self.is_completed = self.given_config[4]

        self.comic_url: str = f"{self.protocol}/series/{self.url_comic_name}"
        self.comic_template_url: str = f"{self.protocol}/series/{self.weird_url_comic_name}/chapter-{{}}"
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"]
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "vortexscans", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")
    
        comic_soup_name_element = comic_soup.find("h1", class_="text-2xl font-bold text-foreground leading-[1.5rem]")

        comic_cover_img_link_element = comic_soup.find("img", class_="w-full rounded-lg object-cover object-bottom sm:max-h-[400px] h-auto transition-transform duration-300 group-hover:scale-105")

        comic_cover_img_link: str = comic_cover_img_link_element.get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        # for getting comic_soup_name
        if not comic_soup_name_element:
            if comic_cover_img_link_element:
                comic_soup_name: str = comic_cover_img_link_element.get("alt").strip()
            else:
                raise ValueError("could not find comic_soup_name through comic_cover_img_link_element")
        else: 
            comic_soup_name: str = comic_soup_name_element.get_text(strip=True)

        comic_status = comic_soup.find("div", class_="text-foreground").find("div", class_="flex sm:justify-between justify-start items-center gap-2").find("p", class_="font-normal text-xs inline ml-1 text-foreground").text.lower().strip()

        first_chapter_str = comic_soup.find("div", class_="hidden sm:block").find("a").get("href").split("/")[-1].lower().strip()
        first_chapter_search = re.search(r"\d+", first_chapter_str)
        first_chapter: str = first_chapter_search.group(0).strip()

        loaded_chapters_list = list(reversed([tag.get_text(strip=True).lower().replace('chapter', '').strip() for tag in comic_soup.find_all("span", class_="text-xs sm:text-sm font-medium")]))
        available_latest_chapter = loaded_chapters_list[-1]

        chapter_divs = comic_soup.find_all("div", class_="w-full h-full flex items-center justify-between gap-2 sm:gap-3")
        all_chapters = [str(idx) for idx in range(int(first_chapter), int(available_latest_chapter)+1)]
        premium_chaps = []
        for chapter_div in chapter_divs:
            premium_cost = chapter_div.find("span", class_="font-medium text-xs sm:text-sm")
            if premium_cost:
                ch_num = chapter_div.find("span", class_="text-xs sm:text-sm font-medium").get_text(strip=True).lower().replace("chapter", "").strip()
                premium_chaps.append(ch_num)
        
        non_premium_chaps = [ch for ch in all_chapters if ch not in premium_chaps]
        latest_chapter = non_premium_chaps[-1]

        # self.dev_tag(f'first_chapter: {first_chapter}')
        # self.dev_tag(f'available_latest_chapter: {available_latest_chapter}')
        # self.dev_tag(f'all_chapters: {all_chapters}')
        # self.dev_tag(f'premium_chaps: {premium_chaps}')
        # self.dev_tag(f'non_premium_chaps: {non_premium_chaps}')
        # self.dev_tag(f'latest_chapter: {latest_chapter}')
        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': non_premium_chaps,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter
        }

    async def get_chapter_links_list(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-dev-shm-usage', '--no-sandbox'],
            )
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(self.comic_url, wait_until="networkidle")

            button_selector = 'button.group.flex.w-full.items-center.justify-center.gap-2.rounded-xl.bg-gray-200\\/80.px-5.py-3.text-sm.font-medium.text-gray-700.transition-all.duration-200.hover\\:bg-gray-300\\/80.dark\\:bg-white\\/10.dark\\:text-gray-300.dark\\:hover\\:bg-white\\/15'
            await page.wait_for_selector(button_selector, state="visible", timeout=10000)
            await page.click(button_selector)
            await asyncio.sleep(1)

            wrapper_selector = 'div.mt-4.space-y-2'
            wrapper = await page.query_selector(wrapper_selector)
            chapter_links = []

            if wrapper:
                link_selector = 'a.flex.w-full.items-center.text-left.justify-between.text-gray-900.dark\\:text-white.visited\\:\\!text-gray-500.min-w-0'
                chapter_divs = await wrapper.query_selector_all(link_selector)

                for chapter_div in chapter_divs:
                    chapter_href = await chapter_div.get_attribute('href')
                    if chapter_href:
                        chapter_link = f"https://vortexscans.org{chapter_href.strip()}"
                        chapter_links.append(chapter_link)
            await browser.close()
            # if latest_chapter is not None and len(chapter_links) == latest_chapter:
            #     print('chapter count matches')
            return chapter_links
        
    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter
  
    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list
    
    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        
        img_tags = chapter_soup.find("div", class_="comic-images-wrapper").find_all("img")
        chapter_image_tags = [tag for tag in img_tags if tag.has_attr("alt") and tag.has_attr("src") and tag["src"].startswith("https://storage.vexmanga.com/public/")]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="vortexscans", src_value="src")
  
class UToon(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name
        self.protocol: str = "https://utoon.net"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "utoon")
        # if needed
        self.comic_uid = self.given_config[2]
        self.release_day = self.given_config[3]
        self.is_completed = self.given_config[4]

        self.comic_url: str = f"{self.protocol}/manga/{self.url_comic_name}"
        self.comic_template_url: str = f"{self.comic_url}/chapter-{{}}"
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"]
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "utoon", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")
    
        comic_soup_name: str = comic_soup.find("div", class_="c-breadcrumb-wrapper").find_all("a")[-1].get_text(strip=True)

        comic_cover_img_link: str = comic_soup.find("div", class_="summary_image").find("img").get("src")
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="post-status").find_all("div", class_="summary-content")[-1].get_text(strip=True).lower()
        
        chapters_list_wrapper = comic_soup.select('ul.main.version-chap.no-volumn li.wp-manga-chapter.has-thumb.free-chap')
        chapters_list: list[str] = list(reversed([tag.find("a").text.replace("Chapter", "").strip() for tag in chapters_list_wrapper]))
        first_chapter: str = chapters_list[0]
        latest_chapter: str = chapters_list[-1]

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list
    
    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        if int(ch_num) < 10:
            ch_num = f"0{ch_num}"
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        backup_url: str = ""
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        if chapter_soup is None and backup_url:
            chapter_soup = await self.get_soup(backup_url)
        
        img_tags = chapter_soup.find_all("img")
        chapter_image_tags = [tag for tag in img_tags if tag.has_attr("alt") and tag.has_attr("src")]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="utoon", src_value="src")

class HiveToon(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name
        self.protocol: str = "https://hivetoons.org"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "hivetoon")
        self.persistent_instance = PersistentPlaywright(given_config)
        # if needed
        self.comic_uid = self.given_config[2]
        self.release_day = self.given_config[3]
        self.is_completed = self.given_config[4]

        self.comic_url: str = f"{self.protocol}/series/{self.url_comic_name}"
        self.comic_template_url: str = f"{self.comic_url}/chapter-{{}}"
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"]
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "hivetoon", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")
    
        comic_soup_name: str = comic_soup.find("h1", class_="text-2xl font-bold text-foreground leading-[1.5rem]").text.strip()

        comic_cover_img_link: str = comic_soup.find("img", class_="w-full rounded-lg object-cover object-bottom sm:max-h-[400px] h-auto").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="flex w-full h-auto shrink-0 flex-col gap-3 rounded-lg sm:w-[17rem] xl:p-0 lg:p-0 md:p-0 px-2 sm:p-0").find("p", class_="font-normal text-xs inline ml-1 text-foreground").text.lower().strip()

        chapters_list_wrapper = comic_soup.find("div", class_="flex w-full flex-col gap-3 px-4 py-4").find_all("h3", class_="text-gray-900 dark:text-white font-medium text-lg")
        chapters_list: list[str] = list(reversed([tag.text.replace("Chapter", "").strip() for tag in chapters_list_wrapper]))
        first_chapter: str = chapters_list[0]
        latest_chapter: str = chapters_list[-1]

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list
    
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
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="hivetoon", src_value="src")

        # img_links = await self.persistent_instance.network_image_scraper({
        #     'chapter_url': comic_chapter_url,
        #     'link_filter': "https://storage.hivetoon.com/public/",
        #     'filename_regex': r"(image_1000_\w{8}|0\d|1\d)\.(webp|jpg)",
        #     "possible_file_extensions": [".webp", ".jpg"]
        # })
        # print(img_links)
        # print(len(img_links))
        # return img_links

class ArenaScans(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None):
        super().__init__(headers, async_client)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name
        self.protocol: str = "https://arenascan.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "arenascans")
        # if needed
        self.comic_uid = self.given_config[2]
        self.release_day = self.given_config[3]
        self.is_completed = self.given_config[4]

        self.comic_url: str = f"{self.protocol}/manga/{self.url_comic_name}/"
        self.comic_template_url: str = f"{self.protocol}/{self.url_comic_name}-{{}}/"
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_template_url:')} {color_msg('white', self.comic_template_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"]
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "arenascans", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            raise ValueError(f"Failed to fetch comic page: {self.comic_url}")
    
        comic_soup_name: str = comic_soup.find("h1", class_="entry-title").get_text(strip=True)

        comic_cover_img_link: str = comic_soup.find("img", class_="attachment- size- wp-post-image").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = "everyday"

        chapters_list: list[str] = list(reversed([tag.get_text(strip=True).lower().replace("chapter", "").strip() for tag in comic_soup.find("div", id="chapterlist").find_all("span", class_="chapternum")]))
        first_chapter: str = chapters_list[0]
        latest_chapter: str = chapters_list[-1]

        return {
            'soup_name': comic_soup_name,
            'cover_img_link': comic_cover_img_link,
            'status': comic_status,
            'chapters_list': chapters_list,
            'first_chapter': first_chapter,
            'latest_chapter': latest_chapter
        }

    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list
    
    async def get_chapter_image_links(self, ch_num: str) -> list[str]:
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        if not chapter_soup: chapter_soup = await self.get_dynamic_soup(url=comic_chapter_url, selector="#readerarea", domain="arenascans")
        chapter_image_tags = chapter_soup.find("div", id="readerarea").find_all("img")
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="arenascans", src_value="src")

""" HELPER FUNCTIONS """

def create_async_client(headers: dict[str, str]) -> httpx.AsyncClient:
    timeout = httpx.Timeout(connect=10.0, read=90.0, write=15.0, pool=10.0)
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=15)
    return httpx.AsyncClient(headers=headers, timeout=timeout, limits=limits, follow_redirects=True)

async def clean_progress_file(progress_fp: str, bookshelf_queue: list[str]) -> None:
    """removes comics from progress.json that are no longer in the catalogue.json queue"""
    
    def progress_tag(msg: str) -> None:
        print(color_msg("yellow", f"[Progress] {msg}"))

    progress_json_fp = os.path.join(os.getcwd(), progress_fp)
    async with aiofiles.open(progress_json_fp, "r", encoding="utf-8") as pj_filepath:
        content = await pj_filepath.read()
        progress_data = json.loads(content)

    new_progress = {}
    def regulate_name(name: str): 
        return name.lower().replace("'", "\u2019").strip()
    
    queue_comic_names = {regulate_name(comic[0]) for comic in bookshelf_queue}
    removed_comics: list[str] = []
    for read_comic, comic_progress in progress_data.items():
        stripped_comic = regulate_name(read_comic)

        if stripped_comic in queue_comic_names:
            new_progress[read_comic] = comic_progress
        else:
            if comic_progress > 1:
                new_progress[read_comic] = comic_progress
            else:
                removed_comics.append(stripped_comic)
    
    for queued_comic in queue_comic_names:
        if queued_comic not in new_progress:
            new_progress[queued_comic] = 1

    if await aios.path.exists(progress_json_fp):
        await aios.remove(progress_json_fp)

    sorted_progress = dict(sorted(new_progress.items()))
    async with aiofiles.open(progress_json_fp, "w", encoding="utf-8") as new_pjfp:
        await new_pjfp.write(json.dumps(sorted_progress, ensure_ascii=True))

    progress_tag(f"Removed {len(removed_comics)} comics from {progress_fp}")
    for removed in removed_comics:
        progress_tag(color_msg("red", f"[-] {removed}"))
    return

async def reset_dir(npath: str) -> None:
    """deletes and recreates a directory at npath"""
    if os.path.exists(npath):
        shutil.rmtree(npath)
    if not os.path.exists(npath):
        os.mkdir(npath)

def get_runtime(start_time: float) -> str:
    """returns runtime string given start_time"""
    curr_time = time.time()
    runtime = curr_time - start_time
    if runtime < 60:
        return f"[  {int(runtime)}s  ]"

    elif runtime < 3600:
        minutes = int(runtime // 60)
        seconds = int(runtime % 60)
        return f"[ {minutes}m {seconds}s ]"

    else:
        hours = int(runtime // 3600)
        remaining_seconds = runtime % 3600
        minutes = int(remaining_seconds // 60)
        return f"[ {hours}h {minutes}m ]"

def get_test_config(config: list[list[str, str]]):
    temp_dict = {}
    for comic in config:
        name = comic[0]
        domain = comic[1]
        if domain not in temp_dict:
            temp_dict[domain] = name
    
    print(f"Available domains: {len(temp_dict)}")
    test_config = []
    for domain, name in temp_dict.items():
        test_config.append([name, domain])
    
    return test_config

async def main():
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    start_time: float = time.time()
    today_day = dt.datetime.now().strftime("%A").lower()

    current_config: str     = os.path.join(os.getcwd(), "catalogue.json")
    merger_config_fp: str   = os.path.join(os.getcwd(), "catalogue_db.json")
    synopsis = Synopsis(current_config, merger_filepath=merger_config_fp)

    headers: dict[str, str] = { "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0", "Accept": "image/*" }
    async_client: httpx.AsyncClient = create_async_client(headers)

    catalogue: list[list[str, str]] = synopsis.get_config_comics()
    print(color_msg("green", f"Found {len(catalogue)} comics to scrape."))

    TEMP_DIR: str = os.path.join(os.getcwd(), "temp")
    await reset_dir(TEMP_DIR)

    my_controls = ControlPanel(headers, async_client)
    print('bookshelf_test directory reset.')
    
    # await clean_progress_file("progress_copy.json", config) # do this only after comic names online are scraped

    num_str_list = [str(idx) for idx in range(0, 10)]
    alphabet_list = list("ABCDEFGHIJKLMNOPQ")
    ignore_list = num_str_list + alphabet_list

    for comic_config in catalogue:
        comic_name = comic_config[0]
        # first_letter = comic_name[0]
        # if first_letter in ignore_list: continue
        # if comic_name != "Eat Before You Go": continue
        domain = comic_config[1]
        if domain != "ravenscans": continue
        await my_controls.comic_redirect(comic_config)
        await asyncio.sleep(2)

    progress_comics = my_controls.get_progress_comics()
    print(len(progress_comics))
    failed_fetches = my_controls.get_failed_fetches()
    for idx in failed_fetches: print(idx)

if __name__ == "__main__":
    asyncio.run(main())
