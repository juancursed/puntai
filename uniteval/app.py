"""
app.py — Construye la aplicación FastAPI: API, archivos estáticos e interfaz.
"""

import os
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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


# Cambia en cada despliegue (commit en Vercel) para que el navegador no use CSS/JS viejos.
ASSET_VERSION = os.environ.get("VERCEL_GIT_COMMIT_SHA", "")[:7] or str(int(time.time()))


@app.get("/", response_class=HTMLResponse)
async def index():
    html = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(
        html.replace("__ASSET_VERSION__", ASSET_VERSION),
        headers={"Cache-Control": "no-cache"},
    )
