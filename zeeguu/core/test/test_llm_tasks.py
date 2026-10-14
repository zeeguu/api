"""
Keeps the LLM task registry (llm_services/tasks.py) in step with models.py,
so the live component map's Models view can't silently miss a task.
"""

import ast
import inspect

from zeeguu.core.llm_services import models, tasks


def _roles():
    """Names in models.py assigned from another constant (WORD_TRANSLATION =
    ANTHROPIC_SONNET), as opposed to the canonical model IDs (string literals)."""
    tree = ast.parse(inspect.getsource(models))
    return {
        node.targets[0].id
        for node in tree.body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name)
    }


def _roles_used_in_tasks():
    tree = ast.parse(inspect.getsource(tasks))
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "models"
    }


def test_every_role_in_models_has_a_task():
    missing = _roles() - _roles_used_in_tasks()
    assert not missing, (
        f"models.py roles with no task in llm_services/tasks.py: {sorted(missing)}. "
        "Add the task there so it shows on the component map."
    )


def test_tasks_use_known_models_and_roles():
    for task in tasks.TASKS:
        assert task.group in tasks.GROUPS, task.id
        assert task.status in ("live", "manual", "off"), task.id
        assert task.models, task.id
        for model, role in task.models:
            assert model in tasks.MODEL_INFO, f"{task.id}: {model} has no MODEL_INFO entry"
            assert role in ("main", "fallback", "flag"), task.id


def test_task_ids_are_unique():
    ids = [t.id for t in tasks.TASKS]
    assert len(ids) == len(set(ids))


def test_as_json_is_serializable():
    import json

    data = json.loads(json.dumps(tasks.as_json()))
    assert len(data["tasks"]) == len(tasks.TASKS)
