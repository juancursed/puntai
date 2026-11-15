"""
Pruebas de uniteval.core.source_resolver.
"""

from pathlib import Path

from uniteval.core import source_resolver

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
