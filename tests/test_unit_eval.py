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
import runner
import scanner

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

        # Error HTTP en proveedor compatible con OpenAI
        err_response = MagicMock(status_code=500, text="Server Error")
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=err_response
        )
        res_http_err = asyncio.run(ai_client.analyze_test("test_a", SAMPLE_CODE, "passed", "laguna", "key"))
        assert "Error HTTP de OpenRouter" in res_http_err["error"]

        # Excepción genérica
        mock_client.post.side_effect = RuntimeError("timeout")
        res_gen_err = asyncio.run(ai_client.analyze_test("test_a", SAMPLE_CODE, "passed", "openai", "key"))
        assert "Error al llamar a OpenAI" in res_gen_err["error"]


# ── Pruebas de main.py ───────────────────────────────────────────────────────

def test_main_endpoints(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(main, "CONFIG_FILE", cfg_file)
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
    assert client.get("/api/config").json()["model"] == "laguna"

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
