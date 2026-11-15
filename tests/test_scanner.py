"""
Pruebas de uniteval.core.scanner.
"""

from pathlib import Path

from uniteval.core import scanner

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
