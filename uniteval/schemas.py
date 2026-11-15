"""
schemas.py — Modelos de datos de entrada de la API.
"""

from pydantic import BaseModel

from uniteval.config import DEFAULT_MODEL, DEFAULT_OPENROUTER_MODEL


class ProjectRequest(BaseModel):
    path: str


class AnalyzeRequest(BaseModel):
    project_path: str
    test_file: str
    test_name: str
    test_code: str
    test_result: str  # PASS | FAIL | ERROR | SKIP
    model: str = DEFAULT_MODEL  # claude | openai | laguna


class ReportPayload(BaseModel):
    id: str | None = None
    project_path: str = ""
    model: str = ""
    summary: dict = {}
    scanned_tests: list = []
    run_results: list = []
    analyses: dict = {}


class ConfigUpdate(BaseModel):
    project_path: str = ""
    model: str = DEFAULT_MODEL
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = DEFAULT_OPENROUTER_MODEL
