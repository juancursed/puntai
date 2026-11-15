"""
client.py — Punto de entrada para evaluar una prueba unitaria con IA.

Modelos soportados:
  - claude: Claude (Anthropic), API directa
  - openai: GPT-4o (OpenAI)
  - laguna: Laguna (Poolside, NVIDIA NIM u OpenRouter)
"""

from uniteval.ai import providers
from uniteval.ai.prompts import build_user_message

SUPPORTED_MODELS = ("claude", "openai", "laguna")


async def analyze_test(
    test_name: str,
    test_code: str,
    test_result: str,
    model: str,
    api_key: str,
    openrouter_model: str = providers.DEFAULT_LAGUNA_MODEL,
    source_code: str = "",
) -> dict:
    """
    Analiza una prueba unitaria y el código fuente que evalúa con la IA seleccionada.

    Returns:
        Dict con el análisis estructurado o {"error": str} si falla.
    """
    user_message = build_user_message(test_name, test_code, test_result, source_code)
    if model == "claude":
        return await providers.call_claude(user_message, api_key)
    if model == "openai":
        return await providers.call_openai(user_message, api_key)
    if model == "laguna":
        return await providers.call_laguna(user_message, api_key, openrouter_model)
    return {"error": f"Modelo '{model}' no soportado."}
