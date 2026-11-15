"""
config.py — Rutas del proyecto y configuración persistente de UnitEval.

La configuración general (ruta del proyecto, modelo) se guarda en config.json.
Las API keys viven solo en variables de entorno / .env, nunca en config.json.

En Vercel (variable VERCEL definida) la app funciona en modo demo de solo lectura:
evalúa únicamente el proyecto de ejemplo incluido en el repo, las claves vienen
de las variables de entorno del panel de Vercel y los reportes van a /tmp.
"""

import json
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv, set_key

# ── Rutas ───────────────────────────────────────────────────────────────────

# Vercel define VERCEL=1 en sus funciones; su disco solo es escribible en /tmp.
IS_VERCEL = bool(os.environ.get("VERCEL"))

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"
CONFIG_FILE = ROOT_DIR / "config.json"
ENV_FILE = ROOT_DIR / ".env"
DEMO_PROJECT_DIR = ROOT_DIR / "Proyecto_test" / "proyecto_test_tg"
REPORTS_DIR = (
    Path(tempfile.gettempdir()) / "uniteval-reports" if IS_VERCEL else ROOT_DIR / "reports"
)

# ── Valores por defecto ─────────────────────────────────────────────────────

DEFAULT_MODEL = "claude"
DEFAULT_OPENROUTER_MODEL = "poolside/laguna-s-2.1"
DEFAULT_PORT = 6060

# Campo del formulario de configuración → variable de entorno con la clave.
KEY_ENV_VARS = {
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "openai_api_key": "OPENAI_API_KEY",
    "openrouter_api_key": "LAGUNA_API_KEY",
}

# Modelo de IA → campo de su clave.
MODEL_KEY_FIELDS = {
    "claude": "anthropic_api_key",
    "openai": "openai_api_key",
    "laguna": "openrouter_api_key",
}

load_dotenv(ENV_FILE)


# ── config.json ─────────────────────────────────────────────────────────────

def load_config() -> dict:
    defaults = {
        "project_path": "",
        "model": DEFAULT_MODEL,
        "openrouter_model": DEFAULT_OPENROUTER_MODEL,
    }
    if IS_VERCEL:
        # Por defecto, el primer modelo cuya clave se configuró en el panel de Vercel.
        model = next((m for m in MODEL_KEY_FIELDS if api_key_for(m)), DEFAULT_MODEL)
        return {**defaults, "project_path": str(DEMO_PROJECT_DIR), "model": model}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return {**defaults, **json.load(f)}
    return defaults


def save_config(data: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── API keys ────────────────────────────────────────────────────────────────

def store_api_key(env_var: str, value: str) -> None:
    """Guarda la clave en .env y la activa sin reiniciar el servidor."""
    set_key(ENV_FILE, env_var, value)
    os.environ[env_var] = value


def configured_keys() -> dict[str, bool]:
    """Indica qué claves están definidas, sin exponer su valor."""
    return {field: bool(os.environ.get(var)) for field, var in KEY_ENV_VARS.items()}


def is_allowed_project(path: str) -> bool:
    """En el modo demo solo se puede evaluar el proyecto de ejemplo incluido."""
    if not IS_VERCEL:
        return True
    resolved = Path(path).expanduser().resolve()
    return resolved == DEMO_PROJECT_DIR.resolve()


def api_key_for(model: str) -> str | None:
    field = MODEL_KEY_FIELDS.get(model)
    return os.environ.get(KEY_ENV_VARS[field]) if field else None
