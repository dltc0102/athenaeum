from fastapi import APIRouter, BackgroundTasks
import subprocess
import sys

scraper_router = APIRouter()

def run_scraper():
    subprocess.run(
        [sys.executable, "scraper.py"],
        cwd="/home/dltc0102/athenaeum",
    )

@scraper_router.post("/scraper/run")
def trigger_scraper(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scraper)
    return {"status": "scraper started"}
