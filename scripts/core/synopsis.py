import os, json, re
from scripts.utils.utils import color_msg
from scripts.utils.comparer import Comparer

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

        self.sorted_config: list[str] = self.sort_temp_config()

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

    def get_config_comics(self) -> dict['comic_name': 'domain_name']:
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
 