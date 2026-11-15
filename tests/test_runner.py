"""
Pruebas de uniteval.core.runner.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from uniteval.core import runner

def test_run_tests_nonexistent(tmp_path: Path):
    result = runner.run_tests(str(tmp_path / "missing"))
    assert "error" in result


def test_run_tests_timeout(tmp_path: Path):
    with patch("uniteval.core.runner.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pytest", timeout=120)):
        result = runner.run_tests(str(tmp_path))
    assert "error" in result
    assert "120 segundos" in result["error"]


def test_run_tests_file_not_found(tmp_path: Path):
    with patch("uniteval.core.runner.subprocess.run", side_effect=FileNotFoundError()),             patch("uniteval.core.runner._run_in_process", return_value=None):
        result = runner.run_tests(str(tmp_path))
    assert "error" in result


def test_run_tests_falls_back_to_in_process_when_subprocess_finds_no_pytest(tmp_path: Path):
    # Caso Vercel: el intérprete del subproceso no tiene pytest instalado.
    failed_proc = MagicMock(stdout="", stderr="No module named pytest")
    in_process_report = {
        "summary": {"total": 1, "passed": 1},
        "tests": [{"nodeid": "tests/test_a.py::test_ok", "outcome": "passed", "call": {"duration": 0.1}}],
    }
    with patch("uniteval.core.runner.subprocess.run", return_value=failed_proc),             patch("uniteval.core.runner._run_in_process", return_value=in_process_report) as in_process:
        result = runner.run_tests(str(tmp_path))

    in_process.assert_called_once()
    assert result["summary"]["passed"] == 1
    assert result["tests"][0]["function"] == "test_ok"


def test_run_tests_reports_error_instead_of_zero_tests(tmp_path: Path):
    failed_proc = MagicMock(stdout="", stderr="No module named pytest")
    with patch("uniteval.core.runner.subprocess.run", return_value=failed_proc),             patch("uniteval.core.runner._run_in_process", return_value=None):
        result = runner.run_tests(str(tmp_path))

    assert "No se pudo ejecutar pytest" in result["error"]
    assert "No module named pytest" in result["error"]


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

    with patch("uniteval.core.runner.subprocess.run", side_effect=fake_run):
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
    with patch("uniteval.core.runner.subprocess.run", return_value=fake_proc):
        with patch("builtins.open", side_effect=FileNotFoundError()):
            result = runner.run_tests(str(tmp_path))

    assert result["summary"]["total"] == 2
    assert result["summary"]["passed"] == 1
    assert result["summary"]["failed"] == 1
    assert "warning" in result


def test_run_tests_explains_collection_errors_when_no_tests_run(tmp_path: Path):
    empty_report = {
        "exitcode": 2,
        "summary": {"total": 0},
        "tests": [],
        "collectors": [{
            "nodeid": "tests/test_a.py", "outcome": "failed",
            "longrepr": "ModuleNotFoundError: No module named 'carrito'",
        }],
    }

    def fake_run(cmd, **_kwargs):
        report_file = next(a.split("=", 1)[1] for a in cmd if a.startswith("--json-report-file="))
        Path(report_file).write_text(json.dumps(empty_report), encoding="utf-8")
        return MagicMock(stdout="", stderr="")

    with patch("uniteval.core.runner.subprocess.run", side_effect=fake_run), \
            patch("uniteval.core.runner._run_in_process", return_value=None) as in_process:
        result = runner.run_tests(str(tmp_path))

    in_process.assert_called_once()
    assert "código de salida 2" in result["error"]
    assert "No module named 'carrito'" in result["error"]


def test_parse_json_report_reads_setup_errors():
    report = {
        "summary": {"total": 1, "error": 1},
        "tests": [{
            "nodeid": "tests/test_a.py::test_x", "outcome": "error",
            "setup": {"longrepr": "fixture 'db' not found"}, "call": {},
        }],
    }
    parsed = runner._parse_json_report(report)
    assert parsed["summary"]["error"] == 1
    assert parsed["tests"][0]["message"] == "fixture 'db' not found"
