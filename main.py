import os, time, requests, json, re, shutil, urllib, math, binascii, discord, datetime, sys, traceback, io, asyncio, httpx, aiofiles, subprocess
import datetime as dt
import aiofiles.os as aios
from tqdm import tqdm
from bs4 import BeautifulSoup
import pillow_avif
from PIL import Image, ImageFile
from colorama import Fore as CFore
from colorama import Style as CStyle
from typing import *
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import quote, urlparse
from sentence_transformers import SentenceTransformer
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from ebooklib import epub
from pathlib import Path



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

"""
v1.0.3 Changes

o Added validation to skip re-downloading cover images if they already exist locally
o Added basic Discord notification support (progress, error)
o Added support for domains GenzToon and ManhwaReads
o Added validation to skip premium_chapters when getting comic details for Domains (Vortexscans)
o Refactored functions for getting chapters left and downloaded chapters to validate chapters that have special names and decimals to be downloaded
o Added memory usage logs for local directories
o Added retry attempts for the get_url_response()
o Made functions for getting comic details in class methods for ease of maintenance and readability. (Omegascans so far)
o Temporarily disabled mangafire domain and ravenscans domain

"""


""" DONE """
# decimal chapters should be downloaded
# temporariily disabled genztoon domain and mangafire domain
# fixed decimal chapters for .1, .5, .X, and chapters where theres a custom chapter number (ex. 14-the-end)
# added cross-referencing and smarter downloads with the implementation of progress.json
# refactored functions for getting chapters left and downloaded chapters to prevent redundant usage of opening the same file multiple times for data
# added mem checks for folders just for console logging
# added retry attempts for get_url_response() function so that it doenst just try once and break
# fixed get_comic_dirpath_data() not taking in decimal chapters properly
# made refactored factions for ease of readability when maintaining domains (only Omegascans so far)


""" Doing """
# fix catalogue commands not working
# fix !mem command?

""" TODO CATALOG.PY """
# smart downloads
# progress.json garbage collector
# update catalogue.json with updated configs and extra attributes
# for flamecomics, if comic_id and soup_name don't match with catalogue config name, then fix the comic_id
# needs more retries for getting comic page and getting comic details

""" TODO Archivist """
# Archivist Start Command
# Archivist Stop Command
# Archivist add comic command ( with save)
# Archivist catalogue search command
# Archivist edit catalogue command (with save)
# Archivist remove comic from catalogue command (with save)


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
    _shared_model = None

    def __init__(self, list_of_configs: list[list[str]]):
        self.list_of_configs = list_of_configs

        if Comparer._shared_model is None:
            print("Loading SentenceTransformer model (first and only time)")
            Comparer._shared_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        self.model = Comparer._shared_model

        if not hasattr(Comparer, '_instance_count'):
            Comparer._instance_count = 0
        Comparer._instance_count += 1

        self.standard_threshold: float = 0.92
        self.english_threshold: float = 0.98
        self.dupes_to_delete_by_basename = self.get_dupes_by_base_name(self.list_of_configs)
        self.dupes_to_delete_by_model, self.manual_review = self.get_dupes_by_model(self.list_of_configs)

        self.all_dupes = self.dupes_to_delete_by_basename + self.dupes_to_delete_by_model
        
    def get_all_dupes(self):
        return self.all_dupes
    
    def get_dupes_to_be_reviewed(self) -> list[str]:
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
        self.current_config_path: str = current_config_path
        self.temp_config_path: str = os.path.join(os.getcwd(), "temp_config.json")
        self.current_config: dict[list[str, str, int | str, str, bool]] = self.load_config(self.current_config_path)
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
        
        clean_config_list = current_config.copy()
    
        # Remove automatic dupes
        for dupe in dupes:
            if dupe in clean_config_list:
                clean_config_list.remove(dupe)
            
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
            if not isinstance(item[1], str):
                print("BAD ITEM:", item, type(item[1]))
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
    def __init__(self, headers: dict[str, str], async_client: httpx.AsyncClient, archivist_inst):
        self.headers = headers
        self.async_client = async_client
        self.archivist_inst = archivist_inst
        self.bookshelf = Bookshelf()
        self.comic_buffer_bypasses: list[str] = ["Eleceed"]
        self.cover_images_dirpath = os.path.join(os.getcwd(), "cover_images")
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

    def catch_and_notify(self, func):
        """Decorator to catch errors and send to Discord"""
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                await self.notify_error(f"Error in {func.__name__}: {str(e)}", error=e)
                raise
        return wrapper
        
    async def notify_message(self, message: str):await self.archivist_inst.notify_message(message)

    async def notify_error(self, message: str, error: Exception=None):
        await self.archivist_inst.notify_error(message, error)
        await self.archivist_inst.mention()
        raise ValueError(message)

    def get_failed_fetches(self) -> list[str]: return self.failed_fetches

    def get_progress_comics(self) -> dict[str, str]: return self.bookshelf.progress_comics

    def cleanup_config(self) -> None:
        if self.configs_to_be_updated == []:
            self.panel_tag("No configs to update.")
            return
        self.panel_tag(f'cleanup_config has {len(self.configs_to_be_updated)} configs to be updated.')
        for config in self.configs_to_be_updated:
            self.panel_tag(config)

    def panel_tag(self, msg: str) -> None: print(color_msg("lightblue", f"[Control] {msg}"))

    def dev_tag(self, msg: str) -> None: print(color_msg("lightred", f"[DEV] {msg}"))

    async def validate_image_link(self, link: str) -> bool:
        # self.dev_tag(f'ControlPanel.validate_image_link(link): link = {link}')
        if not link.startswith("https://"): return False
        timeout = httpx.Timeout(connect=20.0, read=60.0, write=20.0, pool=20.0)
        try:
            async with self.async_client.stream("GET", link, follow_redirects=True, timeout=timeout, headers=self.headers) as response:
                if response.status_code != 200: return False
                content_type = response.headers.get("content-type", "").lower()
                if not content_type.startswith("image/"): return False
                async for chunk in response.aiter_bytes(chunk_size=1024):
                    return bool(chunk)

        except httpx.ReadTimeout:
            print(color_msg("yellow", f"Validation timeout: {link}"))
            await asyncio.sleep(1.5)

        except Exception as e:
            print(color_msg("yellow", f"Validation failed: {link} - {type(e).__name__}: {repr(e)}"))
            return False
        return False

    @staticmethod
    def get_url_comic_name(comic_name: str, domain_name=None) -> str:
        if comic_name == "KinkFolder.ZIP": return "kinkfolder-zip"
        if comic_name == "Reality Quest": comic_name = "Reality Quest 2"
        if domain_name == "omegascans":
            if comic_name == "Mother and Daughter\u2019s Home": return "mother-and-daughters-home"
            if "I\u2019m " in comic_name: comic_name = comic_name.replace("I\u2019m ", "Im ")
        # if domain_name == "mangakatana": comic_name = comic_name.replace("\u2019", "").replace("'", "")

        res = comic_name.lower()
        if domain_name == "vortexscans":
            if comic_name == "Apocalyptic Chef Awakening":
                return "apocalyptic-chef-awakening4"
            res = res.replace(":", "%3A")
            
        chars_to_remove = ["(", ")", ":", "\u2013", "\u2026", "!", "?", "%", ".", "~", ",", "+", "/", "[", "]"]
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
        with open("progress.json", 'r', encoding='utf-8') as p:
            progress_data = json.load(p)
        if comic_name in progress_data.keys():
            return progress_data[comic_name]
        else:
            return 1
    
    def get_comic_dirpath_data(self, chapter_list: list[str]) -> tuple[list[str], list[str]]:
        first_fragment_files = sorted([file for file in os.listdir(self.comic_dirpath) if file.endswith("p1.jpg")])

        def normalize_chapter(raw: str) -> str | None:
            raw = str(raw)
            if (m := re.match(r"^(\d+)x(\d+)$", raw)): return str(float(f"{m.group(1)}.{m.group(2)}"))
            if (m := re.match(r"^(\d+)-(\d+)$", raw)): return str(float(f"{m.group(1)}.{m.group(2)}"))
            if (m := re.match(r"^(\d+)\.(\d+)$", raw)): return f"{int(m.group(1))}.{int(m.group(2))}"
            if (m := re.match(r"^(\d+)", raw)): return str(int(m.group(1)))
            return None

        def extract_and_normalize(filename: str) -> str | None:
            return normalize_chapter(m.group(1)) if (m := re.search(r"chapter-(.+?)-p1\.jpg", filename)) else None

        downloaded_chapters = [ch for ch in (extract_and_normalize(file) for file in first_fragment_files) if ch is not None]
        downloaded_chapters = sorted(set(downloaded_chapters), key=float)

        chapter_list_normalized = [normalize_chapter(ch) for ch in chapter_list]

        chapters_left = [original for original, normalized in zip(chapter_list, chapter_list_normalized) if normalized not in downloaded_chapters]

        # print(f'downloaded_chapters: {downloaded_chapters}')
        # print(f'chapters_left: {chapters_left}')

        return downloaded_chapters, chapters_left

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
            "genztoons": GenZToons,
            "manhwaread": ManhwaRead,
        }[comic_domain]

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

        self.panel_tag(color_msg("lightyellow", f"Starting at chapter: {chapters_left[0] if chapters_left else "None"}"))

        if downloaded_chapters_num == latest_ch:
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
        if comic_domain in ["flamecomics", "genztoons"]:
            chapter_links = await domain_instance.get_chapter_links_list()
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

            if comic_domain in ["flamecomics", "genztoons"]:
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
                if comic_domain in ["flamecomics", "genztoons"]:
                    progress.update_chapter(chapter_num)
                else:
                    progress.update_chapter(chapter_num)
                await self.notify_error(color_msg("yellow", f"ControlPanel.comic_redirect():\n > Domain: {comic_domain}\n > Comic: {comic_soup_name}\n > No images for chapter {chapter_num}"))
        
            if comic_domain in ["flamecomics", "genztoons"]:
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
    
class ChapterProgressBar:
    def __init__(self, total_chapters: int):
        self.total_chapters = total_chapters
        self.current_chapter = 0
        self.pbar = None
        
    def start(self):
        self.pbar = tqdm(total=self.total_chapters, desc="Processing chapters", bar_format="{l_bar}{bar}{r_bar}", leave=False, position=0)
        
    def update_chapter(self, chapter_num: str):
        self.current_chapter += 1
        self.pbar.set_description(f"Ch {chapter_num}")
        self.pbar.update(1)
        self.pbar.refresh()
        
    def log_step(self, step: str, time_taken: float):
        self.pbar.set_postfix_str(f"{step}: {time_taken:.1f}s")
        self.pbar.refresh()
        
    def close(self):
        if self.pbar:
            self.pbar.close()

class Bookshelf:
    def __init__(self):
        self.bookshelf_dirpath = os.path.join(os.getcwd(), "Bookshelf")
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
    def __init__(self, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
    
    async def get_soup(self, url: str) -> Optional[BeautifulSoup]:
        async def retry_soup(url: str, retries: int) -> httpx.Response | None:
            for idx in range(retries):
                res = await self.get_url_response(url)
                if res is not None:
                    return res
                await asyncio.sleep(2)
            return None
        
        res = await retry_soup(url, retries=5)
        if res is None:
            self.dev_tag(f"Failed to fetch {url}")
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

        pattern = r"chapter-(.+?)-p\d+"
        for file in existing_files:
            match = re.search(pattern, file)
            if match:
                existing_chapters.add(match.group(1))

        chapters_left = [
            re.sub(r"-+", "-", str(chapter).strip().replace(" ", "-"))
            for chapter in chapters
            if str(chapter).strip() not in existing_chapters
        ]

        # print(f'get_chapters_left: chapters_left: {chapters_left}')

        def sort_key(chapter: str):
            # 14x5 -> sort as 14.5, but keep original "14x5"
            normalized = chapter.replace("x", ".").replace("-", ".")

            match = re.match(r"^(\d+(?:\.\d+)?)", normalized)
            if match:
                return float(match.group(1))

            return float("inf")

        return sorted(chapters_left, key=sort_key)
    
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
        if len(img_paths) == 1:
            await self.split_image(img_paths, temp_dirpath, comic_dirpath, chapter_number)
        else:
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

    def extract_fragment_number(self, path: str) -> int:
        filename = os.path.basename(path)
        match = re.search(r"f(\d+)\.", filename)
        return int(match.group(1)) if match else 0

    def get_image_object(self, path: str) -> Image:
        return Image.open(path)
    
    async def stitch_images(self, img_paths: list[str], temp_dirpath: str, comic_dirpath: str, chapter_number: str):
        os.makedirs(comic_dirpath, exist_ok=True)
        # # self.dev_tag(f'running stitch images\nlen img_paths: {len(img_paths)}: {img_paths}, chapter_number: {chapter_number}')
        
        img_paths.sort(key=self.extract_fragment_number)
        
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
                if width < 1 or height < 1:
                    await self.notify_error(f'Downloader.stitch_images():\n > width/height is less than 1. width: {width}, height: {height}, img_path: {img_path}')
                
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

    async def split_image(self, img_paths: list[str], temp_dirpath: str, comic_dirpath: str, chapter_number: str):
        os.makedirs(comic_dirpath, exist_ok=True)
        img_filepath: str = img_paths[0]
        img_filename: str = img_filepath.split("/")[-1]
        max_height: int = 65500
        img_object: Image = self.get_image_object(img_filepath)
        img_w, img_h = img_object.size
        img_mode = img_object.mode

        if img_object.mode == 'P':
            img_object = img_object.convert('RGB')
        elif img_mode == "RGBA":
            background = Image.new('RGB', img_object.size, (255, 255, 255))
            background.paste(img_object, mask=img_object.split()[-1])
            img_object = background
        elif img_mode != "RGB" or img_object == "P" or img_mode != "L":
            img_object = img_object.convert("RGB")

        if img_h < max_height:
            part_filename = re.sub(r'f(\d+)\.', r'p\1.', img_filename)
            new_img_filepath = os.path.join(comic_dirpath, part_filename)

            img_object.save(new_img_filepath)
            img_object.close()
            return

        def get_filename_chnum(filename: str) -> tuple[int, int]:
            chapter_pattern = re.compile(r"^chapter\-(\d+)\-f\d+\.(jpg|png|webp|jpeg|gif)$")
            match = re.search(chapter_pattern, filename)
            if match:
                chapter_number = match.group(1)
                extension = match.group(2)
                return chapter_number, extension

        img_filename_attrs = get_filename_chnum(filename=img_filename)
        chapter_number: int = img_filename_attrs[0]
        filename_ext: str = img_filename_attrs[1]
        num_chunks: int = math.ceil(img_h / max_height)
        chunk_height: int = math.ceil(img_h / num_chunks)

        chunk_paths = []
        os.remove(img_filepath)
        for idx in range(num_chunks):
            top_coord = idx * chunk_height
            bot_coord = min((idx + 1) * chunk_height, img_h)
            cropped_img = img_object.crop((0, top_coord, img_w, bot_coord))
            chunk_filename = f'chapter-{chapter_number}-p{idx+1}.{filename_ext}'
            chunk_filepath = os.path.join(comic_dirpath, chunk_filename)
            cropped_img.save(chunk_filepath)
            chunk_paths.append(filename_ext)
        
        img_object.close()
        return

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
            await self.notify_error(color_msg("yellow", f"Downloader.process_cover_image():\n > Comic cover image link is not valid.\n > Link: {link}"))
        
        cover_img_filename: str = self.get_cover_img_fname(self.comic_name, link)
        cover_img_filepath: str = os.path.join(self.cover_images_dirpath, cover_img_filename)
        if cover_img_filename not in self.cover_images:
            await self.download_single_image(link, cover_img_filepath)
        return
    
    async def validate_with_playwright(self, page, chapter_url, img_url: str) -> bool:
        try:
            response = await page.request.get(
                img_url,
                headers={
                    "referer": chapter_url,
                    "user-agent": await page.evaluate("navigator.userAgent"),
                },
                timeout=30000,
            )
            content_type = response.headers.get("content-type", "").lower()
            # print(
            #     f"[PW VALIDATE] {response.status} "
            #     f"{content_type} "
            #     f"{img_url}"
            # )

            return response.ok and content_type.startswith("image/")

        except Exception as e:
            print(f"[PW VALIDATE FAILED] {img_url} - {type(e).__name__}: {e}")
            return False
        
    async def get_images_playwright_scroll(self, chapter_url: str, regex_filter: str, link_filter: str, img_element_filter: str, file_ext: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-dev-shm-usage', '--no-sandbox'],
            )

            page = await browser.new_page()
            page.set_default_timeout(30000)

            network_images = []
            seen = set()
            compiled_regex = re.compile(regex_filter)

            def clean_url(url: str): return url.split("?")[0]

            def add_image(url: str):
                clean = clean_url(url)
                filename = clean.split("/")[-1]

                if link_filter and link_filter not in clean:
                    return

                if file_ext and not clean.endswith(file_ext):
                    return

                if regex_filter and not compiled_regex.match(filename):
                    return

                if clean not in seen:
                    seen.add(clean)
                    network_images.append(clean)

            def handle_response(response): add_image(response.url)
                
            def handle_request(request):
                if request.resource_type == "image":
                    add_image(request.url)

            page.on("response", handle_response)
            page.on("request", handle_request)

            try:
                await page.goto(chapter_url, wait_until="networkidle", timeout=60000)
            except PlaywrightTimeoutError:
                await page.goto(chapter_url, wait_until="domcontentloaded", timeout=60000)

            await page.wait_for_timeout(3000)

            last_height = 0
            stable_rounds = 0

            while stable_rounds < 3:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)

                height = await page.evaluate("document.body.scrollHeight")

                if height == last_height:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                    last_height = height

            img_elements = await page.query_selector_all(
                f'img[src*="{img_element_filter}"], img[data-src*="{img_element_filter}"], img[data-lazy-src*="{img_element_filter}"]'
            )

            for img in img_elements:
                for attr in ["src", "data-src", "data-lazy-src"]:
                    src = await img.get_attribute(attr)
                    if src:
                        add_image(src)

            def get_page_num(url):
                filename = url.split("/")[-1]
                match = re.search(r'^(\d+)', filename)
                if match:
                    return int(match.group(1))
                return 999999

            network_images.sort(key=get_page_num)

            valid_images = []
            for img in network_images:
                if await self.validate_with_playwright(page, chapter_url, img):
                    valid_images.append(img)

            await browser.close()

        return valid_images

    async def download_single_image_playwright(self, page, chapter_url: str, img_link: str, img_output_path: str) -> None:
        try:
            response = await page.request.get(
                img_link,
                headers={
                    "referer": chapter_url,
                    "user-agent": await page.evaluate("navigator.userAgent"),
                },
                timeout=30000,
            )

            if not response.ok:
                print(f"Failed to download {img_link}: {response.status}")
                return

            content_type = response.headers.get("content-type", "").lower()
            if not content_type.startswith("image/"):
                print(f"Not an image: {img_link} ({content_type})")
                return

            async with aiofiles.open(img_output_path, "wb") as file:
                await file.write(await response.body())

        except Exception as e:
            print(f"Failed to download {img_link}: {type(e).__name__}: {e}")
            
    async def get_valid_image_links(self, tag_list: list[str], domain_name: str, src_value: str, comic_name: str, chapter_num: int,extra_attribute: str=None):
        # self.dev_tag(f'Downloader.get_valid_image_links()\ntag_list: {tag_list}\ndomain_name: {domain_name}\nsrc_value: {src_value}\ncomic_name: {comic_name}\nchapter_num: {chapter_num}\nextra_attribute: {extra_attribute}')
        valid_links: int = 0
        valid_links_list: list[str] = []
        for img_tag in tag_list:
            img_link = None
            if domain_name == "manga18.me":
                if img_tag.has_attr("alt") and img_tag["alt"].startswith(extra_attribute) and img_tag.has_attr("src"):
                    img_link = img_tag.get("src").strip()
                elif img_tag.has_attr("src") and "manga18.me/uploads" in img_tag["src"]:
                    img_link = img_tag.get("src").strip()

            elif domain_name == "hentai20":
                if extra_attribute == "kinkfolder-zip": extra_attribute = "kinkfolderzip"
                if img_tag.has_attr("src") and extra_attribute in img_tag.get("src"):
                    img_link = img_tag.get("src").strip()
            
            elif domain_name == "asuracomics":
                img_href: str = img_tag.get("href").strip()
                img_link: str = f"https://asurascans.com{img_href}"

            else:
                img_link: str = img_tag.get(src_value).strip()
            
            if img_link and not img_link.startswith("https://"): continue

            is_valid: bool = await self.validate_image_link(img_link)
            if is_valid:
                valid_links += 1
                valid_links_list.append(img_link)

        if len(valid_links_list) == len(tag_list) - 5:
            # self.dev_tag('one image is invalid, continuing')
            return valid_links_list
        else:
            # print(color_msg("lightgreen", f"Chapter Links Validated ({domain_name}): {valid_links}/{len(tag_list)}"))
            # await self.notify_message(f"({domain_name}) Downloading {comic_name} Ch {chapter_num}: {valid_links}/{len(tag_list)}")
            return valid_links_list

    async def batch_process_playwright(self, page, chapter_url: str, links_list: list[str], temp_dirpath: str, chapter_number: str, comic_dirpath: str):
        img_paths = []

        os.makedirs(temp_dirpath, exist_ok=True)

        for idx, url in enumerate(links_list, 1):
            extension = self.get_extension(url)
            safer_chapter_number = chapter_number.replace(".", "-")
            chapter_filename = f"chapter-{safer_chapter_number}-f{idx}{extension}"
            output_path = os.path.join(temp_dirpath, chapter_filename)

            await self.download_single_image_playwright(page, chapter_url, url, output_path)
            img_paths.append(output_path)

        if len(img_paths) == 1:
            await self.split_image(img_paths, temp_dirpath, comic_dirpath, chapter_number)
        else:
            await self.stitch_images(img_paths, temp_dirpath, comic_dirpath, chapter_number)

        await reset_dir(temp_dirpath)
    
    async def get_images_and_batch_process_playwright(self, chapter_url: str, regex_filter: str, link_filter: str, img_element_filter: str, file_ext: str, temp_dirpath: str, chapter_number: str, comic_dirpath: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--no-sandbox"],
            )

            page = await browser.new_page()
            page.set_default_timeout(30000)

            network_images = []
            seen = set()
            compiled_regex = re.compile(regex_filter)

            def clean_url(url: str): return url.split("?")[0]

            def add_image(url: str):
                clean = clean_url(url)
                filename = clean.split("/")[-1]

                if link_filter and link_filter not in clean:
                    return
                if file_ext and not clean.endswith(file_ext):
                    return
                if regex_filter and not compiled_regex.match(filename):
                    return
                if clean not in seen:
                    seen.add(clean)
                    network_images.append(clean)

            def handle_response(response): add_image(response.url)

            def handle_request(request):
                if request.resource_type == "image":
                    add_image(request.url)

            page.on("response", handle_response)
            page.on("request", handle_request)

            try:
                await page.goto(chapter_url, wait_until="networkidle", timeout=60000)
            except PlaywrightTimeoutError:
                await page.goto(chapter_url, wait_until="domcontentloaded", timeout=60000)

            await page.wait_for_timeout(3000)

            last_height = 0
            stable_rounds = 0

            while stable_rounds < 3:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)

                height = await page.evaluate("document.body.scrollHeight")

                if height == last_height:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                    last_height = height

            img_elements = await page.query_selector_all(
                f'img[src*="{img_element_filter}"], img[data-src*="{img_element_filter}"], img[data-lazy-src*="{img_element_filter}"]'
            )

            for img in img_elements:
                for attr in ["src", "data-src", "data-lazy-src"]:
                    src = await img.get_attribute(attr)
                    if src:
                        add_image(src)

            def get_page_num(url):
                filename = url.split("/")[-1]
                match = re.search(r"mr_(\d+)", filename)
                if match:
                    return int(match.group(1))
                match = re.search(r"^(\d+)", filename)
                if match:
                    return int(match.group(1))
                return 999999

            network_images.sort(key=get_page_num)

            valid_images = []
            for img in network_images:
                if await self.validate_with_playwright(page, chapter_url, img):
                    valid_images.append(img)

            if not valid_images:
                await browser.close()
                return False

            await self.batch_process_playwright(page, chapter_url, valid_images, temp_dirpath, chapter_number, comic_dirpath)

            await browser.close()
            return True
        
    async def get_dynamic_soup(self, url: str, selector: str, domain: str):
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector(selector, timeout=30000)
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

    async def get_pwsoup_buttons(self, comic_url: str, domain_name=None):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(comic_url, wait_until="networkidle", timeout=5000)
            except PlaywrightTimeoutError:
                print("networkidle failed, retrying once...")
                try:
                    await page.goto(comic_url, wait_until="networkidle", timeout=5000)
                except PlaywrightTimeoutError:
                    print("networkidle failed again, falling back to domcontentloaded...")
                    await page.goto(comic_url, wait_until="domcontentloaded", timeout=5000)

            while True:
                if domain_name == "manhwaread":
                    show_more_btn = page.locator("chapterListToggleBtn")
                else:
                    show_more_btn = page.get_by_role("button", name="Show more")
                if await show_more_btn.count() == 0: break
                await show_more_btn.first.click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(500)
            html = await page.content()
            await browser.close()
            return BeautifulSoup(html, 'html.parser')
    
    async def get_soup_images_from_wrapper_after_scroll(self, chapter_url: str, wrapper_selector: str, not_in_src_word: str) -> list[str]:
        headless: bool = True
        timeout: int = 30000
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless, args=["--disable-dev-shm-usage", "--no-sandbox"])
            page = await browser.new_page()
            page.set_default_timeout(30000)

            try:
                await page.goto(chapter_url, wait_until="networkidle", timeout=timeout)
            except PlaywrightTimeoutError:
                await page.goto(chapter_url, wait_until="domcontentloaded", timeout=timeout)

            await page.wait_for_selector(wrapper_selector, timeout=timeout)
            await page.wait_for_timeout(3000)

            for i in range(5):
                await page.evaluate(f"window.scrollTo(0, {i * 800})")
                await page.wait_for_timeout(1500)

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

            await page.wait_for_function(
                """({wrapperSelector, notInSrcWord}) => {
                    const wrapper = document.querySelector(wrapperSelector);
                    if (!wrapper) return false;
                    const imgs = [...wrapper.querySelectorAll("img")];
                    if (!imgs.length) return false;
                    return imgs.every(img => {
                        const src = img.getAttribute("src");
                        return src && !src.includes(notInSrcWord);
                    });
                }""",
                arg={"wrapperSelector": wrapper_selector, "notInSrcWord": not_in_src_word},
                timeout=timeout,
            )

            src_links = await page.eval_on_selector_all(
                f"{wrapper_selector} img",
                "imgs => imgs.map(img => img.getAttribute('src')).filter(Boolean)"
            )

            await browser.close()
            return list(dict.fromkeys(src_links))
    
    def get_style_url(self, tag) -> Optional[str]:
        style = tag.get("style", "")
        if style == "": return None
        url = re.search(r"--photoURL:url\((.*?)\)", style).group(1)
        return url
    
class PersistentPlaywright:
    def __init__(self, config: list[str, str]):
        self.extensions_dirpath = os.path.join(os.getcwd(), "extensions")
        self.path_to_anti_debug_extension = os.path.join(self.extensions_dirpath, "anti_anti_debug_chrome")
        self.path_to_user_data = os.path.join(self.extensions_dirpath, "profile")

    def _mangafire_page_num(self, url: str) -> int:
        filename = urlparse(url).path.split("/")[-1]
        match = re.search(r"(\d+)\.jpg$", filename)
        return int(match.group(1)) if match else 999999
    
    def _is_mangafire_page_image(self, url: str) -> bool:
        return (
            re.search(r"mfcdn\d\.xyz/mf", url) is not None
            and re.search(r"/\d+\.jpg(?:$|\?)", url) is not None
        )
    
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

    async def get_mangafire_network_images(self, url: str) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()

        def add_url(raw_url: str):
            clean_url = raw_url.split("?")[0]

            if self._is_mangafire_page_image(clean_url) and clean_url not in seen:
                seen.add(clean_url)
                found.append(clean_url)

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

            page.on("request", lambda request: add_url(request.url))
            page.on("response", lambda response: add_url(response.url))

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(8000)

            last_height = 0
            stable_rounds = 0

            while stable_rounds < 4:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)

                height = await page.evaluate("document.body.scrollHeight")

                if height == last_height:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                    last_height = height

            await page.wait_for_timeout(3000)

            # Also inspect current DOM, just in case some URLs never appeared as image requests.
            dom_urls = await page.evaluate("""
                () => Array.from(document.images)
                    .map(img => img.currentSrc || img.src)
                    .filter(Boolean)
            """)

            for img_url in dom_urls:
                add_url(img_url)

            await context.close()

        return sorted(found, key=self._mangafire_page_num)
       
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

class CatalogueManager:
    def __init__(self, path="catalogue.json"):
        self.path = path

    def load(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, data):
        data = sorted(data, key=lambda comic: comic[0].lower())
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add(self, name, domain, comic_id=0, release_day="everyday", completed=False):
        data = self.load()

        if any(comic[0].lower() == name.lower() for comic in data):
            return False

        data.append([name, domain, comic_id, release_day, completed])
        self.save(data)
        return True

    def remove(self, name):
        data = self.load()
        new_data = [comic for comic in data if comic[0].lower() != name.lower()]

        if len(new_data) == len(data):
            return False

        self.save(new_data)
        return True

    def find(self, query):
        data = self.load()
        return [comic for comic in data if query.lower() in comic[0].lower()]

    def edit(self, name, field, value):
        fields = {
            "name": 0,
            "domain": 1,
            "comic_id": 2,
            "release_day": 3,
            "completed": 4,
            "status": 4,
        }

        if field not in fields:
            return None

        data = self.load()

        for comic in data:
            if comic[0].lower() == name.lower():
                idx = fields[field]

                if field == "comic_id":
                    value = int(value)
                elif field in ["completed", "status"]:
                    value = value.lower() in ["true", "yes", "1", "completed"]

                comic[idx] = value
                self.save(data)
                return comic

        return None
    
class Archivist:
    def __init__(self, async_client):
        self.async_client = async_client
        load_dotenv()
        self.discord_token: str = os.getenv("DISCORD_TOKEN")
        self.webhook_url: str = os.getenv("WEBHOOK_URL")
        self.intents = discord.Intents.default()
        self.intents.message_content = True
        self.intents.messages = True
        self.bot_channel = "comic-scraper"
        self.bot = commands.Bot(command_prefix="!", intents=self.intents)
        self.catalogue = CatalogueManager("catalogue.json")
        # self.tree = app_commands.CommandTree(self)
    
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(self.handle_loop_exception)
        # self.register_commands()

        @self.bot.event
        async def on_ready():
            await self.bot.tree.sync()
            print(f"Logged in as {self.bot.user}")

        # @self.bot.tree.command()
        # @app_commands.describe(
        #     first_value='The first value you want to add something to',
        #     second_value='The value you want to add to the first value',
        # )
        # async def add(interaction: discord.Interaction, first_value: int, second_value: int):
        #     """Adds two numbers together."""
        #     await interaction.response.send_message(f'{first_value} + {second_value} = {first_value + second_value}')
    
    # def register_commands(self):
    #     @catalogue_group.command(name="add", description="Add a comic to catalogue.json")
    #     async def catalogue_add(
    #         interaction: discord.Interaction,
    #         name: str,
    #         domain: str,
    #         comic_id: int = 0,
    #         release_day: str = "everyday",
    #         completed: bool = False,
    #     ):
    #         added = self.catalogue.add(name, domain, comic_id, release_day, completed)

    #         if added:
    #             await interaction.response.send_message(f"✅ Added `{name}` to catalogue.")
    #         else:
    #             await interaction.response.send_message(
    #                 f"⚠️ `{name}` already exists.",
    #                 ephemeral=True
    #             )

    #     @catalogue_group.command(name="remove", description="Remove a comic from catalogue.json")
    #     async def catalogue_remove(
    #         interaction: discord.Interaction,
    #         name: str,
    #     ):
    #         removed = self.catalogue.remove(name)

    #         if removed:
    #             await interaction.response.send_message(f"🗑️ Removed `{name}`.")
    #         else:
    #             await interaction.response.send_message(
    #                 f"⚠️ Could not find `{name}`.",
    #                 ephemeral=True
    #             )

    #     @catalogue_group.command(name="find", description="Find comics in catalogue.json")
    #     async def catalogue_find(
    #         interaction: discord.Interaction,
    #         query: str,
    #     ):
    #         matches = self.catalogue.find(query)

    #         if not matches:
    #             await interaction.response.send_message("No matches found.", ephemeral=True)
    #             return

    #         lines = []
    #         for idx, comic in enumerate(matches[:10], 1):
    #             name, domain, comic_id, release_day, completed = comic
    #             lines.append(
    #                 f"`{idx}.` **{name}** | `{domain}` | id=`{comic_id}` | `{release_day}` | completed=`{completed}`"
    #             )

    #         await interaction.response.send_message("\n".join(lines))

    #     @catalogue_group.command(name="edit", description="Edit a comic field in catalogue.json")
    #     async def catalogue_edit(
    #         interaction: discord.Interaction,
    #         name: str,
    #         field: str,
    #         value: str,
    #     ):
    #         edited = self.catalogue.edit(name, field, value)

    #         if edited is None:
    #             await interaction.response.send_message(
    #                 "Could not edit comic. Fields are: "
    #                 "`name`, `domain`, `comic_id`, `release_day`, `completed`",
    #                 ephemeral=True
    #             )
    #             return

    #         await interaction.response.send_message(f"✅ Updated:\n```py\n{edited}\n```")

    #     self.bot.tree.add_command(catalogue_group)

    def handle_loop_exception(self, loop, context):
        """Global exception handler for the event loop"""
        exception = context.get('exception')
        message = context.get('message', 'Unknown error')
        
        if exception:
            asyncio.create_task(self.notify_error(f"Unhandled error: {message}", exception))
        else:
            asyncio.create_task(self.notify_error(f"Unhandled error: {message}"))

    async def run_bot(self): await self.bot.start(self.discord_token)

    async def close_bot(self): await self.bot.close()
        
    async def notify_message(self, message: str) -> None:
        await self.async_client.post(self.webhook_url, json={"content": message})

    async def mention(self):
        user_id = 292339806153998336
        await self.async_client.post(self.webhook_url, json={"content": f"<@{user_id}>"})

    async def notify_error(self, message: str, error: Exception = None) -> None:
        if error:
            tb_str = traceback.format_exec()
            if len(tb_str) > 1500: tb_str = tb_str[:1500] + "... (truncated)"
            full_message = f"🚨 **Error:** {message}\n\n```python\n{tb_str}\n```"
        else:
            full_message = f"🚨 **Error:** {message}"

        if error:
            traceback.print_exc()

        await self.async_client.post(self.webhook_url, json={"content": f"{full_message}"})
        
class Ebook:
    def __init__(self, comic_config: str | list[str]):
        self.chapter_regex = re.compile(r"chapter-(\d+)-p(\d+)\.(webp|jpg|jpeg|png)")
        self.comic_input = comic_config

        if isinstance(comic_config, str):
            self.comic_name = comic_config
            self.comic_config = self.get_comic_config()
        else:
            self.comic_name = comic_config[0]
            self.comic_config = comic_config

        if not self.comic_config:
            raise ValueError(f'Comic input {comic_config} is wrong.')

        self.comic_domain = self.comic_config[1]

        if self.comic_domain in ["utoon", "vortexscans", "mangafire"]:
            raise ValueError("Skipped domain")

        self.reso_w = 1284
        self.reso_h = 2778

        self.book = epub.EpubBook()

    def build(self):
        print(f"Building: {self.comic_name}")

        self._setup_paths()
        self._load_cover()
        self._load_comic_data()

        self._setup_book_metadata()
        self._add_css()

        self._process_all_chapters()

        self._finalise_book()
        self._write_book()
        self._cleanup()
        return
    
    def _setup_paths(self) -> None:
        self.base_path = Path.cwd()
        self.aeronaeum_dirpath: Path = self.base_path / "Aeronaeum"
        os.makedirs(self.aeronaeum_dirpath, exist_ok=True)

        self.bookshelf_dirpath: Path = self.base_path / "Bookshelf"
        self.comic_source_dirpath: Path = self.bookshelf_dirpath / self.comic_name
        self.aeronaeum_comic_dirpath: Path = self.aeronaeum_dirpath / self.comic_name

        if not self.aeronaeum_comic_dirpath.exists():
            shutil.copytree(self.comic_source_dirpath, self.aeronaeum_comic_dirpath)
        return
        
    def _load_cover(self) -> None:
        self.cover_images_dirpath: str = os.path.join(os.getcwd(), "cover_images")
        self.comic_cover_img_filepath: str = self.get_comic_cover_image()
        self.cover_image_content = open(self.comic_cover_img_filepath, "rb").read()
        print(self.comic_cover_img_filepath)
        return
    
    def _load_comic_data(self) -> None:
        self.aeronaeum_comic_data = self.get_comic_airplane_data()
        self.sorted_comic_data = sorted(self.aeronaeum_comic_data.items())
        return
    
    def _setup_book_metadata(self) -> None:
        self.book.set_title(self.comic_name)
        self.book.set_language("en")
        self.book.add_author(self.comic_domain)
        self.book.set_cover(self.comic_cover_img_filepath, self.cover_image_content)

        self.book.spine = ["nav"]
        self.book.toc = []
        return

    def _add_css(self) -> None:
        css = epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=self.generate_css()
        )
        self.book.add_item(css)

    def _process_all_chapters(self) -> None:
        with tqdm(total=len(self.sorted_comic_data), 
              desc=f"{self.comic_name}", 
              unit="chapter",
              bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} chapters"
        ) as pbar:
            for chapter_idx, chapter_images in self.sorted_comic_data:
                chunks = self.process_chapter_images((chapter_idx, chapter_images))
                first_page = self._add_chapter_to_book(chapter_idx, chunks)
                if first_page:
                    self.book.toc.append(
                        epub.Link(first_page, f'Chapter {chapter_idx}', f'ch{chapter_idx}')
                    )
                    pbar.set_postfix(current_chapter=chapter_idx, images=len(chunks))
                    pbar.update(1)
        return

    def _add_chapter_to_book(self, chapter_idx, chunks) -> str:
        first_page_filename = None

        for chunk_idx, chunk_img in enumerate(chunks, start=1):
            page_filename = self.process_chunk_to_xhtml_memory(
                chapter_idx, chunk_idx, chunk_img
            )

            if chunk_idx == 1:
                first_page_filename = page_filename

        return first_page_filename

    def _finalise_book(self) -> None:
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())

        self.book.toc = tuple(self.book.toc)
        self.book.spine = ['nav'] + self.book.spine
        return
    
    def _write_book(self) -> None:
        self.epub_filename = f"{self.comic_name}.epub"
        self.epub_filepath = os.path.join(self.aeronaeum_dirpath, self.epub_filename)
        epub.write_epub(self.epub_filepath, self.book)
        return
    
    def _cleanup(self) -> None:
        shutil.rmtree(self.aeronaeum_comic_dirpath)
        return
    
    def get_epub_filepath(self) -> str:
        return self.epub_filepath

    def process_chunk_to_xhtml_memory(self, chapter_idx: int, chunk_idx: int, image: Image.Image):
        img_filename = f"chapter_{chapter_idx}_c{chunk_idx}.jpg"

        img_bytes = io.BytesIO()
        image.save(img_bytes, format="JPEG", quality=95)

        page_filename = f"chapter_{chapter_idx}_page_{chunk_idx}.xhtml"

        xhtml_content = f"""<?xml version="1.0" encoding="utf-8"?>
    <!DOCTYPE html>
    <html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <title>{self.comic_name} - Chapter {chapter_idx} Page {chunk_idx}</title>
        <meta charset="utf-8"/>
    </head>
    <body style="margin:0; padding:0; background:black;">
        <img src="chunks/{img_filename}" style="width:100%; display:block;" />
    </body>
    </html>"""

        page_item = epub.EpubHtml(
            title=f'Chapter {chapter_idx} - Page {chunk_idx}',
            file_name=page_filename,
            lang='en'
        )
        page_item.content = xhtml_content.encode('utf-8')
        self.book.add_item(page_item)

        # Image item
        img_item = epub.EpubImage()
        img_item.file_name = f"chunks/{img_filename}"
        img_item.media_type = "image/jpeg"
        img_item.content = img_bytes.getvalue()

        self.book.add_item(img_item)

        # Spine
        self.book.spine.append(page_item)

        return page_filename
    
    def process_chapter_images(self, chapter_data):
        chapter_idx, chapter_img_filenames = chapter_data
        if not chapter_img_filenames:
            raise ValueError(f"Warning: Chapter {chapter_idx} has no image files")
        
        chapter_img_filepaths = [os.path.join(self.aeronaeum_comic_dirpath, f) for f in chapter_img_filenames]

        all_chunks = []
        for filepath in chapter_img_filepaths:
            try:
                img = Image.open(filepath)
                img = self.normalise_image_mode(img)
                chunks = self.process_image_to_chunks(img, self.reso_w, self.reso_h)
                all_chunks.extend(chunks)
            except Exception as e:
                raise ValueError(f"Error processing {filepath}: {e}")
            
        return all_chunks

    def get_comic_airplane_data(self) -> dict[int, list[str]]:
        data = {}
        for file in os.listdir(self.aeronaeum_comic_dirpath):
            match = self.chapter_regex.match(file)
            if match:
                chapter_num = int(match.group(1))
                data.setdefault(chapter_num, []).append(file)
        return data

    def generate_css(self) -> str: 
        return """
            body {
            margin: 0;
            padding: 0;
            background: black;
        }
        """

    def get_comic_config(self) -> list[str]:
        with open("catalogue.json") as c:
            catalogue_data: list[list[str]] = json.load(c)
        
        for comic_item in catalogue_data:
            if comic_item[0] == self.comic_name:
                return comic_item

    def unformat_to_camel_case(self, some_str: str) -> str:
        unformatted_string: str = re.sub(r"[+.,!?~:\{\}\(\)\[\]\'\u2019\u2013\u2026]", "", some_str.lower().strip())
        unformatted_string = re.sub(r"[ -]+", "_", unformatted_string)
        return unformatted_string
    
    def get_comic_cover_image(self) -> str:
        img_files = os.listdir(self.cover_images_dirpath)
        for img_filepath in img_files:
            img_filename: str = os.path.splitext(img_filepath)[0]
            unformatted_comic_name = self.unformat_to_camel_case(self.comic_name)
            if img_filename == unformatted_comic_name:
                return os.path.join(self.cover_images_dirpath, img_filepath)
        raise FileNotFoundError(f'Comic {unformatted_comic_name} ({self.comic_name}) was not found in self.cover_images_dirpath')

    def normalise_image_mode(self, img_object: Image) -> Image:
        img_mode = img_object.mode
        if img_mode == "RGBA":
            background = Image.new("RGB", img_object.size, (255, 255, 255))
            background.paste(img_object, mask=img_object.split()[-1])
            return background
        elif img_mode != "RGB":
            return img_object.convert("RGB")
        return img_object

    def process_image_to_chunks(self, img_object: Image, target_w: int, target_h: int) -> list[Image.Image]:
        img_w, img_h = img_object.size
        
        if img_w != target_w:
            ratio = target_w / img_w
            new_h = int(img_h * ratio)
            img_object = img_object.resize((target_w, new_h), Image.Resampling.LANCZOS)
            img_h = new_h
        
        chunks = []
        for y in range(0, img_h, target_h):
            chunk_bottom = min(y + target_h, img_h)
            chunk = img_object.crop((0, y, target_w, chunk_bottom))
            chunks.append(chunk)
        
        return chunks

class ComicProgress:
    def __init__(self):
        self.pg_filepath: str = "progress.json"
        self.pg_data: dict[str, int] = self.load_json("progress.json")
        self.ctl_data: list[list] = self.load_json("catalogue.json")
        self.ctl_comics: list[str] = [config[0] for config in self.ctl_data]
        self.actual_progress: dict[str, int] = self.get_actual_progress()
        if self.actual_progress != {}:
            self.write_to_file()

    def write_to_file(self) -> None:
        if os.path.exists(self.pg_filepath): os.remove(self.pg_filepath)
        with open(self.pg_filepath, 'w', encoding='utf-8') as pg:
            json.dump(self.actual_progress, pg, indent=4)
        return

    def get_actual_progress(self) -> dict[str, int]:
        progress = {}
        rm_count = 0
        for comic_name in self.ctl_comics:
            if comic_name not in self.pg_data.keys():
                progress[comic_name] = 1

        for comic_name, comic_pg in self.pg_data.items():
            if comic_name not in self.ctl_comics: 
                rm_count += 1
                continue
            progress[comic_name] = comic_pg
        print(color_msg("lightmagenta", f"[ComicPG] Removed {rm_count} comics from Comic Progress Tracker"))
        return dict(sorted(progress.items()))
        
    def load_json(self, path: str) -> dict | list:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    


        
""" Domains """
class Manga18(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
            await self.notify_error(f"Manga18.get_comic_details():\n > ailed to fetch comic page: {self.comic_url}")
        
        comic_soup_name: str = comic_soup.find("div", class_="post-title wleft").select_one("h1").text.strip()
        comic_cover_img_link: str = comic_soup.find("div", class_="summary_image").select_one("img").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="post_status").find_all("div", class_="post-content_item wleft")[1].find("div", class_="summary-content").text.lower().strip()
        chapters_list: list[str] = [
            tag.text.replace("Chapter", "").strip() 
            for tag in comic_soup.find("ul", class_="row-content-chapter wleft").find_all("a", class_="chapter-name text-nowrap")
        ]

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
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        
        temp_ch_num: str = ch_num.replace("-", ".") if "-" in ch_num else ch_num
        chapter_alt_check: str = f"{self.comic_soup_name} - Chapter {temp_ch_num}"
        chapter_image_tags: list[str] = chapter_soup.find("div", class_="read-content wleft").find_all('img')
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="manga18.me", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num, extra_attribute=chapter_alt_check)

class Mgeko(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
            await self.notify_error(f"Mgeko.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
        
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

        chapter_image_tags: list[str] = [
            tag for tag in chapter_soup.find("div", id="chapter-reader").find_all("img") 
            if tag.has_attr("id") and tag["id"].startswith("image-")
        ]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="mgeko", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)

class Manhuaus(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
            await self.notify_error(f"Manhuaus.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")

        comic_soup_name: str = comic_soup.find("div", class_="post-title").select_one("h1").text.strip()
        comic_cover_img_link: str = comic_soup.find("div", class_="summary_image").select_one("img").get("data-src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="post-status").find("div", class_="summary-content").text.lower().strip()
        chapters_found: list[str] = [
            atag.find("a").get_text().lower().replace("chapter", "").strip() 
            for atag in comic_soup.find_all("li", class_="wp-manga-chapter")
        ]
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
        chapter_image_tags: list[str] = [
            tag for tag in chapter_soup.find("div", class_="reading-content").find_all("img") 
            if tag.has_attr("id") and tag["id"].startswith("image-")
        ]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="yakshascans", src_value="data-src", comic_name=self.comic_soup_name, chapter_num=ch_num)

class Yakshascans(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
            await self.notify_error(f"Yakshascans.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")

        comic_soup_name: str = comic_soup.find("div", class_="post-title").select_one("h1").text.strip()
        comic_cover_img_link: str = comic_soup.find("div", class_="summary_image").find("img").get("data-src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="summary_content").find("div", class_="post-status").find("div", class_="summary-content").text.lower().strip()
        chapters_found: list[str] = [
            tag.find("a").text.replace("Chapter", "").strip() 
            for tag in comic_soup.find_all("li", class_="wp-manga-chapter")
        ]
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
        chapter_image_tags: list[str] = [
            tag for tag in chapter_soup.find("div", class_="reading-content").find_all("img") 
            if tag.has_attr("id") and tag["id"].startswith("image-")
        ]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="yakshascans", src_value="data-src", comic_name=self.comic_soup_name, chapter_num=ch_num)

class Ravenscans(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
            await self.notify_error(f"Ravenscans.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")

        comic_soup_name: str = comic_soup.find("h1", class_="entry-title").get_text(strip=True).replace("/", "")
        comic_cover_img_link: str = comic_soup.find("img", class_="attachment- size- wp-post-image").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="imptdt").find("i").get_text(strip=True).lower()

        chapters_list: list[str] = list(reversed([
            tag.get_text(strip=True).lower().replace("chapter", "").strip() 
            for tag in comic_soup.find("div", id="chapterlist").find_all("span", class_="chapternum")
        ]))
        if chapters_list == []:
            first_chapter: str = '0'
            latest_chapter: str = '0'
        else:
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
        if not chapter_soup or not chapter_soup.find("div", id="readerarea"): 
            chapter_soup = await self.get_dynamic_soup(url=comic_chapter_url, selector="#readerarea", domain="ravenscans")

        chapter_image_tags: list[str] = [
            tag for tag in chapter_soup.find("div", id="readerarea").find_all("img")
        ]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="ravenscans", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)

class Manhwabuddy(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
            await self.notify_error(f"Manhwabuddy.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")

        comic_soup_name: str = comic_soup.find("h1", class_="main-info-title title-bigger").text.strip()
        comic_cover_img_link: str = comic_soup.find("img", class_="img-cover").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="post-status").find_all("li")[1].find("span").get_text().lower().strip()
        chapters_list: list[str] = [
            tag.find("span", class_="chapter-name").text.replace("Chapter", "").strip() 
            for tag in comic_soup.find("ul", class_="chapter-list").find_all("li", class_="myfut")
        ]
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
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="manhwabuddy", src_value="data-src", comic_name=self.comic_soup_name, chapter_num=ch_num)

class Pornhwa(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
            await self.notify_error(f"Pornhwa.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")

        comic_soup_name: str = comic_soup.find("h1", class_="px-1 text-2xl text-left font-bold mb-5").text.strip()
        comic_cover_img_link: str = comic_soup.find("img", class_="w-32 h-full mx-auto border-4 border-solid border-slate-800 dark:border-white unset md:w-full md:border-8").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="overflow-hidden grid grid-cols-1 gap-4 text-left leading-7 mb-6").find_all("span")[1].get_text().lower().strip()
        chapters_list: list[str] = [
            tag.text.replace("Chapter", "").strip() 
            for tag in comic_soup.find("ul", id="chapter-list", class_="overflow-hidden pl-1 pr-1.5 grid md:grid-cols-2 gap-2").find_all("span") 
            if "Chapter" in tag.text
        ]
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
        chapter_image_tags: list[str] = [
            tag for tag in chapter_soup.find("div", id="bacaArea").find_all("img", class_="mx-auto") 
            if tag.get("src") != "/banner.jpg"
        ]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="pornhwa.me", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)

class Hentai20(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
            await self.notify_error(f"Hentai20.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")

        comic_soup_name: str = comic_soup.find("h1", class_="entry-title").get_text().strip()

        comic_cover_img_link: str = comic_soup.find("img", class_="attachment- size- wp-post-image").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("table", class_="infotable").find_all("tr")[0].find_all("td")[1].text.lower().strip()
        chapters_list: list[str] = [
            tag.text.replace("Chapter", "").strip() 
            for tag in comic_soup.find("div", id="chapterlist").find_all("span", class_="chapternum")
        ]
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
        chapter_soup = await self.get_soup(comic_chapter_url)
        if ch_num == "0" and not chapter_soup:
            ch_num = "0-prologue"
            comic_chapter_url = self.comic_template_url.format(ch_num)
            chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
            if not chapter_soup:
                chapter_soup = await self.get_dynamic_soup(url=comic_chapter_url, selector="#readerarea", domain="hentai20")
        if ch_num != "0" and not chapter_soup:
            chapter_soup = await self.get_dynamic_soup(url=comic_chapter_url, selector="#readerarea", domain="hentai20")
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

class AsuraComics(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, series_url: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
            await self.notify_error(f"Asuracomics.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
        
        comic_soup_name: str = comic_soup.find("h1", class_="text-xl lg:text-[32px] font-semibold leading-tight").text.strip()

        comic_cover_img_link: str = comic_soup.find("div", class_="rounded-xl z-0 w-full h-full absolute top-0 left-0").find("img").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("span", class_="text-base font-bold text-[#A78BFA] capitalize").get_text(strip=True).lower().strip()
        
        chapter_wrapper = comic_soup.find("div", class_="max-h-[500px] overflow-y-auto")
        premium_chapter: str = chapter_wrapper.find("div", class_="flex items-center gap-3 min-w-0 flex-1").find("span", class_="font-medium transition-colors text-white group-hover:text-[#913FE2]").get_text().lower().replace("chapter", "").strip()
        non_premium_chapters = list(reversed([
            tag.find("span", class_="font-medium transition-colors text-white group-hover:text-[#913FE2]").get_text(strip=True).lower().replace("chapter", "").strip() 
            for tag in chapter_wrapper.find("div", class_="divide-y divide-white/5").find_all("a", class_="group flex items-center justify-between px-4 py-4 transition-colors hover:bg-white/5")
        ]))
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
        # self.dev_tag(f'running search_asura, query_comic_name: {query_comic_name}')
        lowered_query = query_comic_name.lower().strip()
        clean_query = query_comic_name.replace("'", "\u2019")
        domain_protocol: str = "https://asurascans.com"
        search_protocol: str = "https://asurascans.com/browse?search={}"
        has_unicode_element: bool = self.has_unicode(clean_query)
        self.dev_tag(f'has_unicode_element: {has_unicode_element}')
        search_query = query_comic_name.replace(" ", "%20")
        if has_unicode_element:
            search_query = self.find_query_part(clean_query)

        search_url = search_protocol.format(search_query.lower().strip())
        
        # self.dev_tag(f'search asura query: {search_query}')
        # self.dev_tag(f'search url: {search_protocol.format(search_query.lower().strip())}')
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
    def __init__(self, given_config: list[str], comic_name: str, comic_id: int, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
            await self.notify_error(f"Flamecomics.get_comic_details():\n > Failed to fetch this comic page: {self.comic_url}")
        
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

        chapters_list = list(reversed([
            tag.find("p", class_="mantine-focus-auto m_b6d8b162 mantine-Text-root").get_text(strip=True).lower().replace("chapter", "").strip() 
            for tag in comic_soup.find("div", class_="m_c0783ff9 mantine-ScrollArea-viewport").find_all("a", class_="ChapterCard_chapterWrapper__NIPp5 mantine-focus-auto")
        ]))
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

    async def get_chapter_image_links(self, ch_num: int, chapter_url: str) -> list[str]:
        comic_chapter_soup: Optional[BeautifulSoup] = await self.get_soup(chapter_url)
        img_tags = comic_chapter_soup.find_all("img")
        chapter_image_tags = [
            tag for tag in img_tags 
            if tag and tag.has_attr("src") and tag["src"].startswith("https://cdn.flamecomics.xyz/uploads/images/series")
        ]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="flamecomics", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)

class OmegaScans(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
        self.chapters_list: list[str]   = details["chapters_list"]
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.release_day: str = details["release_day"]
        self.generated_config: list[str] = [self.comic_soup_name, "omegascans", 0, self.release_day, True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    def get_comic_soup_name(self, soup: BeautifulSoup) -> str:
        return soup.find("div", id="content").find("h1", class_="text-xl md:text-3xl text-foreground font-bold text-center lg:text-left inline").text.strip()
    
    def get_comic_cover_img_link(self, soup: BeautifulSoup) -> str:
        ele = soup.find("img", class_="w-full bg-muted/40 h-[500px] sm:h-[720px] md:h-[530px] lg:w-full lg:h-[320px] xl:h-[430px] 2xl:h-[450px] rounded")
        return self.handle_srcset(ele)
    
    def get_comic_status(self, soup: BeautifulSoup) -> str:
        comic_tags = [
            tag.get_text(strip=True).lower() 
            for tag in soup.find("div", class_="flex flex-row flex-wrap gap-2").find_all("span")
        ]
        if not "ongoing" in comic_tags:
            return "completed"
        else:
            return "ongoing"
        
    def get_comic_release_day(self, soup: BeautifulSoup) -> str:
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
    
    def get_comic_chapters_list(self, soup: BeautifulSoup) -> list[str]:
        wrapper = (
            soup.find("div", class_="max-h-[720px] overflow-y-auto pr-1")
            .find("ul", attrs={
                "class": lambda c: c and "grid grid-cols-1" in c
            })
        )
        if not wrapper: 
            raise ValueError('OmegaScans.get_comic_details().get_comic_chapters_list(): not wrapper')
    
        chapters_list: list[str] = list(reversed([
            tag.find("span", class_="m-0 text-[1rem] line-clamp-1 lg:max-w-none").get_text(strip=True).lower().replace("chapter", "").strip().split(" - ")[0] 
            for tag in wrapper.find_all("a", class_="text-foreground visited:text-[rgb(79,0,225)]")
        ]))
        return chapters_list
    
    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if not comic_soup or not comic_soup.find("div", class_="space-y-4"):
            comic_soup = await self.get_dynamic_soup(self.comic_url, selector=".space-y-4", domain="omegascans")
            if not comic_soup:
                await self.notify_error(f"Omegascans.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
    
        comic_soup_name: str = self.get_comic_soup_name(comic_soup)

        comic_cover_img_link: str = self.get_comic_cover_img_link(comic_soup)
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = self.get_comic_status(comic_soup)

        release_day: str = self.get_comic_release_day(comic_soup)
        
        chapters_list: list[str] = self.get_comic_chapters_list(comic_soup)
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
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="omegascans", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)

class KingOfShojo(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
            await self.notify_error(f"Kingofshojo.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")

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
        # self.dev_tag(f'KingOfShojo.get_chapter_image_links(): ch_num = {ch_num}')
        comic_chapter_url: str = self.comic_template_url.format(ch_num)
        backup_url: str = ""
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        if chapter_soup is None and backup_url:
            chapter_soup = await self.get_soup(backup_url)

        img_tags = chapter_soup.find_all("img")
        decimal_ch_num = ch_num.replace("-", ".") if "-" in ch_num else ch_num
        chapter_image_tags = [tag for tag in img_tags if tag.has_attr("title") and tag["title"].strip().startswith(f"{self.comic_soup_name.strip()} Chapter {decimal_ch_num}") and tag.has_attr("src")]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="kingofshojo", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)

class MangaKatana(Downloader):
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
            await self.notify_error(f"Mangakatana.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
        
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
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
            await self.notify_error(f"Toonily.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
    
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
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="toonily", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)

class MangaFire(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
        url_pattern = r"mfcdn\d\.xyz\/mf"
        chapter_image_tags = [tag for tag in img_tags if tag.has_attr("src") and re.search(url_pattern, tag["src"])]
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="mangafire", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)

class VortexScans(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
        # self.dev_tag(f'vortexscans __INIT__ self.comic_template_url: {self.comic_template_url}')
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
        comic_soup: Optional[BeautifulSoup]  = await self.get_pwsoup_buttons(self.comic_url)
        if comic_soup is None:
            await self.notify_error(f"Vortexscans.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
    
        comic_soup_name: str = comic_soup.find("h1", class_="text-2xl font-bold leading-[1.5rem] text-foreground").get_text(strip=True)

        comic_cover_img_link: str = comic_soup.find("img", class_="w-full rounded-lg object-cover object-bottom sm:max-h-[400px] h-auto transition-transform duration-300 group-hover:scale-105").get("src").strip()

        comic_status: str = comic_soup.find("div", class_="text-foreground").find_all("div", class_="flex sm:justify-between justify-start items-center gap-2")[0].find("p", class_="font-normal text-xs inline ml-1 text-foreground").get_text(strip=True).lower().capitalize()

        chapters_wrapper = comic_soup.find("div", "mt-4 space-y-2")
        non_premium_chapters_found = [div_tag for div_tag in chapters_wrapper.find_all("div", class_="w-full h-full flex items-center justify-between gap-2 sm:gap-3") if not div_tag.find("div", class_="flex items-center gap-1.5 text-yellow-600 dark:text-yellow-500")]
        chapters_list: list[str] = list(reversed([tag.find("span", class_="text-xs sm:text-sm font-medium").get_text().lower().replace("chapter", "").strip() for tag in non_premium_chapters_found]))
        first_chapter: str = chapters_list[0]
        latest_chapter: str = chapters_list[-1]

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
        chapter_image_tags = chapter_soup.find("div", class_="comic-images-wrapper reader-mode-strip").find_all("img", class_="h-auto w-full object-contain")
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="vortexscans", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)
  
class UToon(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
            await self.notify_error(f"Utoon.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
    
        comic_soup_name: str = comic_soup.find("div", class_="c-breadcrumb-wrapper").find_all("a")[-1].get_text(strip=True)

        comic_cover_img_link: str = comic_soup.find("div", class_="summary_image").find("img").get("src")
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="post-status").find_all("div", class_="summary-content")[-1].get_text(strip=True).lower()
        
        chapters_list_wrapper = comic_soup.select('ul.main.version-chap.no-volumn li.wp-manga-chapter.has-thumb.free-chap')
        chapters_list: list[str] = list(reversed([tag.find("a").text.replace("Chapter", "").replace("(Fixed)", "fixed").strip().replace(" ", "-") for tag in chapters_list_wrapper]))
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
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="utoon", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)

class HiveToon(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
            await self.notify_error(f"HiveToon.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
    
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
        return await self.get_valid_image_links(tag_list=chapter_image_tags, domain_name="hivetoon", src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num)

class ArenaScans(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
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
        self.backup_template_url: str = f"{self.protocol}/{self.url_comic_name}-chapter-{{}}"
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
            await self.notify_error(f"ArenaScans.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
    
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
        backup_chapter_url: str = self.backup_template_url.format(ch_num)
        
        chapter_image_wrappers = None
        
        chapter_soup: BeautifulSoup = await self.get_soup(comic_chapter_url)
        if chapter_soup:
            chapter_image_wrappers = chapter_soup.find("div", id="readerarea")
        
        if not chapter_image_wrappers:
            dynamic_soup = await self.get_dynamic_soup(
                url=comic_chapter_url, 
                selector="#readerarea", 
                domain="arenascans"
            )
            if dynamic_soup: 
                chapter_image_wrappers = dynamic_soup.find("div", id="readerarea")
                    
        if not chapter_image_wrappers:
            backup_soup = await self.get_soup(backup_chapter_url)
            if backup_soup:
                chapter_image_wrappers = backup_soup.find("div", id="readerarea")
        
        if not chapter_image_wrappers:
            backup_dynamic_soup = await self.get_dynamic_soup(
                url=backup_chapter_url, 
                selector="#readerarea", 
                domain="arenascans"
            )
            if backup_dynamic_soup:
                chapter_image_wrappers = backup_dynamic_soup.find("div", id="readerarea")
        
        if not chapter_image_wrappers:
            self.dev_tag(f"Failed to find readerarea for chapter {ch_num}")
            return []
        
        chapter_image_tags = chapter_image_wrappers.find_all("img")
        return await self.get_valid_image_links(
            tag_list=chapter_image_tags, 
            domain_name="arenascans", 
            src_value="src", comic_name=self.comic_soup_name, chapter_num=ch_num
        )

class GenZToons(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name
        self.protocol: str = "https://genzupdates.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "genztoons")
        self.comic_uid = self.given_config[2]
        self.release_day = self.given_config[3]
        self.is_completed = self.given_config[4]

        self.comic_url: str = f"{self.protocol}/series/{self.url_comic_name}/"
        self.panel_tag(f'{color_msg('lightyellow', 'self.url_comic_name:')} {color_msg('white', self.url_comic_name)}')
        self.panel_tag(f'{color_msg('lightyellow', 'self.comic_url:')} {color_msg('white', self.comic_url)}')

    async def initialize(self):
        details = await self.get_comic_details()
        self.comic_soup_name: str       = details["soup_name"]
        self.comic_cover_img_link: str  = details["cover_img_link"]
        self.comic_status: str          = details["status"]
        self.chapters_list: list[str]   = details["chapters_list"]
        self.chapters_link_list: list[str] = details['chapters_link_list']
        self.first_chapter: str         = details["first_chapter"]
        self.latest_chapter: str        = details["latest_chapter"]
        self.generated_config: list[str] = [self.comic_soup_name, "genztoons", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_soup(self.comic_url)
        if comic_soup is None:
            await self.notify_error(f"GenZToons.get_comic_details():\n > Failed to fetch comic page: {self.comic_url}")
    
        comic_soup_name: str = comic_soup.select_one("h1.text-2xl.font-semibold").get_text(strip=True)

        comic_cover_img_tag = comic_soup.find("div", class_="rounded-lg w-full bg-[image:--photoURL] aspect-[0.75/1] bg-cover bg-center bg-white/10 relative overflow-hidden")
        comic_cover_img_link: str | None = self.get_style_url(comic_cover_img_tag)
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("div", class_="w-full flex gap-3 flex-wrap").find_all("div", class_="grid gap-2 h-fit")[-1].find("div", class_="min-h-8 py-1 px-3 flex justify-center items-center bg-white/10 hover:bg-white/20 transition-all rounded-lg w-fit uppercase").get_text(strip=True).capitalize()

        chapters_found = comic_soup.find("div", id="chapters").find_all("a", class_="group cursor-pointer relative overflow-hidden grid sm:gap-4 gap-[4vw] hover:bg-white/20 bg-white/10 rounded-2xl sm:p-2 p-[2vw] transition-all")
        non_premium_chapters: list[str] = list(reversed([
            tag for tag in chapters_found 
            if not tag.find("div", class_="flex gap-1 justify-center items-center w-fit bg-yellow-200 text-yellow-600 border-yellow-200 pl-1 pr-1.5 h-5 bg-opacity-90 rounded-full")
        ]))
        chapters_link_list: list[str] = [
            f"{self.protocol}{tag.get("href")}" 
            for tag in non_premium_chapters
        ]
        chapters_list: list[str] = [
            tag.select_one("span.text-sm.truncate").get_text(strip=True).lower().replace("chapter", "").strip() 
            for tag in non_premium_chapters
        ]
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

    async def get_chapter_links_list(self) -> list[str]:
        return self.chapters_link_list
    
    def get_comic_soup_name(self) -> str:
        return self.comic_soup_name
    
    def get_first_chapter(self) -> str:
        return self.first_chapter

    def get_latest_chapter(self) -> str:
        return self.latest_chapter

    def get_chapters_list(self) -> list[str]:
        return self.chapters_list
    
    async def get_chapter_image_links(self, ch_num: int, chapter_url: str) -> list[str]:
        chapter_image_links = await self.get_soup_images_from_wrapper_after_scroll(
            chapter_url=chapter_url, 
            wrapper_selector="#pages_panel", 
            not_in_src_word="placeholder"
        )
        return chapter_image_links

class ManhwaRead(Downloader):
    def __init__(self, given_config: list[str], comic_name: str, headers=None, async_client=None, archivist_inst=None):
        super().__init__(headers, async_client, archivist_inst)
        self.given_config: list[str] = given_config
        self.comic_name: str = comic_name
        self.protocol: str = "https://manhwaread.com"
        self.url_comic_name: str = self.get_url_comic_name(self.comic_name, "manhwaread")

        self.comic_url: str = f"{self.protocol}/manhwa/{self.url_comic_name}/"
        self.comic_template_url: str = f"{self.comic_url}chapter-{{}}/"

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
        self.generated_config: list[str] = [self.comic_soup_name, "manhwaread", 0, "everyday", True if self.comic_status != "ongoing" else False]
        if self.generated_config != self.given_config:
            self.configs_to_be_updated.append(self.generated_config)

        if self.dev_mode == 1:
            for k, v in details.items():
                print(f'{k}: {v}')

    async def get_comic_details(self) -> dict:
        comic_soup: Optional[BeautifulSoup] = await self.get_pwsoup_buttons(self.comic_url, domain_name="manhwaread")
    
        comic_soup_name: str = comic_soup.find("div", class_="manga-titles grow").find("h1").get_text(strip=True)

        comic_cover_img_link: str = comic_soup.find("div", class_="flex justify-center sm:max-w-sm w-full xl:max-w-full").find("img").get("src").strip()
        await self.process_cover_image(comic_cover_img_link)

        comic_status: str = comic_soup.find("span", class_="manga-status flex items-center gap-2").get("data-status").strip()

        chapter_wrapper = comic_soup.find("div", id="groupChapterList").find_all("a", class_="chapter-item")
        chapters_list: list[str] = []
        for tag in chapter_wrapper:
            raw_text: str = tag.find("span", class_="text-gray-50 chapter-item__name").get_text().lower().replace("chapter", "").strip()
            # print(f'raw_text: {raw_text}')
            chapter_number: str = re.sub(r'-+', '-', raw_text.replace(" ", "-"))
            # print(f'chapter_number: {chapter_number}')
            chapters_list.append(chapter_number)

        # print(f'get_comic_details().chapters_list: {chapters_list}')
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
    

""" HELPER FUNCTIONS """

def create_async_client(headers: dict[str, str]) -> httpx.AsyncClient:
    timeout = httpx.Timeout(connect=10.0, read=90.0, write=15.0, pool=10.0)
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=15)
    return httpx.AsyncClient(headers=headers, timeout=timeout, limits=limits, follow_redirects=True)

async def reset_dir(npath: str) -> None:
    """deletes and recreates a directory at npath"""
    if os.path.exists(npath):
        shutil.rmtree(npath)
    if not os.path.exists(npath):
        os.mkdir(npath)

def setup_aero_dir(aero_dir: str):
    os.makedirs(aero_dir, exist_ok=True)
    if os.path.exists("Aeronaeum"):
        files = os.listdir(os.path.join(os.getcwd(), "Aeronaeum"))
        for file in files: 
            full_path_filepath = os.path.join(os.getcwd(), "Aeronaeum", file)
            if os.path.isdir(full_path_filepath): 
                shutil.rmtree(full_path_filepath)
    print(f'Deleted Incomplete Epub Directories...\n\n')
    return

def format_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"
    
def get_folder_size(path: str) -> str:
    try:
        result = subprocess.run(
            ["du", "-sb", path],
            capture_output=True,
            text=True,
            check=True
        )
        size_bytes = int(result.stdout.split()[0])
        return format_size(size_bytes)
    except subprocess.CalledProcessError as e:
        return f"Error: {e}"
    
async def main():
    load_dotenv(".env")

    ImageFile.LOAD_TRUNCATED_IMAGES = True
    start_time: float = time.time()
    today_day = dt.datetime.now().strftime("%A").lower()

    current_config: str     = os.path.join(os.getcwd(), "catalogue.json")
    merger_config_fp: str   = os.path.join(os.getcwd(), "catalogue_db.json")
    synopsis = Synopsis(current_config, merger_filepath=merger_config_fp)

    headers: dict[str, str] = { 
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0", 
        "Accept": "image/*" 
    }
    async_client: httpx.AsyncClient = create_async_client(headers)

    archivist_inst = Archivist(async_client)
    bot_task = asyncio.create_task(archivist_inst.run_bot())
    # await asyncio.sleep(5)

    catalogue: list[list[str, str]] = synopsis.get_config_comics()
    print(color_msg("green", f"Found {len(catalogue)} comics to scrape."))

    TEMP_DIR: str = os.path.join(os.getcwd(), "temp")
    await reset_dir(TEMP_DIR)

    my_controls = ControlPanel(headers, async_client, archivist_inst)
    print("bookshelf directory has been reset")
    
    ComicProgress()
    print('comic progress cross-checked with catalogue')

    num_str_list = [str(idx) for idx in range(0, 10)]
    alphabet_list = list("+-ABCDEFGHIJKLMNOPQR")
    ignore_list = num_str_list + alphabet_list

    """ setup aeronaeum """
    aero_dirname: str = "Aeronaeum"
    setup_aero_dir(aero_dirname)
    downloaded_epubs: list[str] = [filename for filename in os.listdir(os.path.join(os.getcwd(), aero_dirname)) if filename.endswith(".epub")]
    ebooks = []

    selected_comics: list[str] = [
        "Switch ON Season 2",
        "SSS-Class Undercover Agent",
        "CCTV",
        "Cleaning Service",
        "1 Second",
        "Eleceed",
        "Astral Pet Store",
        "A World-Class Walkthrough",
        "My Wife Is a Heavenly Big Shot",
        "My Wife and I Dominate the Three Realms",
        "Reality Quest",
        "Bug Player",
        "Superhuman Era",
        "Genius Martial Arts Trainer",
        "How I Became an SSS Rank Delivery Hunter",
        "Emperor of Solo Play",
        "Return of the Mount Hua Sect",
        "Solo Leveling: Ragnarok",
        "Stockpiling Ten Thousand Tons of Pork During the Apocalypse",
    ]

    ignore_chars = set('ABCDEFGH123456789+/[')
    await my_controls.notify_message(f'> Starting to scrape!')

    print(color_msg("lightcyan", f"[MEM] Bookshelf: {get_folder_size("Bookshelf")}"))
    print(color_msg("lightcyan", f"[MEM] cover_images: {get_folder_size("cover_images")}"))
    print(color_msg("lightcyan", f"[MEM] Aeronaeum: {get_folder_size("Aeronaeum")}"))
    for comic_config in catalogue:
        comic_name = comic_config[0]
        comic_dirpath: str = os.path.join("Bookshelf", comic_name.replace("/", ""))
        if not os.path.exists(comic_dirpath): 
            print(color_msg("lightcyan", f"[MEM] {comic_name}: 0 B"))
        else:
            print(color_msg("lightcyan", f"[MEM] {comic_name}: {get_folder_size(comic_dirpath)}"))
        domain_name = comic_config[1]
        first_letter = comic_name[0]
        if domain_name in ["mangafire", "ravenscans"]: continue
        # if domain_name == "genztoons": continue
        # if first_letter in ignore_chars: continue
        # if comic_name != "I Alone Have An EX-Rank Summon": continue
        if first_letter == "N": 
            raise ValueError(f' lol just stopping to check the mem for bookshelf')

        await my_controls.comic_redirect(comic_config)
        await asyncio.sleep(2)

        # if comic_name not in selected_comics:
        #     check_filename = f"{comic_name}.epub"
        #     if check_filename in downloaded_epubs:
        #         print(f'\n{check_filename} is already in the Aeronaeum. Skipping...\n--------------------------------')
        #         continue
        #     ebook = Ebook(comic_name)
        #     ebook.build()
        #     ebook_filepath = ebook.get_epub_filepath()
        #     print(f'Epub Written: {ebook_filepath}\n\n--------------------------------')
        #     ebooks.append(ebook_filepath)
        #     await asyncio.sleep(2)

    # Clean shutdown
    progress_comics = my_controls.get_progress_comics()
    print(f'\nprogress comics: {len(progress_comics)}')

    failed_fetches = my_controls.get_failed_fetches()
    print(f'\nfailed fetches: {len(failed_fetches)}')
    for idx in failed_fetches: 
        print(idx)

    configs_to_update = my_controls.configs_to_be_updated
    print(f'\nconfigs to be updated: {len(configs_to_update)}')
    for idx in configs_to_update: 
        print(idx)
    
    # Shut down the bot
    print(color_msg("red", "Shutting down Discord bot..."))
    await archivist_inst.close_bot()
    bot_task.cancel()
    
    # Close the async client
    await async_client.aclose()
    
    print(color_msg("green", "Shutdown complete."))

if __name__ == "__main__":
    asyncio.run(main())
