"""
providers.py — Llamadas HTTP a cada proveedor de IA.

Cada función devuelve el análisis ya parseado de la respuesta,
o {"error": str} si la llamada falla.
"""

from typing import Callable

import httpx

from uniteval.ai.parser import parse_ai_response
from uniteval.ai.prompts import SYSTEM_PROMPT

CLAUDE_MODEL = "claude-sonnet-4-20250514"
OPENAI_MODEL = "gpt-4o"
DEFAULT_LAGUNA_MODEL = "poolside/laguna-s-2.1"
NIM_LAGUNA_MODEL = "poolside/laguna-xs-2.1"

MAX_TOKENS = 2048
TIMEOUT_SECONDS = 60


async def call_claude(user_message: str, api_key: str) -> dict:
    """Llama a la API de Anthropic Claude."""
    return await _post(
        provider_name="Claude",
        url="https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        payload={
            "model": CLAUDE_MODEL,
            "max_tokens": MAX_TOKENS,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}],
        },
        extract_text=lambda data: data["content"][0]["text"],
    )


async def call_openai(user_message: str, api_key: str) -> dict:
    """Llama a la API de OpenAI."""
    return await _call_openai_compatible(
        url="https://api.openai.com/v1/chat/completions",
        model_id=OPENAI_MODEL,
        provider_name="OpenAI",
        user_message=user_message,
        api_key=api_key,
    )


async def call_laguna(
    user_message: str,
    api_key: str,
    model_id: str = DEFAULT_LAGUNA_MODEL,
) -> dict:
    """Llama a Laguna vía Poolside Platform, NVIDIA NIM u OpenRouter según la clave."""
    if api_key.startswith("sk-or-"):
        url = "https://openrouter.ai/api/v1/chat/completions"
        provider_name = "OpenRouter"
    elif api_key.startswith("nvapi-"):
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        provider_name = "NVIDIA NIM"
        # NVIDIA NIM solo aloja la variante XS de Laguna 2.1
        if model_id == DEFAULT_LAGUNA_MODEL:
            model_id = NIM_LAGUNA_MODEL
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

    def extract_text(data: dict) -> str:
        message = data["choices"][0]["message"]
        return message.get("content") or message.get("reasoning_content") or ""

    return await _post(
        provider_name=provider_name,
        url=url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        payload={
            "model": model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": MAX_TOKENS,
            "temperature": 0.3,
        },
        extract_text=extract_text,
    )


async def _post(
    provider_name: str,
    url: str,
    headers: dict,
    payload: dict,
    extract_text: Callable[[dict], str],
) -> dict:
    """Envía la petición, extrae el texto de la respuesta y lo parsea."""
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return parse_ai_response(extract_text(response.json()))
        except httpx.HTTPStatusError as e:
            return {"error": f"Error HTTP de {provider_name}: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": f"Error al llamar a {provider_name}: {str(e)}"}
