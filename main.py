"""
UnitEval - Evaluador de pruebas unitarias con IA
Ejecutar con: python main.py
"""

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import json

from scanner import scan_project
from runner import run_tests
from ai_client import analyze_test

app = FastAPI(title="UnitEval API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# ---------- Modelos de datos ----------

class ProjectRequest(BaseModel):
    path: str

class AnalyzeRequest(BaseModel):
    project_path: str
    test_file: str
    test_name: str
    test_code: str
    test_result: str  # PASS | FAIL | ERROR | SKIP
    model: str = "claude"  # claude | openai

class ConfigUpdate(BaseModel):
    project_path: str = ""
    model: str = "claude"
    anthropic_api_key: str = ""
    openai_api_key: str = ""

# ---------- Config en disco ----------

CONFIG_FILE = Path("config.json")

def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {
        "project_path": "",
        "model": "claude",
        "anthropic_api_key": "",
        "openai_api_key": "",
    }

def save_config(data: dict):
    CONFIG_FILE.write_text(json.dumps(data, indent=2))

# ---------- Rutas ----------

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path("frontend/templates/index.html")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

@app.get("/api/config")
async def get_config():
    return load_config()

@app.post("/api/config")
async def update_config(body: ConfigUpdate):
    cfg = load_config()
    cfg.update(body.model_dump())
    save_config(cfg)
    return {"ok": True}

@app.post("/api/scan")
async def scan(body: ProjectRequest):
    """Escanea el proyecto y devuelve todos los archivos y funciones de prueba."""
    result = scan_project(body.path)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/run")
async def run(body: ProjectRequest):
    """Ejecuta pytest en el proyecto y devuelve resultados."""
    result = run_tests(body.path)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/analyze")
async def analyze(body: AnalyzeRequest):
    """Envía una prueba a la IA y devuelve el análisis."""
    cfg = load_config()
    api_key = cfg.get("anthropic_api_key") if body.model == "claude" else cfg.get("openai_api_key")

    if not api_key:
        raise HTTPException(status_code=400, detail=f"API key para '{body.model}' no configurada.")

    result = await analyze_test(
        test_name=body.test_name,
        test_code=body.test_code,
        test_result=body.test_result,
        model=body.model,
        api_key=api_key,
    )
    return result

if __name__ == "__main__":
    print("\n🔬 UnitEval arrancando en http://localhost:6060\n")
    uvicorn.run("main:app", host="0.0.0.0", port=6060, reload=True)
