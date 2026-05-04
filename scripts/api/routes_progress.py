from pydantic import BaseModel
from fastapi import APIRouter

from .utils import load_json, save_json, PROGRESS_PATH

progress_router = APIRouter(tags=["progress"])

class ProgressUpdate(BaseModel):
    chapter_num: str

@progress_router.get("/progress/{comic_name}")
def get_progress(comic_name: str):
    progress = load_json(PROGRESS_PATH, {})

    return {
        "comic_name": comic_name,
        "chapter_num": str(progress.get(comic_name, "0")),
    }

@progress_router.put("/progress/{comic_name}")
def update_progress(comic_name: str, data: ProgressUpdate):
    progress = load_json(PROGRESS_PATH, {})
    progress[comic_name] = data.chapter_num
    save_json(PROGRESS_PATH, progress)

    return {
        "comic_name": comic_name,
        "chapter_num": data.chapter_num,
    }