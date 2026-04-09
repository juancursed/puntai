"""
runner.py — Ejecuta pytest en el proyecto y parsea los resultados.

Usa pytest con salida JSON para obtener resultados estructurados.
Requiere: pip install pytest pytest-json-report
"""

import subprocess
import json
import tempfile
import os
from pathlib import Path


def run_tests(project_path: str) -> dict:
    """
    Ejecuta pytest en el proyecto y devuelve resultados estructurados.

    Args:
        project_path: Ruta al directorio del proyecto.

    Returns:
        {
            "summary": {"total": int, "passed": int, "failed": int, "error": int, "skipped": int},
            "tests": [
                {
                    "name": str,       # nombre completo: archivo::función
                    "file": str,       # archivo relativo
                    "function": str,   # nombre de la función
                    "outcome": str,    # passed | failed | error | skipped
                    "duration": float, # segundos
                    "message": str,    # mensaje de error si falla
                }
            ],
            "duration": float,
        }
    """
    root = Path(project_path).expanduser().resolve()

    if not root.exists():
        return {"error": f"La ruta '{project_path}' no existe."}

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        report_path = tmp.name

    try:
        result = subprocess.run(
            [
                "python", "-m", "pytest",
                "--json-report",
                f"--json-report-file={report_path}",
                "--tb=short",
                "-q",
                str(root),
            ],
            capture_output=True,
            text=True,
            cwd=str(root),
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return {"error": "pytest tardó más de 120 segundos. Verifica que las pruebas no cuelguen."}
    except FileNotFoundError:
        return {"error": "No se encontró 'python' o 'pytest'. Asegúrate de tener el entorno activado."}
    finally:
        pass

    # Leer reporte JSON
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Fallback: parsear salida de texto si no hay reporte JSON
        return _parse_text_output(result.stdout, result.stderr)
    finally:
        try:
            os.unlink(report_path)
        except OSError:
            pass

    return _parse_json_report(report, root)


def _parse_json_report(report: dict, root: Path) -> dict:
    """Convierte el reporte JSON de pytest-json-report a nuestro formato."""
    summary_raw = report.get("summary", {})

    summary = {
        "total": summary_raw.get("total", 0),
        "passed": summary_raw.get("passed", 0),
        "failed": summary_raw.get("failed", 0),
        "error": summary_raw.get("error", 0),
        "skipped": summary_raw.get("skipped", 0),
    }

    tests = []
    for t in report.get("tests", []):
        node_id = t.get("nodeid", "")
        # nodeid ejemplo: "tests/test_calc.py::test_suma"
        parts = node_id.split("::")
        file_part = parts[0] if parts else ""
        func_part = parts[-1] if len(parts) > 1 else node_id

        # Mensaje de error
        message = ""
        if t.get("outcome") in ("failed", "error"):
            call = t.get("call", {})
            longrepr = call.get("longrepr", "")
            # Tomar las últimas líneas relevantes
            if longrepr:
                lines = longrepr.strip().splitlines()
                message = "\n".join(lines[-10:])  # últimas 10 líneas

        tests.append({
            "name": node_id,
            "file": file_part,
            "function": func_part,
            "outcome": t.get("outcome", "unknown"),
            "duration": round(t.get("call", {}).get("duration", 0), 4),
            "message": message,
        })

    return {
        "summary": summary,
        "tests": tests,
        "duration": round(report.get("duration", 0), 3),
    }


def _parse_text_output(stdout: str, stderr: str) -> dict:
    """
    Fallback: parsea la salida de texto de pytest cuando no hay reporte JSON.
    Útil si pytest-json-report no está instalado.
    """
    tests = []
    summary = {"total": 0, "passed": 0, "failed": 0, "error": 0, "skipped": 0}

    for line in stdout.splitlines():
        line = line.strip()
        if "::" in line:
            if " PASSED" in line:
                name = line.split(" ")[0]
                parts = name.split("::")
                tests.append({
                    "name": name,
                    "file": parts[0],
                    "function": parts[-1],
                    "outcome": "passed",
                    "duration": 0,
                    "message": "",
                })
                summary["passed"] += 1
            elif " FAILED" in line:
                name = line.split(" ")[0]
                parts = name.split("::")
                tests.append({
                    "name": name,
                    "file": parts[0],
                    "function": parts[-1],
                    "outcome": "failed",
                    "duration": 0,
                    "message": "Ver logs de pytest para detalles.",
                })
                summary["failed"] += 1

    summary["total"] = len(tests)

    return {
        "summary": summary,
        "tests": tests,
        "duration": 0,
        "warning": "pytest-json-report no instalado. Instala con: pip install pytest-json-report",
    }
