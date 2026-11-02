"""
source_resolver.py — Localiza el código fuente que ejercita una prueba unitaria.

Solo usa AST, sin ejecutar nada. Parte de los nombres usados en la prueba, sigue
sus fixtures y helpers (archivo de prueba y conftest.py) y los busca en un índice
de los módulos del proyecto. Indexar por nombre, en vez de seguir los imports,
resuelve también las reexportaciones de __init__.py. Las dependencias internas
(otras funciones, métodos vía self, constantes) se recorren de forma transitiva.
"""

import ast
import os
from collections import deque
from pathlib import Path

from scanner import IGNORE_DIRS, _is_test_file

# Límite para no enviar proyectos enteros a la IA en cada prueba.
MAX_SOURCE_CHARS = 20000

_INIT_METHODS = {"__init__", "__post_init__", "__new__"}
_SETUP_METHODS = {"setup_method", "setUp", "setup_class", "setUpClass"}
_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def find_source_code(project_path: str, test_file: str, test_name: str) -> dict:
    """
    Devuelve el código fuente relacionado con una prueba.

    Returns:
        {"code": str, "files": [rutas relativas], "truncated": bool}.
        "code" queda vacío si no se localizó nada.
    """
    empty = {"code": "", "files": [], "truncated": False}
    root = Path(project_path).expanduser().resolve()
    test_path = (root / test_file).resolve()
    if not test_path.is_relative_to(root):
        return empty

    tree = _parse(test_path)
    if tree is None:
        return empty

    test_node, test_class = _find_test(tree, test_name)
    if test_node is None:
        return empty

    support = _support_functions(root, test_path, tree)
    roots = [test_node] + _setup_methods(test_class)
    names = _names_reachable_from_test(roots, support)
    definitions = _index_project(root)
    selected = _select_definitions(names, definitions, _imported_modules(tree))
    return _render(selected)


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
        return None


def _find_test(tree: ast.Module, test_name: str) -> tuple:
    for node in tree.body:
        if isinstance(node, _FUNCTION_NODES) and node.name == test_name:
            return node, None
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, _FUNCTION_NODES) and child.name == test_name:
                    return child, node
    return None, None


def _setup_methods(test_class: ast.ClassDef | None) -> list:
    if test_class is None:
        return []
    return [
        child for child in test_class.body
        if isinstance(child, _FUNCTION_NODES) and child.name in _SETUP_METHODS
    ]


def _support_functions(root: Path, test_path: Path, tree: ast.Module) -> dict:
    """Fixtures y helpers visibles para la prueba; el más cercano tiene prioridad."""
    support = {}
    directories = [test_path.parent, *test_path.parent.parents]
    for directory in reversed(directories):
        if not directory.is_relative_to(root):
            continue
        conftest = _parse(directory / "conftest.py")
        if conftest is not None:
            support.update(_module_functions(conftest))
    support.update(_module_functions(tree))
    return support


def _module_functions(tree: ast.Module) -> dict:
    return {
        node.name: node for node in tree.body
        if isinstance(node, _FUNCTION_NODES) and not node.name.startswith("test_")
    }


def _names_in(node: ast.AST) -> set[str]:
    """Nombres y atributos usados dentro de un nodo."""
    names = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


def _parameters(node: ast.AST) -> set[str]:
    return {arg.arg for arg in ast.walk(node.args) if isinstance(arg, ast.arg)}


def _names_reachable_from_test(roots: list, support: dict) -> list[str]:
    """Nombres usados por la prueba, sus fixtures y sus helpers, en orden estable."""
    names = []
    seen = set()
    pending = deque(roots)
    visited = set()
    while pending:
        node = pending.popleft()
        if id(node) in visited:
            continue
        visited.add(id(node))
        for name in sorted(_names_in(node) | _parameters(node)):
            if name in support:
                pending.append(support[name])
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _index_project(root: Path) -> dict:
    """Mapea cada nombre a sus definiciones en los módulos que no son de prueba."""
    index: dict[str, list] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for filename in filenames:
            if not filename.endswith(".py") or filename == "conftest.py" or _is_test_file(filename):
                continue
            path = Path(dirpath) / filename
            _index_module(path, path.relative_to(root).as_posix(), index)
    return index


def _index_module(path: Path, rel_path: str, index: dict) -> None:
    tree = _parse(path)
    if tree is None:
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    for node in tree.body:
        for name in _defined_names(node):
            index.setdefault(name, []).append(
                {"file": rel_path, "node": node, "lines": lines}
            )


def _defined_names(node: ast.stmt) -> list[str]:
    if isinstance(node, (*_FUNCTION_NODES, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.Assign):
        return [t.id for t in node.targets if isinstance(t, ast.Name)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


def _imported_modules(tree: ast.Module) -> set[str]:
    """Rutas (a/b) de los módulos importados, para desambiguar nombres repetidos."""
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.replace(".", "/"))
        elif isinstance(node, ast.Import):
            modules.update(alias.name.replace(".", "/") for alias in node.names)
    return modules


def _pick_candidates(candidates: list, imported: set[str]) -> list:
    if len(candidates) == 1:
        return candidates
    preferred = [
        c for c in candidates
        if any(
            c["file"].removesuffix(".py").removesuffix("/__init__").endswith(module)
            for module in imported
        )
    ]
    return preferred or candidates


def _select_definitions(names: list[str], index: dict, imported: set[str]) -> list:
    """
    Recorre en anchura los nombres y sus dependencias internas.

    Devuelve entradas {"file", "node", "lines", "methods"}, donde "methods" son
    los métodos conservados si la definición es una clase.
    """
    selected: dict[tuple, dict] = {}
    pending = deque(names)
    seen = set()
    used_names = set(names)

    def visit(node: ast.AST) -> None:
        for name in sorted(_names_in(node)):
            used_names.add(name)
            pending.append(name)

    while pending:
        name = pending.popleft()
        if name in seen:
            continue
        seen.add(name)
        for candidate in _pick_candidates(index.get(name, []), imported):
            node = candidate["node"]
            key = (candidate["file"], node.lineno)
            if key in selected:
                continue
            selected[key] = {**candidate, "methods": set()}
            if not isinstance(node, ast.ClassDef):
                visit(node)

        # Un método recién usado puede pertenecer a una clase ya seleccionada.
        for entry in selected.values():
            if isinstance(entry["node"], ast.ClassDef):
                for method in _class_methods(entry["node"]):
                    keep = method.name in _INIT_METHODS or method.name in used_names
                    if keep and method.name not in entry["methods"]:
                        entry["methods"].add(method.name)
                        visit(method)

    return list(selected.values())


def _class_methods(node: ast.ClassDef) -> list:
    return [child for child in node.body if isinstance(child, _FUNCTION_NODES)]


def _start_line(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", [])
    return min([node.lineno] + [d.lineno for d in decorators])


def _source_of(entry: dict) -> str:
    """Código de la definición; en clases omite los métodos que no se usan."""
    node = entry["node"]
    start, end = _start_line(node), node.end_lineno
    skipped = set()
    if isinstance(node, ast.ClassDef):
        for method in _class_methods(node):
            if method.name not in entry["methods"]:
                skipped.update(range(_start_line(method), method.end_lineno + 1))
    kept = [
        entry["lines"][number - 1]
        for number in range(start, end + 1)
        if number not in skipped
    ]
    return _collapse_blank_lines(kept)


def _collapse_blank_lines(lines: list[str]) -> str:
    result = []
    for line in lines:
        if line.strip() or (result and result[-1].strip()):
            result.append(line)
    return "\n".join(result).rstrip()


def _render(selected: list) -> dict:
    """Aplica el límite (las dependencias lejanas salen primero) y agrupa por archivo."""
    kept = []
    used = 0
    truncated = False
    for entry in selected:
        source = _source_of(entry)
        if used + len(source) > MAX_SOURCE_CHARS:
            truncated = True
            continue
        used += len(source)
        kept.append((entry["file"], entry["node"].lineno, source))

    kept.sort(key=lambda item: item[:2])
    files = sorted({file for file, _, _ in kept})
    blocks = []
    for file in files:
        sources = [source for f, _, source in kept if f == file]
        blocks.append(f"# Archivo: {file}\n" + "\n\n".join(sources))

    return {"code": "\n\n".join(blocks), "files": files, "truncated": truncated}
