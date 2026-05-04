import os, json
from scripts.utils.utils import color_msg

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
 