"""Standard-library imports belong at the top of the file, where the reader
sees what a module depends on. Unlike our own modules, they can't be part of
an import cycle, so nothing forces them into a function."""
import ast
import sys
from pathlib import Path

import zeeguu

ROOT = Path(zeeguu.__file__).parent


def _names(node):
    """The name each alias binds, with the statement that binds it."""
    if isinstance(node, ast.Import):
        return {a.asname or a.name.split(".")[0]: a.name for a in node.names}
    return {a.asname or a.name: f"{node.module}.{a.name}" for a in node.names}


def _is_stdlib(node):
    if isinstance(node, ast.ImportFrom):
        return not node.level and node.module.split(".")[0] in sys.stdlib_module_names
    return node.names[0].name.split(".")[0] in sys.stdlib_module_names


def _function_level_stdlib_imports(tree):
    for function in ast.walk(tree):
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(function):
                if isinstance(node, (ast.Import, ast.ImportFrom)) and _is_stdlib(node):
                    yield node


def _offenders(path):
    tree = ast.parse(path.read_text())
    at_top = {}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            at_top.update(_names(node))

    for node in _function_level_stdlib_imports(tree):
        # `import datetime` next to a top-level `from datetime import datetime`
        # can't move: one name, two meanings.
        if all(at_top.get(name, source) == source for name, source in _names(node).items()):
            yield f"{path.relative_to(ROOT.parent)}:{node.lineno}"


def test_stdlib_imports_are_at_the_top_of_the_file():
    sources = [p for p in ROOT.rglob("*.py") if "test" not in p.relative_to(ROOT).parts]
    assert sorted(o for p in sources for o in _offenders(p)) == []
