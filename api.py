from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from pathlib import Path
import os, json, asyncio, shutil, re, mimetypes, subprocess, sys
from datetime import datetime

app = FastAPI(title="Bookshelf API", description="API for managing books, progress and cover images")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Svelte dev server ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

COVER_IMAGES_DIR = Path("cover_images_test")
BOOKSHELF_DIR = Path("Bookshelf_test")
CATALOGUE_PATH = Path("catalogue.json")
PROGRESS_PATH = Path("progress_bup.json")

COVER_IMAGES_DIR.mkdir(exist_ok=True)
BOOKSHELF_DIR.mkdir(exist_ok=True)

class Comic(BaseModel):
    name: str
    domain: str
    comic_uid: Optional[str] = ""
    release_day: Optional[str] = "everyday"
    is_completed: Optional[bool] = False
    cover_image: Optional[str] = None
    status: Optional[str] = "ongoing"

class ComicDetails(Comic):
    chapters: List[str] = []
    total_chapters: int = 0
    downloaded_chapters: int = 0
    progress_percentage: float = 0.0

class Chapter(BaseModel):
    number: str
    pages: List[str] = []
    downloaded: bool = False

class ChapterProgress(BaseModel):
    comic_name: str
    chapter_number: str
    total_pages: int
    downloaded_pages: int

class ProgressUpdate(BaseModel):
    comic_name: str
    progress: int

class ScanRequest(BaseModel):
    comic_name: Optional[str] = None
    domain: Optional[str] = None

class ScrapeStatus(BaseModel):
    running: bool = False
    current_comic: Optional[str] = None
    total_comics: int = 0
    completed_comics: int = 0
    message: Optional[str] = None

def load_file(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(path)
    return data

def load_catalogue() -> list[Comic]:
    comic_objects: list[Comic] = []
    catalogue_data: list[list[str]] = load_file(CATALOGUE_PATH)
    for comic_item in catalogue_data:
        name, domain, comic_uid, release_day, is_completed = comic_item
        comic_objects.append(Comic(
            name=name,
            domain=domain,
            comic_uid=comic_uid,
            release_day=release_day,
            is_completed=is_completed
        ))
    return comic_objects

def load_progress() -> Dict[str, int]:
    progress_data: Dict[str, int] = load_file(PROGRESS_PATH)
    return progress_data

def get_comic_downloaded_chapters(comic_name: str) -> List[str]:
    """Get list of downloaded chapters for a comic"""
    comic_dir = BOOKSHELF_DIR / comic_name
    if not comic_dir.exists():
        return []
    
    chapters = set()
    pattern = r'chapter-(\d+(?:[\.-]\d+)*)-p\d+'
    
    for file in comic_dir.iterdir():
        match = re.search(pattern, file.name)
        if match:
            chapter_str = match.group(1)
            if '-' in chapter_str:
                chapter_str = chapter_str.replace('-', '.')
            chapters.add(chapter_str)
    
    return sorted(chapters, key=lambda x: float(x))

def get_comic_cover_image(comic_name: str) -> Optional[str]:
    filename = comic_name.lower()
    filename = re.sub(r'[^\w\s\-+]', '', filename)
    filename = filename.replace(' ', '_').replace('-', '_')
    filename = re.sub(r'_+', '_', filename)
    filename = filename.strip('_')

    for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
        cover_path = COVER_IMAGES_DIR / f"{filename}{ext}"
        if cover_path.exists():
            return str(cover_path)
    return None

def get_chapter_images(comic_name: str, chapter_number: str) -> List[str]:
    comic_dir = BOOKSHELF_DIR / comic_name
    if not comic_dir.exists():
        return []
    
    safe_chapter = chapter_number.replace('.', '-')
    pattern = re.compile(rf'chapter-{re.escape(safe_chapter)}-p(\d+)\.(jpg|png|webp|gif)')
    
    images = []
    for file in comic_dir.iterdir():
        match = pattern.match(file.name)
        if match:
            page_num = int(match.group(1))
            images.append((page_num, str(file)))
    
    images.sort(key=lambda x: x[0])
    return [img_path for _, img_path in images]

@app.get("/")
async def root():
    return {
        "name": "Comic Bookshelf API",
        "version": "1.0.0",
        "endpoints": {
            "comics": "/comics",
            "comic_details": "/comics/{comic_name}",
            "chapters": "/comics/{comic_name}/chapters",
            "chapter_images": "/comics/{comic_name}/chapters/{chapter_number}",
            "cover_images": "/covers/{comic_name}",
            "progress": "/progress",
            "scrape": "/scrape",
            "scan": "/scan"
        }
    }

