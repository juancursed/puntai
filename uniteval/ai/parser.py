"""
parser.py — Convierte la respuesta de texto de la IA en un análisis estructurado.

El prompt pide una evaluación en cuatro pasos; si el modelo responde en JSON
(formato antiguo) también se acepta.
"""

import json
import re

STEP_TITLES = {
    1: "Cobertura y refactorización",
    2: "Detección de flakiness",
    3: "Adecuación y mutaciones",
    4: "Veredicto final",
}
MAX_SCORE = 5

_SCORE_RE = re.compile(r"(?<![\d.,])([1-5](?:[.,]\d)?)\s*/\s*5(?!\d)")
_SCORE_LABEL_RE = re.compile(
    r"^[\s*_#]*(?:Calificaci[oó]n[\s*_:]*)?\d(?:[.,]\d)?\s*/\s*5[\s*_.:,;\-–—]*",
    flags=re.IGNORECASE,
)
_JUSTIFICATION_LABEL_RE = re.compile(
    r"^[\s*_#]*Justificaci[oó]n[*_\s]*:[*_]{0,2}\s*",
    flags=re.IGNORECASE,
)
_SEPARATOR_RE = re.compile(r"\n\s*-{3,}\s*(?:\n|\Z)")
_RECOMMENDATIONS_RE = re.compile(
    r"#*\s*[*_]{0,2}Recomendaci[oó]n(?:es)?(?: de mejora)?[*_]{0,2}\s*:\s*[*_]{0,2}",
    flags=re.IGNORECASE,
)


def parse_ai_response(raw: str) -> dict:
    """Parsea la respuesta de la IA (evaluación por 4 pasos o JSON)."""
    # Un informe puede citar diccionarios del código, así que los pasos van antes que el JSON.
    steps_parsed = _parse_steps_response(raw)
    if steps_parsed is not None and steps_parsed["steps"]:
        return steps_parsed

    json_parsed = _parse_json_response(raw)
    if json_parsed is not None:
        return json_parsed

    if steps_parsed is not None:
        return steps_parsed

    return {
        "error": "No se pudo parsear la respuesta de la IA.",
        "raw": raw[:500],
    }


# ── Evaluación por pasos ────────────────────────────────────────────────────

def _parse_steps_response(text: str) -> dict | None:
    contents = {num: _extract_step(text, num) for num in STEP_TITLES}
    score = _extract_score(contents[4], text)
    if score is None and not any(contents.values()):
        return None

    has_verdict = bool(contents[4])
    justification, recommendations = _split_verdict(contents[4])
    contents[4] = justification

    return {
        "quality": _quality_label(score),
        "quality_score": score,
        "max_score": MAX_SCORE,
        "summary": justification or text[:240],
        "steps": [
            {"number": num, "title": STEP_TITLES[num], "content": content}
            for num, content in contents.items()
            if content or (num == 4 and has_verdict)
        ],
        "recommendations": recommendations,
    }


def _extract_step(text: str, step_num: int) -> str:
    pattern = (
        rf"Paso\s*{step_num}\s*\([^)]*\)\s*\*{{0,2}}\s*:?\s*\*{{0,2}}\s*"
        rf"(.+?)(?=\n[\s#*\-]*Paso\s*{step_num + 1}\b|\Z)"
    )
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_score(verdict: str, text: str) -> int | float | None:
    """Prioriza el veredicto: el resto del texto puede citar otras fracciones (3/5 ramas)."""
    match = _SCORE_RE.search(verdict) or _SCORE_RE.search(text)
    if match is None:
        return None
    score = float(match.group(1).replace(",", "."))
    return int(score) if score.is_integer() else score


def _split_verdict(verdict: str) -> tuple[str, str]:
    """Separa la justificación de las recomendaciones y quita la nota ya mostrada aparte."""
    # Tras una línea --- los modelos suelen repetir lo ya dicho a modo de resumen.
    verdict = _SEPARATOR_RE.split(verdict, maxsplit=1)[0]
    parts = _RECOMMENDATIONS_RE.split(verdict, maxsplit=1)
    justification = _SCORE_LABEL_RE.sub("", parts[0])
    justification = _JUSTIFICATION_LABEL_RE.sub("", justification).strip()
    recommendations = parts[1].strip() if len(parts) > 1 else ""
    return justification, recommendations


def _quality_label(score: int | float | None) -> str:
    if score is None:
        return ""
    if score >= 4:
        return "alta"
    if score >= 3:
        return "media"
    return "baja"


# ── Respuesta JSON ──────────────────────────────────────────────────────────

def _parse_json_response(raw: str) -> dict | None:
    text = _strip_code_fences(raw.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return None


def _strip_code_fences(text: str) -> str:
    """Quita los bloques ```json ... ``` que algunos modelos añaden."""
    if not text.startswith("```"):
        return text
    lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
    return "\n".join(lines).strip()
