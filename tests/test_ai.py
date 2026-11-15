"""
Pruebas de uniteval.ai: parseo de respuestas y llamadas a los proveedores.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from uniteval.ai import client, parser

SAMPLE_CODE = "assert True"

def test_parse_ai_response_variants():
    raw_json = '{"quality": "alta", "quality_score": 9}'
    assert parser.parse_ai_response(raw_json)["quality"] == "alta"

    fenced = '```json\n{"quality": "media", "quality_score": 6}\n```'
    assert parser.parse_ai_response(fenced)["quality"] == "media"

    embedded = 'Aquí está el resultado: {"quality": "baja", "quality_score": 3} fin.'
    assert parser.parse_ai_response(embedded)["quality"] == "baja"

    steps_text = (
        "- **Paso 1 (Cobertura y Refactorización):** Cubre la rama principal.\n"
        "- **Paso 2 (Detección de Flakiness):** Es determinista.\n"
        "- **Paso 3 (Adecuación y Mutaciones):** Aserción adecuada.\n"
        "- **Paso 4 (Veredicto Final):** Calificación: **4/5**. Recomendación: Ampliar casos."
    )
    parsed_steps = parser.parse_ai_response(steps_text)
    assert parsed_steps["quality"] == "alta"
    assert parsed_steps["quality_score"] == 4
    assert parsed_steps["max_score"] == 5
    assert len(parsed_steps["steps"]) == 4

    steps_low = "- **Paso 4 (Veredicto Final):** Calificación: **2/5**."
    assert parser.parse_ai_response(steps_low)["quality"] == "baja"

    steps_mid = "- **Paso 4 (Veredicto Final):** Calificación: **3/5**."
    assert parser.parse_ai_response(steps_mid)["quality"] == "media"

    broken = "texto sin json {invalido}"
    assert "error" in parser.parse_ai_response(broken)


def test_analyze_test_unsupported_model():
    res = asyncio.run(client.analyze_test("test_a", SAMPLE_CODE, "passed", "unknown_model", "key"))
    assert "error" in res


def test_analyze_test_claude_success_and_errors():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"content": [{"text": '{"quality": "alta", "quality_score": 9}'}]}

    with patch("uniteval.ai.providers.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        res = asyncio.run(client.analyze_test("test_a", SAMPLE_CODE, "passed", "claude", "key"))
        assert res["quality"] == "alta"

        # Error HTTP
        err_response = MagicMock(status_code=401, text="Unauthorized")
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=err_response
        )
        res_http_err = asyncio.run(client.analyze_test("test_a", SAMPLE_CODE, "passed", "claude", "key"))
        assert "Error HTTP de Claude" in res_http_err["error"]

        # Excepción genérica
        mock_client.post.side_effect = RuntimeError("network down")
        res_gen_err = asyncio.run(client.analyze_test("test_a", SAMPLE_CODE, "passed", "claude", "key"))
        assert "Error al llamar a Claude" in res_gen_err["error"]


def test_analyze_test_openai_and_laguna():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"quality": "alta", "quality_score": 8}'}}]
    }

    with patch("uniteval.ai.providers.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        res_openai = asyncio.run(client.analyze_test("test_a", SAMPLE_CODE, "passed", "openai", "key"))
        assert res_openai["quality"] == "alta"

        res_laguna = asyncio.run(client.analyze_test("test_a", SAMPLE_CODE, "passed", "laguna", "key"))
        assert res_laguna["quality"] == "alta"

        res_nim = asyncio.run(client.analyze_test("test_a", SAMPLE_CODE, "passed", "laguna", "nvapi-key"))
        assert res_nim["quality"] == "alta"

        # Error HTTP en proveedor compatible con OpenAI
        err_response = MagicMock(status_code=500, text="Server Error")
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=err_response
        )
        res_http_err = asyncio.run(client.analyze_test("test_a", SAMPLE_CODE, "passed", "laguna", "sk-or-key"))
        assert "Error HTTP de OpenRouter" in res_http_err["error"]

        # Excepción genérica
        mock_client.post.side_effect = RuntimeError("timeout")
        res_gen_err = asyncio.run(client.analyze_test("test_a", SAMPLE_CODE, "passed", "openai", "key"))
        assert "Error al llamar a OpenAI" in res_gen_err["error"]


def test_analyze_test_sends_source_and_test_code():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"content": [{"text": "**Paso 4 (Veredicto Final):** Calificación: **4/5**."}]}

    with patch("uniteval.ai.providers.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        asyncio.run(client.analyze_test(
            "test_a", SAMPLE_CODE, "passed", "claude", "key", source_code="def suma(a, b): ...",
        ))

    message = mock_client.post.call_args.kwargs["json"]["messages"][0]["content"]
    assert "**Código fuente de la función evaluada:**" in message
    assert "def suma(a, b): ..." in message
    assert SAMPLE_CODE in message


def test_parse_report_structure():
    report = (
        "### Paso 1 (Cobertura y Refactorización)\nCubre 3/5 ramas de `suma`.\n\n"
        "**Paso 2 (Detección de Flakiness):** Determinista.\n"
        "**Paso 3 (Adecuación y Mutaciones):** Revisa {\"a\": 1}.\n"
        "**Paso 4 (Veredicto Final):** Calificación: **2/5**. Falta cobertura. "
        "**Recomendaciones:** Añadir casos límite."
    )
    parsed = parser.parse_ai_response(report)

    assert parsed["quality_score"] == 2
    assert parsed["quality"] == "baja"
    assert [s["number"] for s in parsed["steps"]] == [1, 2, 3, 4]
    assert parsed["steps"][0]["content"] == "Cubre 3/5 ramas de `suma`."
    assert parsed["steps"][3]["content"] == "Falta cobertura."
    assert parsed["recommendations"] == "Añadir casos límite."


def test_parse_report_cleans_verdict_labels_and_repeated_summary():
    report = (
        "**Paso 4 (Veredicto Final):**\n"
        "**Calificación: 3/5**\n"
        "**Justificación:** Es clara pero parcial.\n\n"
        "**Recomendaciones:**\n1. Agregar casos.\n\n---\n\n**Resumen:** Calidad 3/5"
    )
    parsed = parser.parse_ai_response(report)

    assert parsed["quality_score"] == 3
    assert parsed["steps"][0]["content"] == "Es clara pero parcial."
    assert parsed["recommendations"] == "1. Agregar casos."


def test_parse_report_accepts_markdown_headings_in_verdict():
    report = (
        "### Paso 4 (Veredicto Final)\n"
        "#### Calificación: **2/5**\n"
        "#### Justificación:\nMuy limitada.\n\n"
        "#### Recomendaciones:\n- Agregar casos."
    )
    parsed = parser.parse_ai_response(report)

    assert parsed["quality_score"] == 2
    assert parsed["steps"][0]["content"] == "Muy limitada."
    assert parsed["recommendations"] == "- Agregar casos."


def test_parse_report_keeps_recommendations_without_justification():
    parsed = parser.parse_ai_response(
        "**Paso 4 (Veredicto Final):** Calificación: **4/5**. Recomendación: Ampliar casos."
    )
    assert [s["number"] for s in parsed["steps"]] == [4]
    assert parsed["recommendations"] == "Ampliar casos."


def test_parse_report_without_score_does_not_invent_one():
    parsed = parser.parse_ai_response("**Paso 1 (Cobertura y Refactorización):** Respuesta cortada")
    assert parsed["quality_score"] is None
    assert parsed["quality"] == ""
