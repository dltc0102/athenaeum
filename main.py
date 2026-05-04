from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from scripts.api.routes_comics import comic_router
from scripts.api.routes_progress import progress_router


app = FastAPI(title="Athenaeum API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/covers", StaticFiles(directory="cover_images"), name="covers")
app.mount("/pages", StaticFiles(directory="Bookshelf"), name="pages")

app.include_router(comic_router, prefix="/api")
app.include_router(progress_router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Athenaeum API is running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8080,
        reload=True,
    )