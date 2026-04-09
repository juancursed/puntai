"""
scanner.py — Detecta archivos y funciones de prueba en un proyecto Python.

Busca archivos con el patrón test_*.py o *_test.py y extrae
las funciones que comienzan con test_ usando AST (sin ejecutar el código).
"""

import ast
import os
from pathlib import Path


def scan_project(project_path: str) -> dict:
    """
    Escanea un directorio buscando pruebas unitarias de pytest.

    Args:
        project_path: Ruta absoluta o relativa al proyecto.

    Returns:
        {
            "project_path": str,
            "test_files": [
                {
                    "file": str,           # ruta relativa al proyecto
                    "abs_path": str,       # ruta absoluta
                    "tests": [
                        {
                            "name": str,       # nombre de la función
                            "lineno": int,     # línea donde inicia
                            "code": str,       # código fuente de la función
                            "docstring": str,  # docstring si existe
                        },
                        ...
                    ]
                },
                ...
            ],
            "total_tests": int,
        }
    """
    root = Path(project_path).expanduser().resolve()

    if not root.exists():
        return {"error": f"La ruta '{project_path}' no existe."}
    if not root.is_dir():
        return {"error": f"'{project_path}' no es un directorio."}

    test_files = []
    total_tests = 0

    # Directorios a ignorar
    IGNORE_DIRS = {".git", "__pycache__", ".venv", "venv", "env", "node_modules", ".tox", "dist", "build"}

    for dirpath, dirnames, filenames in os.walk(root):
        # Filtrar directorios ignorados
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

        for filename in filenames:
            if _is_test_file(filename):
                abs_path = Path(dirpath) / filename
                rel_path = abs_path.relative_to(root)

                tests = _extract_tests(abs_path)
                if tests is not None:
                    test_files.append({
                        "file": str(rel_path),
                        "abs_path": str(abs_path),
                        "tests": tests,
                    })
                    total_tests += len(tests)

    return {
        "project_path": str(root),
        "test_files": test_files,
        "total_tests": total_tests,
    }


def _is_test_file(filename: str) -> bool:
    """Verifica si un archivo es un archivo de pruebas de pytest."""
    return filename.endswith(".py") and (
        filename.startswith("test_") or filename.endswith("_test.py")
    )


def _extract_tests(file_path: Path) -> list | None:
    """
    Extrae funciones de prueba de un archivo Python usando AST.
    Retorna None si el archivo no puede ser parseado.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    lines = source.splitlines()
    tests = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                code = _extract_function_source(lines, node)
                docstring = ast.get_docstring(node) or ""

                tests.append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "code": code,
                    "docstring": docstring,
                })

    return tests


def _extract_function_source(lines: list[str], node: ast.FunctionDef) -> str:
    """Extrae el código fuente de una función dado el árbol AST y las líneas."""
    start = node.lineno - 1  # AST usa base 1
    end = node.end_lineno     # inclusive, base 1

    func_lines = lines[start:end]

    # Calcular indentación base para normalizar
    if func_lines:
        indent = len(func_lines[0]) - len(func_lines[0].lstrip())
        func_lines = [line[indent:] if len(line) > indent else line for line in func_lines]

    return "\n".join(func_lines)
