from fastapi import APIRouter, HTTPException, Query

from .utils import (
    load_json,
    save_json,
    list_comics,
    get_cover_filename,
    get_chapters,
    get_chapter_images,
    PROGRESS_PATH,
    FAVORITES_PATH,
    ARCHIVE_PATH,
)

comic_router = APIRouter(tags=["comics"])

@comic_router.get("/home")
def get_home(
    search: str = "",
    sort: str = Query("alphabetical", enum=["alphabetical", "chapters", "progress"]),
):
    progress = load_json(PROGRESS_PATH, {})
    favorites = load_json(FAVORITES_PATH, [])
    archive = load_json(ARCHIVE_PATH, [])

    comics = []

    for comic_name in list_comics():
        if search and search.lower() not in comic_name.lower():
            continue

        chapters = get_chapters(comic_name)
        total_chapters = len(chapters)
        current_chapter = str(progress.get(comic_name, "0"))

        try:
            current_index = chapters.index(current_chapter) + 1
        except ValueError:
            current_index = 0

        percentage = round((current_index / total_chapters) * 100, 1) if total_chapters else 0

        cover_filename = get_cover_filename(comic_name)

        comics.append({
            "name": comic_name,
            "cover_url": f"/covers/{cover_filename}" if cover_filename else None,
            "current_chapter": current_chapter,
            "read_chapters": current_index,
            "total_chapters": total_chapters,
            "progress_percentage": percentage,
            "is_favorite": comic_name in favorites,
            "is_archived": comic_name in archive,
        })

    if sort == "alphabetical":
        comics.sort(key=lambda comic: comic["name"].lower())

    if sort == "chapters":
        comics.sort(key=lambda comic: comic["total_chapters"], reverse=True)
    
    if sort == "progress":
        comics.sort(key=lambda comic: comic["progress_percentage"], reverse=True)

    return {
        "favorites": [comic for comic in comics if comic["is_favorite"]],
        "recently_read": comics[:10],
        "recently_updated": comics[:10],
        "all_comics": comics,
    }

@comic_router.get("/comics/{comic_name}/chapters")
def list_chapters(comic_name: str):
    chapters = get_chapters(comic_name)

    if not chapters:
        raise HTTPException(status_code=404, detail="No chapters found")

    return {
        "comic_name": comic_name,
        "chapters": chapters,
    }

@comic_router.get("/comics/{comic_name}/chapters/{chapter_num}")
def read_chapter(comic_name: str, chapter_num: str):
    chapters = get_chapters(comic_name)

    if chapter_num not in chapters:
        raise HTTPException(status_code=404, detail="Chapter not found")

    images = get_chapter_images(comic_name, chapter_num)

    current_index = chapters.index(chapter_num)
    next_chapter = chapters[current_index + 1] if current_index + 1 < len(chapters) else None

    return {
        "comic_name": comic_name,
        "chapter_num": chapter_num,
        "chapters": chapters,
        "images": [
            f"/pages/{comic_name}/{filename}"
            for filename in images
        ],
        "next_chapter": next_chapter,
        "is_latest_chapter": next_chapter is None,
    }

@comic_router.patch("/comics/{comic_name}/favorite")
def toggle_favorite(comic_name: str):
    favorites = load_json(FAVORITES_PATH, [])

    if comic_name in favorites:
        favorites.remove(comic_name)
        is_favorite = False
    else:
        favorites.append(comic_name)
        is_favorite = True

    save_json(FAVORITES_PATH, favorites)

    return {
        "comic_name": comic_name,
        "is_favorite": is_favorite,
    }

@comic_router.patch("/comics/{comic_name}/archive")
def toggle_archive(comic_name: str):
    archive = load_json(ARCHIVE_PATH, [])

    if comic_name in archive:
        archive.remove(comic_name)
        is_archived = False
    else:
        archive.append(comic_name)
        is_archived = True

    save_json(ARCHIVE_PATH, archive)

    return {
        "comic_name": comic_name,
        "is_archived": is_archived,
    }