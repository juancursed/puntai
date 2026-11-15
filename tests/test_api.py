"""
Pruebas de los endpoints de configuración, pruebas y análisis.
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from uniteval import config
from uniteval.app import app

SAMPLE_CODE = "assert True"
SAMPLE_TEST_FILE = "test_a.py"

def test_api_endpoints(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    for env_var in config.KEY_ENV_VARS.values():
        monkeypatch.delenv(env_var, raising=False)
    client = TestClient(app)

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
    assert os.environ["LAGUNA_API_KEY"] == "or-key"

    # Guardar con el campo vacío conserva la clave
    client.post("/api/config", json={"project_path": str(tmp_path), "model": "laguna"})
    assert os.environ["LAGUNA_API_KEY"] == "or-key"

    # Scan valid & invalid
    resp_scan_ok = client.post("/api/scan", json={"path": str(tmp_path)})
    assert resp_scan_ok.status_code == 200
    resp_scan_err = client.post("/api/scan", json={"path": str(tmp_path / "nope")})
    assert resp_scan_err.status_code == 400

    # Run valid & invalid
    with patch("uniteval.routes.run_tests", return_value={"summary": {}, "tests": [], "duration": 0}):
        assert client.post("/api/run", json={"path": str(tmp_path)}).status_code == 200
    with patch("uniteval.routes.run_tests", return_value={"error": "fallo"}):
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
    with patch("uniteval.routes.analyze_test", new=AsyncMock(return_value={"quality": "alta"})):
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
    with patch("uniteval.routes.analyze_test", new=AsyncMock(return_value={"error": "Fallo proveedor"})):
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
