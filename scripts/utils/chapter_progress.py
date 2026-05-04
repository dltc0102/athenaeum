from tqdm import tqdm

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
