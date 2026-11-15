"""
prompts.py — Carga los prompts que se envían a la IA.

El texto vive en archivos Markdown (prompts/system.md y prompts/user.md) para
poder revisarlo y versionarlo sin tocar el código.
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


SYSTEM_PROMPT = _load("system.md")
USER_PROMPT = _load("user.md")


def build_user_message(
    test_name: str,
    test_code: str,
    test_result: str,
    source_code: str = "",
) -> str:
    """Rellena la plantilla de usuario con la prueba y el código que evalúa."""
    codigo_fuente = source_code or (
        f"# No se localizó el código fuente de {test_name} "
        f"(resultado: {test_result.upper()}). Evalúa solo la prueba e indícalo."
    )
    return USER_PROMPT.format(
        codigo_fuente=codigo_fuente,
        codigo_prueba=test_code,
    )
