"""
ai_client.py — Envía pruebas unitarias a la IA y devuelve análisis estructurado.

Soporta:
  - Claude (Anthropic) via API directa
  - OpenAI (GPT-4o)
  - Laguna (Poolside via OpenRouter)
"""

import json
import re
import httpx


SYSTEM_PROMPT = """# [ROL]

Actúa como un **Ingeniero de Pruebas de Software Senior** y un **Investigador Académico especializado en calidad de software**.

# [CONTEXTO Y OBJETIVO]

Tu objetivo es evaluar la calidad de las pruebas unitarias que te proporcionaré, considerando aspectos como la cobertura, la estabilidad, la adecuación de las aserciones y la capacidad de detectar errores en el código.

# [DESCOMPOSICIÓN DE LA TAREA Y ANÁLISIS PASO A PASO]

Para analizar cada prueba unitaria, debes dividir tu evaluación en los siguientes cuatro pasos:

- **Paso 1 (Cobertura y Refactorización):** Analiza qué métricas de cobertura (líneas, ramas y condiciones) podría alcanzar la prueba. Evalúa también si la prueba está correctamente estructurada y si presenta dependencias innecesarias respecto a la implementación interna del código.

- **Paso 2 (Detección de Flakiness):** Evalúa si existen dependencias de tiempo (por ejemplo, `sleep`), concurrencia, estados compartidos o dependencias externas que puedan provocar resultados inconsistentes entre ejecuciones.

- **Paso 3 (Adecuación y Mutaciones):** Analiza lógicamente si la prueba sobreviviría a pruebas de mutación. Identifica posibles cambios en la implementación que no serían detectados por las aserciones actuales y evalúa si estas verifican correctamente el comportamiento esperado.

- **Paso 4 (Veredicto Final):** Basándote en los análisis anteriores, otorga una calificación de 1 a 5, donde 1 representa una prueba de muy baja calidad y 5 una prueba de excelente calidad. Justifica brevemente la calificación y proporciona recomendaciones de mejora.

# [EJEMPLOS (FEW-SHOT)]

## EJEMPLO 1

**Código de la prueba unitaria:**

```python
def test_user_login_timeout():
    user = User("test_user")
    user.login()
    time.sleep(2)  # Esperar a que el servidor responda
    assert user.is_logged_in == True
```

**Evaluación:**

- **Paso 1 (Cobertura y Refactorización):** La prueba cubre el flujo principal de inicio de sesión. Sin embargo, no contempla escenarios alternativos ni condiciones de error.

- **Paso 2 (Detección de Flakiness):** Existe un alto riesgo de flakiness. El uso de `time.sleep()` introduce una dependencia temporal que puede generar resultados inconsistentes dependiendo del rendimiento del servidor o del entorno de ejecución.

- **Paso 3 (Adecuación y Mutaciones):** La aserción es básica. Un mutante que cambie la lógica de autenticación, pero mantenga el valor de `is_logged_in` en `True`, podría no ser detectado.

- **Paso 4 (Veredicto Final):** Calificación: **2/5**. Recomendación: Eliminar el `time.sleep()` y utilizar mecanismos de sincronización adecuados. Además, incorporar pruebas para escenarios de autenticación fallida.

## EJEMPLO 2

**Código de la prueba unitaria:**

```python
def test_calculate_discount():
    order = Order(100.0)
    discount = DiscountCalculator.apply(order, "VIP")
    assert discount == pytest.approx(20.0, abs=0.001)
```

**Evaluación:**

- **Paso 1 (Cobertura y Refactorización):** Cubre la rama correspondiente al cliente "VIP". Sin embargo, falta cobertura para otros tipos de clientes y condiciones límite.

- **Paso 2 (Detección de Flakiness):** La prueba es determinista y se ejecuta en un solo hilo. No presenta dependencias temporales ni externas que puedan afectar su resultado.

- **Paso 3 (Adecuación y Mutaciones):** La aserción con tolerancia (`0.001`) es adecuada para validar valores de punto flotante. Sin embargo, podrían existir mutaciones en otras ramas de la lógica de descuentos que esta prueba no detectaría.

- **Paso 4 (Veredicto Final):** Calificación: **4/5**. Recomendación: La prueba es sólida y determinista. Se recomienda ampliar los casos de prueba para cubrir otros tipos de clientes y condiciones límite.

# [ENTRADA DEL USUARIO]

Por favor, evalúa la siguiente prueba unitaria siguiendo exactamente los cuatro pasos definidos anteriormente. Basa tu análisis tanto en la prueba como en el código fuente de la función evaluada.
"""

USER_PROMPT = """**Código fuente de la función evaluada:**

```python
{codigo_fuente}
```

**Código de la prueba unitaria:**

```python
{codigo_prueba}
```
"""


def _build_user_message(
    test_name: str,
    test_code: str,
    test_result: str,
    source_code: str = "",
) -> str:
    codigo_fuente = source_code or (
        f"# No se localizó el código fuente de {test_name} "
        f"(resultado: {test_result.upper()}). Evalúa solo la prueba e indícalo."
    )
    return USER_PROMPT.format(
        codigo_fuente=codigo_fuente,
        codigo_prueba=test_code,
    )


async def analyze_test(
    test_name: str,
    test_code: str,
    test_result: str,
    model: str,
    api_key: str,
    openrouter_model: str = "poolside/laguna-s-2.1",
    source_code: str = "",
) -> dict:
    """
    Analiza una prueba unitaria y el código fuente que evalúa con la IA seleccionada.

    Returns:
        Dict con el análisis estructurado o {"error": str} si falla.
    """
    user_message = _build_user_message(test_name, test_code, test_result, source_code)
    if model == "claude":
        return await _call_claude(user_message, api_key)
    elif model == "openai":
        return await _call_openai(user_message, api_key)
    elif model == "laguna":
        return await _call_openrouter(user_message, api_key, openrouter_model)
    else:
        return {"error": f"Modelo '{model}' no soportado."}


async def _call_claude(user_message: str, api_key: str) -> dict:
    """Llama a la API de Anthropic Claude."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2048,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_message}],
    }

    async with httpx.AsyncClient(timeout=60) as client:
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


async def _call_openai(user_message: str, api_key: str) -> dict:
    """Llama a la API de OpenAI."""
    return await _call_openai_compatible(
        url="https://api.openai.com/v1/chat/completions",
        model_id="gpt-4o",
        provider_name="OpenAI",
        user_message=user_message,
        api_key=api_key,
    )


async def _call_openrouter(
    user_message: str,
    api_key: str,
    model_id: str = "poolside/laguna-s-2.1",
) -> dict:
    """Llama a Laguna S 2.1 vía Poolside Platform, NVIDIA NIM u OpenRouter."""
    if api_key.startswith("sk-or-"):
        url = "https://openrouter.ai/api/v1/chat/completions"
        provider_name = "OpenRouter"
    elif api_key.startswith("nvapi-"):
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        provider_name = "NVIDIA NIM"
        # NVIDIA NIM solo aloja la variante XS de Laguna 2.1
        if model_id == "poolside/laguna-s-2.1":
            model_id = "poolside/laguna-xs-2.1"
    else:
        url = "https://inference.poolside.ai/v1/chat/completions"
        provider_name = "Poolside"

    return await _call_openai_compatible(
        url=url,
        model_id=model_id,
        provider_name=provider_name,
        user_message=user_message,
        api_key=api_key,
    )


async def _call_openai_compatible(
    url: str,
    model_id: str,
    provider_name: str,
    user_message: str,
    api_key: str,
) -> dict:
    """Llama a un endpoint compatible con OpenAI Chat Completions."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 2048,
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            message = data["choices"][0]["message"]
            raw_text = message.get("content") or message.get("reasoning_content") or ""
            return _parse_ai_response(raw_text)
        except httpx.HTTPStatusError as e:
            return {"error": f"Error HTTP de {provider_name}: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": f"Error al llamar a {provider_name}: {str(e)}"}


STEP_TITLES = {
    1: "Cobertura y refactorización",
    2: "Detección de flakiness",
    3: "Adecuación y mutaciones",
    4: "Veredicto final",
}

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
        "max_score": 5,
        "summary": justification or text[:240],
        "steps": [
            {"number": num, "title": STEP_TITLES[num], "content": content}
            for num, content in contents.items()
            if content or (num == 4 and has_verdict)
        ],
        "recommendations": recommendations,
    }


def _parse_ai_response(raw: str) -> dict:
    """
    Parsea la respuesta de la IA (soporta evaluación por 4 pasos o JSON).
    """
    text = raw.strip()

    # Un informe puede citar diccionarios del código, así que los pasos van antes que el JSON.
    steps_parsed = _parse_steps_response(raw)
    if steps_parsed is not None and steps_parsed["steps"]:
        return steps_parsed

    # Remover bloques ```json ... ```
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

    if steps_parsed is not None:
        return steps_parsed

    return {
        "error": "No se pudo parsear la respuesta de la IA.",
        "raw": raw[:500],
    }
