"""
ai_client.py — Envía pruebas unitarias a la IA y devuelve análisis estructurado.

Soporta:
  - Claude (Anthropic) via API directa
  - OpenAI (GPT-4o)
"""

import httpx
import json


SYSTEM_PROMPT = """Eres un experto en calidad de software y pruebas unitarias con Python y pytest.

Tu tarea es analizar una función de prueba unitaria y devolver un análisis estructurado en JSON.

SIEMPRE responde ÚNICAMENTE con un objeto JSON válido con esta estructura exacta:
{
  "quality": "alta" | "media" | "baja",
  "quality_score": <número 1-10>,
  "summary": "<resumen en 1-2 oraciones de qué hace la prueba>",
  "issues": ["<problema 1>", "<problema 2>", ...],
  "suggestions": ["<sugerencia 1>", "<sugerencia 2>", ...],
  "missing_cases": ["<caso no cubierto 1>", "<caso no cubierto 2>", ...],
  "good_practices": ["<buena práctica encontrada>", ...]
}

Criterios de calidad:
- Alta (8-10): Prueba clara, cubre casos límite, tiene assertions descriptivos, nombre descriptivo.
- Media (5-7): Funcional pero le faltan casos o tiene problemas menores de claridad.
- Baja (1-4): No prueba lo que dice, falta manejo de excepciones esperadas, assertions triviales.

No incluyas explicaciones fuera del JSON. Solo el objeto JSON.
"""


def _build_user_message(test_name: str, test_code: str, test_result: str) -> str:
    return f"""Analiza esta prueba unitaria de Python:

**Nombre:** {test_name}
**Resultado de ejecución:** {test_result.upper()}

**Código:**
```python
{test_code}
```

Devuelve el análisis en JSON según el formato indicado."""


async def analyze_test(
    test_name: str,
    test_code: str,
    test_result: str,
    model: str,
    api_key: str,
) -> dict:
    """
    Analiza una prueba unitaria usando la IA seleccionada.

    Returns:
        Dict con el análisis estructurado o {"error": str} si falla.
    """
    if model == "claude":
        return await _call_claude(test_name, test_code, test_result, api_key)
    elif model == "openai":
        return await _call_openai(test_name, test_code, test_result, api_key)
    else:
        return {"error": f"Modelo '{model}' no soportado."}


async def _call_claude(test_name: str, test_code: str, test_result: str, api_key: str) -> dict:
    """Llama a la API de Anthropic Claude."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": _build_user_message(test_name, test_code, test_result),
            }
        ],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            raw_text = data["content"][0]["text"]
            return _parse_ai_response(raw_text)
        except httpx.HTTPStatusError as e:
            return {"error": f"Error HTTP de Claude: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": f"Error al llamar a Claude: {str(e)}"}


async def _call_openai(test_name: str, test_code: str, test_result: str, api_key: str) -> dict:
    """Llama a la API de OpenAI."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(test_name, test_code, test_result)},
        ],
        "max_tokens": 1024,
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            raw_text = data["choices"][0]["message"]["content"]
            return _parse_ai_response(raw_text)
        except httpx.HTTPStatusError as e:
            return {"error": f"Error HTTP de OpenAI: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": f"Error al llamar a OpenAI: {str(e)}"}


def _parse_ai_response(raw: str) -> dict:
    """
    Parsea la respuesta de la IA. Intenta extraer JSON aunque venga
    envuelto en bloques de código markdown.
    """
    text = raw.strip()

    # Remover bloques ```json ... ```
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Intentar extraer el primer objeto JSON del texto
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return {
            "error": "No se pudo parsear la respuesta de la IA.",
            "raw": raw[:500],
        }
