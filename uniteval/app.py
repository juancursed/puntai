"""
app.py — Construye la aplicación FastAPI: API, archivos estáticos e interfaz.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from uniteval import __version__
from uniteval.config import STATIC_DIR, TEMPLATES_DIR
from uniteval.routes import router

app = FastAPI(title="UnitEval API", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR, check_dir=False), name="static")
app.include_router(router)


@app.get("/")
async def index():
    return FileResponse(TEMPLATES_DIR / "index.html")
