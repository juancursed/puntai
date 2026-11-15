"""
runner.py — Ejecuta pytest en el proyecto y parsea los resultados.

Usa pytest con salida JSON para obtener resultados estructurados.
Requiere: pip install pytest pytest-json-report
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PYTEST_TIMEOUT_SECONDS = 120


def run_tests(project_path: str) -> dict:
    """
    Ejecuta pytest en el proyecto y devuelve el resumen y el resultado de cada prueba.

    Primero lo intenta en un subproceso (aísla las pruebas del servidor). Si el
    subproceso no puede ejecutar pytest —por ejemplo en Vercel, donde las
    dependencias no están en el Python del sistema— lo ejecuta en este proceso.
    """
    root = Path(project_path).expanduser().resolve()

    if not root.exists():
        return {"error": f"La ruta '{project_path}' no existe."}

    results = []   # Salidas de los subprocesos, para explicar un fallo
    reports = []   # Reportes JSON obtenidos sin pruebas
    for explicit_plugin in (False, True):
        try:
            result, report = _subprocess_attempt(root, explicit_plugin)
        except subprocess.TimeoutExpired:
            return {"error": f"pytest tardó más de {PYTEST_TIMEOUT_SECONDS} segundos. Verifica que las pruebas no cuelguen."}
        except OSError:  # No se pudo lanzar el intérprete
            break
        if _has_tests(report):
            mode = "subproceso (plugin explícito)" if explicit_plugin else "subproceso"
            return {**_parse_json_report(report), "runner": mode}
        results.append(result)
        if report is not None:
            reports.append(report)

    for result in results:
        # pytest corrió pero sin reporte JSON: se intenta leer su salida de texto.
        parsed = _parse_text_output(result.stdout or "")
        if parsed["tests"]:
            return {**parsed, "runner": "salida de texto"}

    # El entorno del subproceso puede ser el problema, así que se reintenta aquí.
    in_process = _run_in_process(root)
    if _has_tests(in_process):
        return {**_parse_json_report(in_process), "runner": "en proceso"}

    report = in_process or (reports[-1] if reports else None)
    return {"error": _failure_message(root, report, results)}


def _subprocess_attempt(root: Path, explicit_plugin: bool) -> tuple:
    """Ejecuta pytest en un subproceso y devuelve (salida, reporte JSON o None)."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        report_path = tmp.name
    try:
        result = _run_subprocess(root, report_path, explicit_plugin)
        return result, _read_report(report_path)
    finally:
        try:
            os.unlink(report_path)
        except OSError:
            pass


def _has_tests(report: dict | None) -> bool:
    return bool(report and report.get("tests"))


def _failure_message(root: Path, report: dict | None, results: list) -> str:
    """Explica por qué no hay resultados: errores de recolección o salida de pytest."""
    lines = []
    if report is None:
        lines.append("No se pudo ejecutar pytest en el proyecto.")
    else:
        exitcode = report.get("exitcode")
        if exitcode == 5:
            lines.append(f"pytest no encontró pruebas en '{root}'.")
        else:
            lines.append(f"pytest no reportó pruebas (código de salida {exitcode}).")
        for collector in report.get("collectors", []):
            if collector.get("outcome") == "failed":
                lines.append(f"Error al cargar {collector.get('nodeid') or '(raíz)'}:")
                lines.append(_tail(collector.get("longrepr", ""), 8))
    for result in results:
        lines.append(_tail(result.stderr or result.stdout, 8))
    return "\n".join(line for line in lines if line)


def _pytest_args(root: Path, report_file: str) -> list[str]:
    return [
        f"--json-report-file={report_file}",
        "--tb=short",
        "-q",
        # Sin .pytest_cache ni __pycache__: el proyecto puede estar en un
        # disco de solo lectura (Vercel) y no se ensucia el repo evaluado.
        "-p", "no:cacheprovider",
        # El rootdir es siempre el proyecto evaluado, nunca una carpeta superior.
        f"--rootdir={root}",
        str(root),
    ]


def _project_import_paths(root: Path) -> list[str]:
    """Rutas para importar el código del proyecto aunque no tenga configurado pythonpath."""
    paths = [root, root / "src"]
    return [str(path) for path in paths if path.is_dir()]


def _run_subprocess(root: Path, report_path: str, explicit_plugin: bool = False) -> subprocess.CompletedProcess:
    plugin_args = []
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        # El subproceso ve los mismos paquetes que el servidor (en Vercel no
        # están en el site-packages del intérprete, sino en la carpeta de la función).
        "PYTHONPATH": os.pathsep.join(_project_import_paths(root) + [p for p in sys.path if p]),
    }
    if explicit_plugin:
        # Si el plugin no se autodescubre (p. ej. faltan los metadatos del paquete en
        # el bundle de Vercel), se carga a mano; con autodescubrimiento activo se
        # registraría dos veces, por eso se desactiva solo en este intento.
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        plugin_args = ["-p", "pytest_jsonreport.plugin"]
    return subprocess.run(
        [sys.executable, "-m", "pytest", *plugin_args, "--json-report", *_pytest_args(root, report_path)],
        capture_output=True,
        text=True,
        cwd=str(root),
        env=env,
        timeout=PYTEST_TIMEOUT_SECONDS,
    )


def _read_report(report_path: str) -> dict | None:
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _run_in_process(root: Path) -> dict | None:
    """Ejecuta pytest dentro del servidor y devuelve el reporte JSON, o None si falla."""
    try:
        import pytest
        from pytest_jsonreport.plugin import JSONReport
    except ImportError:
        return None

    plugin = JSONReport()
    previous_cwd = os.getcwd()
    previous_bytecode = sys.dont_write_bytecode
    previous_path = list(sys.path)
    sys.dont_write_bytecode = True
    sys.path[:0] = _project_import_paths(root)
    try:
        os.chdir(root)
        # Con el plugin pasado como objeto no se usa --json-report (lo registraría dos veces).
        pytest.main(_pytest_args(root, "none"), plugins=[plugin])
    except Exception:
        return None
    finally:
        os.chdir(previous_cwd)
        sys.dont_write_bytecode = previous_bytecode
        sys.path[:] = previous_path
    return plugin.report or None


def _tail(text: str, lines: int = 15) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def _parse_json_report(report: dict) -> dict:
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
            # Un "error" ocurre al preparar la prueba (setup) o al limpiarla (teardown).
            longrepr = next(
                (t.get(phase, {}).get("longrepr") for phase in ("call", "setup", "teardown")
                 if t.get(phase, {}).get("longrepr")),
                "",
            )
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


def _parse_text_output(stdout: str) -> dict:
    """
    Fallback: parsea la salida de texto de pytest cuando no hay reporte JSON.
    Útil si pytest-json-report no está instalado.
    """
    outcomes = {
        " PASSED": ("passed", ""),
        " FAILED": ("failed", "Ver logs de pytest para detalles."),
    }
    tests = []
    summary = {"total": 0, "passed": 0, "failed": 0, "error": 0, "skipped": 0}

    for line in stdout.splitlines():
        line = line.strip()
        if "::" not in line:
            continue
        for marker, (outcome, message) in outcomes.items():
            if marker in line:
                name = line.split(" ")[0]
                parts = name.split("::")
                tests.append({
                    "name": name,
                    "file": parts[0],
                    "function": parts[-1],
                    "outcome": outcome,
                    "duration": 0,
                    "message": message,
                })
                summary[outcome] += 1
                break

    summary["total"] = len(tests)

    return {
        "summary": summary,
        "tests": tests,
        "duration": 0,
        "warning": "pytest-json-report no instalado. Instala con: pip install pytest-json-report",
    }


def environment_report(project_dir: Path) -> dict:
    """Datos para diagnosticar por qué pytest no corre en un servidor (p. ej. Vercel)."""
    files = sorted(
        p.relative_to(project_dir).as_posix()
        for p in project_dir.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    ) if project_dir.is_dir() else []

    versions = {}
    for module in ("pytest", "pytest_jsonreport"):
        try:
            versions[module] = getattr(__import__(module), "__version__", "instalado")
        except ImportError as e:
            versions[module] = f"no disponible: {e}"

    probe = None
    try:
        completed = subprocess.run(
            [sys.executable, "-c", "import pytest, pytest_jsonreport; print(pytest.__version__)"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "PYTHONPATH": os.pathsep.join(p for p in sys.path if p)},
        )
        probe = {"returncode": completed.returncode, "output": _tail(completed.stdout + completed.stderr, 5)}
    except (OSError, subprocess.SubprocessError) as e:
        probe = {"error": str(e)}

    return {
        "python": sys.version,
        "executable": sys.executable,
        "cwd": os.getcwd(),
        "project_dir": str(project_dir),
        "project_exists": project_dir.is_dir(),
        "project_files": files[:200],
        "modules": versions,
        "subprocess_probe": probe,
    }
