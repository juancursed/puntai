"""
Pruebas unitarias para UnitEval (scanner, runner, ai_client y main).
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from fastapi.testclient import TestClient

import ai_client
import main
import reports
import runner
import scanner
import source_resolver

SAMPLE_CODE = "assert True"
SAMPLE_TEST_FILE = "test_a.py"


# ── Pruebas de scanner.py ────────────────────────────────────────────────────

def test_scan_project_nonexistent(tmp_path: Path):
    missing = tmp_path / "does_not_exist"
    result = scanner.scan_project(str(missing))
    assert "error" in result


def test_scan_project_not_a_dir(tmp_path: Path):
    file_path = tmp_path / "some_file.txt"
    file_path.write_text("hello", encoding="utf-8")
    result = scanner.scan_project(str(file_path))
    assert "error" in result


def test_scan_project_success_and_syntax_error(tmp_path: Path):
    valid_test = tmp_path / "test_sample.py"
    valid_test.write_text(
        'def test_ok():\n    """Docstring."""\n    assert 1 == 1\n\n'
        'async def test_async_ok():\n    assert True\n\n'
        'def helper():\n    pass\n',
        encoding="utf-8",
    )
    bad_test = tmp_path / "bad_test.py"
    bad_test.write_text("def test_broken(:\n", encoding="utf-8")

    ignored_dir = tmp_path / "venv"
    ignored_dir.mkdir()
    (ignored_dir / "test_ignored.py").write_text("def test_ign(): assert True\n", encoding="utf-8")

    result = scanner.scan_project(str(tmp_path))
    assert result["total_tests"] == 2
    assert len(result["test_files"]) == 1
    names = {t["name"] for t in result["test_files"][0]["tests"]}
    assert names == {"test_ok", "test_async_ok"}


def test_extract_tests_os_error(tmp_path: Path):
    missing_file = tmp_path / "test_missing.py"
    assert scanner._extract_tests(missing_file) is None


# ── Pruebas de runner.py ─────────────────────────────────────────────────────

def test_run_tests_nonexistent(tmp_path: Path):
    result = runner.run_tests(str(tmp_path / "missing"))
    assert "error" in result


def test_run_tests_timeout(tmp_path: Path):
    with patch("runner.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pytest", timeout=120)):
        result = runner.run_tests(str(tmp_path))
    assert "error" in result
    assert "120 segundos" in result["error"]


def test_run_tests_file_not_found(tmp_path: Path):
    with patch("runner.subprocess.run", side_effect=FileNotFoundError()):
        result = runner.run_tests(str(tmp_path))
    assert "error" in result


def test_run_tests_json_report(tmp_path: Path):
    fake_report = {
        "summary": {"total": 2, "passed": 1, "failed": 1, "error": 0, "skipped": 0},
        "duration": 0.456,
        "tests": [
            {
                "nodeid": "tests/test_a.py::test_pass",
                "outcome": "passed",
                "call": {"duration": 0.012},
            },
            {
                "nodeid": "tests/test_a.py::test_fail",
                "outcome": "failed",
                "call": {"duration": 0.023, "longrepr": "AssertionError: boom"},
            },
        ],
    }

    def fake_run(cmd, **_kwargs):
        for arg in cmd:
            if arg.startswith("--json-report-file="):
                report_file = arg.split("=", 1)[1]
                Path(report_file).write_text(json.dumps(fake_report), encoding="utf-8")
        return MagicMock(stdout="", stderr="")

    with patch("runner.subprocess.run", side_effect=fake_run):
        result = runner.run_tests(str(tmp_path))

    assert result["summary"]["passed"] == 1
    assert result["summary"]["failed"] == 1
    assert len(result["tests"]) == 2
    assert result["tests"][1]["message"] == "AssertionError: boom"


def test_run_tests_text_fallback(tmp_path: Path):
    fake_proc = MagicMock(
        stdout="tests/test_x.py::test_one PASSED\ntests/test_x.py::test_two FAILED\n",
        stderr="",
    )
    with patch("runner.subprocess.run", return_value=fake_proc):
        with patch("builtins.open", side_effect=FileNotFoundError()):
            result = runner.run_tests(str(tmp_path))

    assert result["summary"]["total"] == 2
    assert result["summary"]["passed"] == 1
    assert result["summary"]["failed"] == 1
    assert "warning" in result


# ── Pruebas de ai_client.py ──────────────────────────────────────────────────

def test_parse_ai_response_variants():
    raw_json = '{"quality": "alta", "quality_score": 9}'
    assert ai_client._parse_ai_response(raw_json)["quality"] == "alta"

    fenced = '```json\n{"quality": "media", "quality_score": 6}\n```'
    assert ai_client._parse_ai_response(fenced)["quality"] == "media"

    embedded = 'Aquí está el resultado: {"quality": "baja", "quality_score": 3} fin.'
    assert ai_client._parse_ai_response(embedded)["quality"] == "baja"

    steps_text = (
        "- **Paso 1 (Cobertura y Refactorización):** Cubre la rama principal.\n"
        "- **Paso 2 (Detección de Flakiness):** Es determinista.\n"
        "- **Paso 3 (Adecuación y Mutaciones):** Aserción adecuada.\n"
        "- **Paso 4 (Veredicto Final):** Calificación: **4/5**. Recomendación: Ampliar casos."
    )
    parsed_steps = ai_client._parse_ai_response(steps_text)
    assert parsed_steps["quality"] == "alta"
    assert parsed_steps["quality_score"] == 4
    assert parsed_steps["max_score"] == 5
    assert len(parsed_steps["steps"]) == 4

    steps_low = "- **Paso 4 (Veredicto Final):** Calificación: **2/5**."
    assert ai_client._parse_ai_response(steps_low)["quality"] == "baja"

    steps_mid = "- **Paso 4 (Veredicto Final):** Calificación: **3/5**."
    assert ai_client._parse_ai_response(steps_mid)["quality"] == "media"

    broken = "texto sin json {invalido}"
    assert "error" in ai_client._parse_ai_response(broken)


def test_analyze_test_unsupported_model():
    res = asyncio.run(ai_client.analyze_test("test_a", SAMPLE_CODE, "passed", "unknown_model", "key"))
    assert "error" in res


def test_analyze_test_claude_success_and_errors():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"content": [{"text": '{"quality": "alta", "quality_score": 9}'}]}

    with patch("ai_client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        res = asyncio.run(ai_client.analyze_test("test_a", SAMPLE_CODE, "passed", "claude", "key"))
        assert res["quality"] == "alta"

        # Error HTTP
        err_response = MagicMock(status_code=401, text="Unauthorized")
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=err_response
        )
        res_http_err = asyncio.run(ai_client.analyze_test("test_a", SAMPLE_CODE, "passed", "claude", "key"))
        assert "Error HTTP de Claude" in res_http_err["error"]

        # Excepción genérica
        mock_client.post.side_effect = RuntimeError("network down")
        res_gen_err = asyncio.run(ai_client.analyze_test("test_a", SAMPLE_CODE, "passed", "claude", "key"))
        assert "Error al llamar a Claude" in res_gen_err["error"]


def test_analyze_test_openai_and_laguna():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"quality": "alta", "quality_score": 8}'}}]
    }

    with patch("ai_client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        res_openai = asyncio.run(ai_client.analyze_test("test_a", SAMPLE_CODE, "passed", "openai", "key"))
        assert res_openai["quality"] == "alta"

        res_laguna = asyncio.run(ai_client.analyze_test("test_a", SAMPLE_CODE, "passed", "laguna", "key"))
        assert res_laguna["quality"] == "alta"

        res_nim = asyncio.run(ai_client.analyze_test("test_a", SAMPLE_CODE, "passed", "laguna", "nvapi-key"))
        assert res_nim["quality"] == "alta"

        # Error HTTP en proveedor compatible con OpenAI
        err_response = MagicMock(status_code=500, text="Server Error")
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=err_response
        )
        res_http_err = asyncio.run(ai_client.analyze_test("test_a", SAMPLE_CODE, "passed", "laguna", "sk-or-key"))
        assert "Error HTTP de OpenRouter" in res_http_err["error"]

        # Excepción genérica
        mock_client.post.side_effect = RuntimeError("timeout")
        res_gen_err = asyncio.run(ai_client.analyze_test("test_a", SAMPLE_CODE, "passed", "openai", "key"))
        assert "Error al llamar a OpenAI" in res_gen_err["error"]


def test_analyze_test_sends_source_and_test_code():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"content": [{"text": "**Paso 4 (Veredicto Final):** Calificación: **4/5**."}]}

    with patch("ai_client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        asyncio.run(ai_client.analyze_test(
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
    parsed = ai_client._parse_ai_response(report)

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
    parsed = ai_client._parse_ai_response(report)

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
    parsed = ai_client._parse_ai_response(report)

    assert parsed["quality_score"] == 2
    assert parsed["steps"][0]["content"] == "Muy limitada."
    assert parsed["recommendations"] == "- Agregar casos."


def test_parse_report_keeps_recommendations_without_justification():
    parsed = ai_client._parse_ai_response(
        "**Paso 4 (Veredicto Final):** Calificación: **4/5**. Recomendación: Ampliar casos."
    )
    assert [s["number"] for s in parsed["steps"]] == [4]
    assert parsed["recommendations"] == "Ampliar casos."


def test_parse_report_without_score_does_not_invent_one():
    parsed = ai_client._parse_ai_response("**Paso 1 (Cobertura y Refactorización):** Respuesta cortada")
    assert parsed["quality_score"] is None
    assert parsed["quality"] == ""


# ── Pruebas de source_resolver.py ────────────────────────────────────────────

def _write_project(root: Path) -> None:
    package = root / "src" / "tienda"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "from .carro import Carro\nfrom .precios import con_cupon\n", encoding="utf-8"
    )
    (package / "carro.py").write_text(
        "class Carro:\n"
        "    def __init__(self):\n"
        "        self.items = []\n\n"
        "    def agregar(self, item):\n"
        "        self._validar(item)\n"
        "        self.items.append(item)\n\n"
        "    def _validar(self, item):\n"
        "        assert item\n\n"
        "    def no_usado(self):\n"
        "        return 'secreto'\n",
        encoding="utf-8",
    )
    (package / "precios.py").write_text(
        "CUPONES = {'A': 10}\n\n"
        "def base(monto):\n"
        "    return monto\n\n"
        "def con_cupon(monto, codigo):\n"
        "    return base(monto) - CUPONES[codigo]\n\n"
        "def otra():\n"
        "    return 'ajena'\n",
        encoding="utf-8",
    )
    tests = root / "tests"
    tests.mkdir()
    (tests / "conftest.py").write_text(
        "import pytest\nfrom tienda import Carro\n\n"
        "@pytest.fixture\ndef base_carro():\n    return Carro()\n\n"
        "@pytest.fixture\ndef carro(base_carro):\n    return base_carro\n",
        encoding="utf-8",
    )
    (tests / "test_tienda.py").write_text(
        "from tienda import con_cupon\n\n"
        "def test_cupon():\n    assert con_cupon(20, 'A') == 10\n\n"
        "def test_agregar(carro):\n    carro.agregar('x')\n\n"
        "def test_sin_fuente():\n    assert 1 + 1 == 2\n\n"
        "class TestClase:\n"
        "    def setup_method(self):\n"
        "        from tienda import Carro\n"
        "        self.carro = Carro()\n\n"
        "    def test_en_clase(self):\n"
        "        self.carro.agregar('x')\n",
        encoding="utf-8",
    )


def test_find_source_follows_reexports_and_dependencies(tmp_path: Path):
    _write_project(tmp_path)
    found = source_resolver.find_source_code(str(tmp_path), "tests/test_tienda.py", "test_cupon")

    assert "def con_cupon" in found["code"]
    assert "def base" in found["code"]
    assert "CUPONES = {'A': 10}" in found["code"]
    assert "def otra" not in found["code"]
    assert found["files"] == ["src/tienda/precios.py"]


def test_find_source_follows_fixtures_and_keeps_only_used_methods(tmp_path: Path):
    _write_project(tmp_path)
    found = source_resolver.find_source_code(str(tmp_path), "tests/test_tienda.py", "test_agregar")

    assert "class Carro" in found["code"]
    assert "def __init__" in found["code"]
    assert "def agregar" in found["code"]
    assert "def _validar" in found["code"]
    assert "def no_usado" not in found["code"]


def test_find_source_uses_setup_of_test_class(tmp_path: Path):
    _write_project(tmp_path)
    found = source_resolver.find_source_code(str(tmp_path), "tests/test_tienda.py", "test_en_clase")
    assert "def agregar" in found["code"]


def test_find_source_without_matches(tmp_path: Path):
    _write_project(tmp_path)
    empty = {"code": "", "files": [], "truncated": False}
    resolve = source_resolver.find_source_code

    assert resolve(str(tmp_path), "tests/test_tienda.py", "test_sin_fuente") == empty
    assert resolve(str(tmp_path), "tests/test_tienda.py", "test_inexistente") == empty
    assert resolve(str(tmp_path), "tests/no_existe.py", "test_cupon") == empty


def test_find_source_rejects_paths_outside_project(tmp_path: Path):
    _write_project(tmp_path)
    found = source_resolver.find_source_code(str(tmp_path / "src"), "../tests/test_tienda.py", "test_cupon")
    assert found["code"] == ""


def test_find_source_respects_size_limit(tmp_path: Path, monkeypatch):
    _write_project(tmp_path)
    monkeypatch.setattr(source_resolver, "MAX_SOURCE_CHARS", 70)
    found = source_resolver.find_source_code(str(tmp_path), "tests/test_tienda.py", "test_cupon")

    assert found["truncated"] is True
    assert "def con_cupon" in found["code"]


# ── Pruebas de main.py ───────────────────────────────────────────────────────

def test_main_endpoints(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(main, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(main, "ENV_FILE", tmp_path / ".env")
    for env_var in main.KEY_ENV_VARS.values():
        monkeypatch.delenv(env_var, raising=False)
    client = TestClient(main.app)

    # Index
    resp_index = client.get("/")
    assert resp_index.status_code == 200

    # Get default config (when file does not exist)
    resp_cfg = client.get("/api/config")
    assert resp_cfg.status_code == 200
    assert resp_cfg.json()["model"] == "claude"

    # Update config
    resp_upd = client.post(
        "/api/config",
        json={
            "project_path": str(tmp_path),
            "model": "laguna",
            "anthropic_api_key": "",
            "openai_api_key": "",
            "openrouter_api_key": "or-key",
        },
    )
    assert resp_upd.status_code == 200
    saved_cfg = client.get("/api/config").json()
    assert saved_cfg["model"] == "laguna"

    # La clave va a .env: ni a config.json ni a la respuesta de la API
    assert saved_cfg["configured_keys"]["openrouter_api_key"] is True
    assert "or-key" not in str(saved_cfg)
    assert "or-key" not in cfg_file.read_text(encoding="utf-8")
    assert 'LAGUNA_API_KEY' in (tmp_path / ".env").read_text(encoding="utf-8")
    assert main.os.environ["LAGUNA_API_KEY"] == "or-key"

    # Guardar con el campo vacío conserva la clave
    client.post("/api/config", json={"project_path": str(tmp_path), "model": "laguna"})
    assert main.os.environ["LAGUNA_API_KEY"] == "or-key"

    # Scan valid & invalid
    resp_scan_ok = client.post("/api/scan", json={"path": str(tmp_path)})
    assert resp_scan_ok.status_code == 200
    resp_scan_err = client.post("/api/scan", json={"path": str(tmp_path / "nope")})
    assert resp_scan_err.status_code == 400

    # Run valid & invalid
    with patch("main.run_tests", return_value={"summary": {}, "tests": [], "duration": 0}):
        assert client.post("/api/run", json={"path": str(tmp_path)}).status_code == 200
    with patch("main.run_tests", return_value={"error": "fallo"}):
        assert client.post("/api/run", json={"path": str(tmp_path)}).status_code == 400

    # Analyze without key -> 400
    resp_no_key = client.post(
        "/api/analyze",
        json={
            "project_path": str(tmp_path),
            "test_file": SAMPLE_TEST_FILE,
            "test_name": "test_1",
            "test_code": SAMPLE_CODE,
            "test_result": "passed",
            "model": "claude",
        },
    )
    assert resp_no_key.status_code == 400

    # Analyze with key -> 200
    with patch("main.analyze_test", new=AsyncMock(return_value={"quality": "alta"})):
        resp_an = client.post(
            "/api/analyze",
            json={
                "project_path": str(tmp_path),
                "test_file": SAMPLE_TEST_FILE,
                "test_name": "test_1",
                "test_code": SAMPLE_CODE,
                "test_result": "passed",
                "model": "laguna",
            },
        )
        assert resp_an.status_code == 200
        assert resp_an.json()["quality"] == "alta"
        assert resp_an.json()["source_code"] == ""

    # Analyze error from AI provider -> 400
    with patch("main.analyze_test", new=AsyncMock(return_value={"error": "Fallo proveedor"})):
        resp_an_err = client.post(
            "/api/analyze",
            json={
                "project_path": str(tmp_path),
                "test_file": SAMPLE_TEST_FILE,
                "test_name": "test_1",
                "test_code": SAMPLE_CODE,
                "test_result": "passed",
                "model": "laguna",
            },
        )
        assert resp_an_err.status_code == 400


# ── Pruebas de reports.py ────────────────────────────────────────────────────

def test_reports_save_update_and_list(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(reports, "REPORTS_DIR", tmp_path / "reports")
    assert reports.list_reports() == []

    first = reports.save_report({"project_path": "a", "summary": {"average": 4}, "analyses": {"t": 1}})
    assert reports.is_valid_id(first["id"])
    assert reports.get_report(first["id"])["analyses"] == {"t": 1}

    updated = reports.save_report({"project_path": "a", "analyses": {"t": 2}}, first["id"])
    assert updated["created_at"] == first["created_at"]
    assert len(reports.list_reports()) == 1

    listed = reports.list_reports()[0]
    assert listed["id"] == first["id"]
    assert "analyses" not in listed


def test_reports_list_orders_recent_first_and_skips_corrupt_files(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(reports, "REPORTS_DIR", tmp_path)
    (tmp_path / "20250101-000000-aaaaaa.json").write_text('{"id": "viejo", "created_at": "2025-01-01"}', encoding="utf-8")
    (tmp_path / "20260101-000000-bbbbbb.json").write_text('{"id": "nuevo", "created_at": "2026-01-01"}', encoding="utf-8")
    (tmp_path / "20260101-000000-cccccc.json").write_text("{roto", encoding="utf-8")

    assert [r["id"] for r in reports.list_reports()] == ["nuevo", "viejo"]


def test_reports_endpoints(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(reports, "REPORTS_DIR", tmp_path / "reports")
    client = TestClient(main.app)

    assert client.get("/api/reports").json() == []
    saved = client.post("/api/reports", json={
        "project_path": "p", "model": "laguna", "summary": {"analyzed": 1}, "analyses": {"t": {"quality": "alta"}},
    }).json()

    assert client.get(f"/api/reports/{saved['id']}").json()["analyses"]["t"]["quality"] == "alta"
    assert len(client.get("/api/reports").json()) == 1
    assert client.get("/api/reports/20260101-000000-abcdef").status_code == 404
    assert client.get("/api/reports/no-valido").status_code == 404
    assert client.post("/api/reports", json={"id": "../config"}).status_code == 400
    assert not (tmp_path / "config.json").exists()
