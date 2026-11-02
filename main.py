"""
UnitEval - Evaluador de pruebas unitarias con IA
Ejecutar con: python main.py
"""

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv, set_key
import json
import os

from scanner import scan_project
from runner import run_tests
from ai_client import analyze_test
from source_resolver import find_source_code
import reports

app = FastAPI(title="UnitEval API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="frontend/static", check_dir=False), name="static")

# ---------- Modelos de datos ----------

class ProjectRequest(BaseModel):
    path: str

class AnalyzeRequest(BaseModel):
    project_path: str
    test_file: str
    test_name: str
    test_code: str
    test_result: str  # PASS | FAIL | ERROR | SKIP
    model: str = "claude"  # claude | openai | laguna

class ReportPayload(BaseModel):
    id: str | None = None
    project_path: str = ""
    model: str = ""
    summary: dict = {}
    scanned_tests: list = []
    run_results: list = []
    analyses: dict = {}

class ConfigUpdate(BaseModel):
    project_path: str = ""
    model: str = "claude"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = "poolside/laguna-s-2.1"

# ---------- Config en disco ----------

CONFIG_FILE = Path("config.json")
ENV_FILE = Path(".env")

# Las claves viven solo en variables de entorno, nunca en config.json.
KEY_ENV_VARS = {
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "openai_api_key": "OPENAI_API_KEY",
    "openrouter_api_key": "LAGUNA_API_KEY",
}

load_dotenv(ENV_FILE)

def load_config() -> dict:
    defaults = {
        "project_path": "",
        "model": "claude",
        "openrouter_model": "poolside/laguna-s-2.1",
    }
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return {**defaults, **json.load(f)}
    return defaults

def save_config(data: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def store_api_key(env_var: str, value: str):
    """Guarda la clave en .env y la activa sin reiniciar el servidor."""
    set_key(ENV_FILE, env_var, value)
    os.environ[env_var] = value

# ---------- Rutas ----------

@app.get("/")
async def index():
    return FileResponse("frontend/templates/index.html")

@app.get("/api/config")
async def get_config():
    """Devuelve la configuración; de las claves solo indica si están definidas."""
    configured = {field: bool(os.environ.get(var)) for field, var in KEY_ENV_VARS.items()}
    return {**load_config(), "configured_keys": configured}

@app.post("/api/config")
async def update_config(body: ConfigUpdate):
    data = body.model_dump()
    for field, env_var in KEY_ENV_VARS.items():
        value = data.pop(field).strip()
        if value:  # Un campo vacío conserva la clave actual
            store_api_key(env_var, value)
    save_config({**load_config(), **data})
    return {"ok": True}

@app.post("/api/scan", responses={400: {"description": "Ruta del proyecto inválida"}})
async def scan(body: ProjectRequest):
    """Escanea el proyecto y devuelve todos los archivos y funciones de prueba."""
    result = scan_project(body.path)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/run", responses={400: {"description": "Error al ejecutar pruebas en la ruta indicada"}})
async def run(body: ProjectRequest):
    """Ejecuta pytest en el proyecto y devuelve resultados."""
    result = run_tests(body.path)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/analyze", responses={400: {"description": "API key no configurada"}})
async def analyze(body: AnalyzeRequest):
    """Envía una prueba y el código fuente que evalúa a la IA y devuelve el análisis."""
    cfg = load_config()
    api_keys = {
        "claude": os.environ.get(KEY_ENV_VARS["anthropic_api_key"]),
        "openai": os.environ.get(KEY_ENV_VARS["openai_api_key"]),
        "laguna": os.environ.get(KEY_ENV_VARS["openrouter_api_key"]),
    }
    api_key = api_keys.get(body.model)

    if not api_key:
        raise HTTPException(status_code=400, detail=f"API key para '{body.model}' no configurada.")

    source = find_source_code(body.project_path, body.test_file, body.test_name)

    result = await analyze_test(
        test_name=body.test_name,
        test_code=body.test_code,
        test_result=body.test_result,
        model=body.model,
        api_key=api_key,
        openrouter_model=cfg.get("openrouter_model") or "poolside/laguna-s-2.1",
        source_code=source["code"],
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {
        **result,
        "source_code": source["code"],
        "source_files": source["files"],
        "source_truncated": source["truncated"],
    }

@app.get("/api/reports")
async def list_saved_reports():
    """Lista las evaluaciones guardadas, de la más reciente a la más antigua."""
    return reports.list_reports()

@app.post("/api/reports", responses={400: {"description": "Identificador inválido"}})
async def save_saved_report(body: ReportPayload):
    """Guarda el reporte general; con id actualiza una evaluación existente."""
    if body.id is not None and not reports.is_valid_id(body.id):
        raise HTTPException(status_code=400, detail="Identificador de reporte inválido.")
    return reports.save_report(body.model_dump(exclude={"id"}), body.id)

@app.get("/api/reports/{report_id}", responses={404: {"description": "Reporte no encontrado"}})
async def get_saved_report(report_id: str):
    """Devuelve una evaluación guardada completa."""
    report = reports.get_report(report_id) if reports.is_valid_id(report_id) else None
    if report is None:
        raise HTTPException(status_code=404, detail="Reporte no encontrado.")
    return report

if __name__ == "__main__":
    print("\n🔬 UnitEval arrancando en http://localhost:6060\n")
    uvicorn.run("main:app", host="127.0.0.1", port=6060, reload=True)
