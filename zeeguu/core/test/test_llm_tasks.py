"""
Keeps the LLM task registry (llm_services/tasks.py) in step with models.py,
so the live component map's Models view can't silently miss a task.
"""

import ast
import inspect
import pathlib

import pytest

from zeeguu.core.llm_services import models, tasks
from zeeguu.core.llm_services.llm_service import UnifiedLLMService

# Tasks whose service tries models in the order tasks.py lists, through
# run_llm_task. Add a task here when its service moves onto it.
ROUTED = {"EXPLAIN", "EXAMPLES", "LEARNING_CARD", "AUDIO_SCRIPT", "TOPIC_CHECK"}


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


def test_routed_tasks_are_used_outside_the_registry():
    """A routed task nobody passes to a service would be a task whose real order
    lives somewhere else."""
    root = pathlib.Path(tasks.__file__).parents[2]
    used = set()
    for path in root.rglob("*.py"):
        if "test" in path.parts or path.name == "tasks.py":
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "tasks":
                used.add(node.attr)
    assert ROUTED <= used, f"routed tasks no service runs: {sorted(ROUTED - used)}"


class _FakeService:
    def __init__(self, answers):
        self.answers = answers
        self.model = None
        self.asked = []

    def generate_text(self, prompt, max_tokens, temperature, system):
        self.asked.append(self.model)
        answer = self.answers[self.model]
        if isinstance(answer, Exception):
            raise answer
        return answer


def _service(task, answers):
    service = UnifiedLLMService(task)
    fake = _FakeService(answers)
    service._service_for = lambda model: (setattr(fake, "model", model), fake)[1]
    return service, fake


def test_unified_service_tries_models_in_the_task_order():
    task = tasks.EXAMPLES
    main, fallback = task.chain()
    service, fake = _service(task, {main: RuntimeError("down"), fallback: "from fallback"})
    assert service.generate_text_with_model("p") == ("from fallback", fallback)
    assert fake.asked == [main, fallback]


def test_explanation_order_follows_the_registry():
    """EXPLAIN is DeepSeek first, the reverse of the other tasks: the order must
    come from tasks.py, not from the service."""
    main, fallback = tasks.EXPLAIN.chain()
    assert main == models.WORD_EXPLANATION and fallback == models.WORD_EXPLANATION_FALLBACK
    service, fake = _service(tasks.EXPLAIN, {main: "explained", fallback: "unused"})
    assert service.generate_text("p") == "explained"
    assert fake.asked == [main]


def test_every_model_failing_raises():
    task = tasks.TOPIC_CHECK
    service, _ = _service(task, {m: RuntimeError("down") for m in task.chain()})
    with pytest.raises(Exception, match="every model failed"):
        service.generate_text("p")


def test_flag_models_are_not_fallbacks():
    assert models.SIMPLIFICATION not in tasks.CEFR_OWN_TEXT.chain()
