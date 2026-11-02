"""
reports.py — Guarda en disco los reportes generales de las evaluaciones con IA.

Cada evaluación es un archivo reports/<id>.json con todo lo necesario para volver
a abrirla: pruebas detectadas, resultados de pytest, análisis y resumen.
"""

import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path("reports")

_REPORT_ID_RE = re.compile(r"\d{8}-\d{6}-[0-9a-f]{6}")


def is_valid_id(report_id: str) -> bool:
    """El id forma parte de una ruta: solo se aceptan los que genera este módulo."""
    return _REPORT_ID_RE.fullmatch(report_id) is not None


def _now() -> datetime:
    return datetime.now()


def _path(report_id: str) -> Path:
    return REPORTS_DIR / f"{report_id}.json"


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def save_report(data: dict, report_id: str | None = None) -> dict:
    """Crea un reporte o actualiza uno existente conservando su fecha de creación."""
    now = _now()
    report_id = report_id or f"{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    previous = _read(_path(report_id)) or {}
    timestamp = now.isoformat(timespec="seconds")
    report = {
        **data,
        "id": report_id,
        "created_at": previous.get("created_at", timestamp),
        "updated_at": timestamp,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    # Se escribe aparte y se reemplaza para no dejar un reporte a medias.
    temporary = _path(report_id).with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, _path(report_id))
    return report


def get_report(report_id: str) -> dict | None:
    return _read(_path(report_id))


def list_reports() -> list[dict]:
    """Datos de cada reporte para el historial, del más reciente al más antiguo."""
    if not REPORTS_DIR.exists():
        return []
    fields = ("id", "created_at", "updated_at", "project_path", "model", "summary")
    reports = (_read(path) for path in REPORTS_DIR.glob("*.json"))
    entries = [
        {field: report.get(field) for field in fields}
        for report in reports
        if report is not None
    ]
    return sorted(entries, key=lambda entry: entry["created_at"] or "", reverse=True)
