"""
routes.py — Endpoints REST de UnitEval (/api/...).
"""

from fastapi import APIRouter, HTTPException

from uniteval import config, reports
from uniteval.ai import analyze_test
from uniteval.core.runner import run_tests
from uniteval.core.scanner import scan_project
from uniteval.core.source_resolver import find_source_code
from uniteval.schemas import AnalyzeRequest, ConfigUpdate, ProjectRequest, ReportPayload

router = APIRouter(prefix="/api")


def _check_project(path: str) -> None:
    if not config.is_allowed_project(path):
        raise HTTPException(
            status_code=403,
            detail="En la demo en línea solo se puede evaluar el proyecto de ejemplo incluido.",
        )


def _raise_on_error(result: dict, status_code: int = 400) -> dict:
    if "error" in result:
        raise HTTPException(status_code=status_code, detail=result["error"])
    return result


# ── Configuración ───────────────────────────────────────────────────────────

@router.get("/config")
async def get_config():
    """Devuelve la configuración; de las claves solo indica si están definidas."""
    return {
        **config.load_config(),
        "configured_keys": config.configured_keys(),
        "read_only": config.IS_VERCEL,
    }


@router.post("/config", responses={403: {"description": "Configuración de solo lectura (demo)"}})
async def update_config(body: ConfigUpdate):
    if config.IS_VERCEL:
        raise HTTPException(status_code=403, detail="La configuración de la demo en línea es de solo lectura.")
    data = body.model_dump()
    for field, env_var in config.KEY_ENV_VARS.items():
        value = data.pop(field).strip()
        if value:  # Un campo vacío conserva la clave actual
            config.store_api_key(env_var, value)
    config.save_config({**config.load_config(), **data})
    return {"ok": True}


# ── Pruebas ─────────────────────────────────────────────────────────────────

@router.post("/scan", responses={400: {"description": "Ruta del proyecto inválida"}})
async def scan(body: ProjectRequest):
    """Escanea el proyecto y devuelve todos los archivos y funciones de prueba."""
    _check_project(body.path)
    return _raise_on_error(scan_project(body.path))


@router.post("/run", responses={400: {"description": "Error al ejecutar pruebas en la ruta indicada"}})
async def run(body: ProjectRequest):
    """Ejecuta pytest en el proyecto y devuelve resultados."""
    _check_project(body.path)
    return _raise_on_error(run_tests(body.path))


@router.post("/analyze", responses={400: {"description": "API key no configurada"}})
async def analyze(body: AnalyzeRequest):
    """Envía una prueba y el código fuente que evalúa a la IA y devuelve el análisis."""
    _check_project(body.project_path)
    api_key = config.api_key_for(body.model)
    if not api_key:
        raise HTTPException(status_code=400, detail=f"API key para '{body.model}' no configurada.")

    source = find_source_code(body.project_path, body.test_file, body.test_name)
    result = await analyze_test(
        test_name=body.test_name,
        test_code=body.test_code,
        test_result=body.test_result,
        model=body.model,
        api_key=api_key,
        openrouter_model=config.load_config().get("openrouter_model") or config.DEFAULT_OPENROUTER_MODEL,
        source_code=source["code"],
    )
    _raise_on_error(result)
    return {
        **result,
        "source_code": source["code"],
        "source_files": source["files"],
        "source_truncated": source["truncated"],
    }


# ── Reportes ────────────────────────────────────────────────────────────────

@router.get("/reports")
async def list_saved_reports():
    """Lista las evaluaciones guardadas, de la más reciente a la más antigua."""
    return reports.list_reports()


@router.post("/reports", responses={400: {"description": "Identificador inválido"}})
async def save_saved_report(body: ReportPayload):
    """Guarda el reporte general; con id actualiza una evaluación existente."""
    if body.id is not None and not reports.is_valid_id(body.id):
        raise HTTPException(status_code=400, detail="Identificador de reporte inválido.")
    return reports.save_report(body.model_dump(exclude={"id"}), body.id)


@router.get("/reports/{report_id}", responses={404: {"description": "Reporte no encontrado"}})
async def get_saved_report(report_id: str):
    """Devuelve una evaluación guardada completa."""
    report = reports.get_report(report_id) if reports.is_valid_id(report_id) else None
    if report is None:
        raise HTTPException(status_code=404, detail="Reporte no encontrado.")
    return report
