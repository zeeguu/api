"""
A botched splice once left two UnifiedLLMService classes (and two
_client_options) in llm_service.py; Python silently used the second.
"""

import ast
from pathlib import Path

import zeeguu.core.llm_services.llm_service as module


def _duplicates(body):
    names = [n.name for n in body if isinstance(n, (ast.ClassDef, ast.FunctionDef))]
    return sorted({n for n in names if names.count(n) > 1})


def test_llm_service_defines_each_name_once():
    tree = ast.parse(Path(module.__file__).read_text())
    assert _duplicates(tree.body) == []
    for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        assert _duplicates(cls.body) == [], cls.name
