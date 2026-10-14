"""
Every task Zeeguu gives an LLM, with the models it uses and where it runs.

models.py says which model each role uses; this says which tasks there are and
how each one falls back. The "Models" view of the live component map is built
from it:

    python -m zeeguu.core.llm_services.tasks > llm_tasks.json

test_llm_tasks.py fails when models.py gains a role that no task here uses, so a
new LLM feature can't ship without showing up on the map.

Services run a task through run_llm_task(), which tries the task's models in the
order listed here, so the order on the map is the order in production. Tasks not
moved onto it yet still keep their own order in their service; test_llm_tasks.py
lists which ones are.

Fields:
  models       (model ID, "main" | "fallback" | "flag") in the order they are tried;
               "flag" means chosen by a setting or a missing key, not by errors.
  entry_points Sentry transaction names minus "endpoints.": API endpoint
               functions, and "task:<name>" for cron jobs (run_task.sh names).
  status       "live", "manual" (run by hand) or "off".
"""

import json
from dataclasses import asdict, dataclass

import sentry_sdk

from zeeguu.core.llm_services import models
from zeeguu.logging import log

# How each model is called, shown under its column on the map
MODEL_INFO = {
    models.ANTHROPIC_SONNET: "Anthropic SDK, thinking off",
    models.ANTHROPIC_HAIKU: "Anthropic SDK, low-effort thinking",
    models.DEEPSEEK_CHAT: "raw HTTP",
}

GROUPS = {
    "read": "Reading",
    "words": "Words and exercises",
    "audio": "Audio lessons",
    "crawl": "Crawler",
    "off": "Off, dormant or manual",
}


@dataclass(frozen=True)
class LLMTask:
    id: str
    label: str
    about: str
    group: str
    models: tuple
    fallback_when: str
    entry_points: tuple
    code: str
    status: str = "live"

    def chain(self):
        """The models tried after an error, in order. "flag" models are chosen by a
        setting, not by errors, so they are not part of it."""
        return [model for model, role in self.models if role in ("main", "fallback")]


def run_llm_task(task, call):
    """
    Try `call(model)` for each model in the task's chain until one returns.
    Returns (result, model that answered); raises when every model failed.

    Recorded in Sentry as an llm.task span described "<task id> <model>", so the
    component map counts calls per task and model, fallbacks included.
    """
    chain = task.chain()
    errors = []
    with sentry_sdk.start_span(op="llm.task", name=task.id) as span:
        for i, model in enumerate(chain):
            try:
                result = call(model)
            except Exception as e:
                log(f"[{task.id}] {model} failed: {e}")
                errors.append(f"{model}: {e}")
                continue
            if i:
                log(f"[{task.id}] answered by fallback {model}")
            span.description = f"{task.id} {model}"
            span.set_data("llm.model", model)
            span.set_data("llm.fallback", i > 0)
            return result, model
        span.description = f"{task.id} failed"
        span.set_status("internal_error")
        raise Exception(f"{task.label}: every model failed ({'; '.join(errors)})")


# --- Reading ---

ASK_LLM = LLMTask(
    "ask_llm", "Ask LLM translation", "a word or phrase in its context", "read",
    ((models.WORD_TRANSLATION, "main"), (models.MWE_TRANSLATION, "main")),
    "No fallback: the reader shows \"try again\".",
    ("ask_llm_translation", "get_multiple_translations", "get_translations_stream"),
    "core/llm_services/mwe_translation_service.py",
)

EXPLAIN = LLMTask(
    "explain", "Word explanation", "explain a selected word", "read",
    ((models.WORD_EXPLANATION, "main"), (models.WORD_EXPLANATION_FALLBACK, "fallback")),
    "The fallback answers when the main model raises. DeepSeek is first on purpose: "
    "it was measured more reliable on Danish compounds (see models.py).",
    ("explain_selection", "explain_selection_endpoint"),
    "core/llm_services/llm_service.py",
)

SIMPLIFY = LLMTask(
    "simplify", "On-demand simplification", "an easier level of an article or own text", "read",
    ((models.DEEPSEEK_GENERAL, "main"), (models.SIMPLIFICATION, "fallback")),
    "Fallback on an error, an empty reply, a reply still in the wrong language "
    "after one retry, or a missing DeepSeek key.",
    ("simplify_article", "simplify_own_text", "article_upload_simplify", "share_article_with_friend"),
    "core/llm_services/simplification_service.py",
)

ADAPT = LLMTask(
    "adapt", "Translate and adapt", "an article into another language", "read",
    ((models.DEEPSEEK_GENERAL, "main"), (models.SIMPLIFICATION, "fallback")),
    "Fallback on an error or a reply in the wrong language.",
    ("translate_and_adapt_article", "article_upload_translate_and_adapt", "share_article_with_friend"),
    "core/llm_services/simplification_service.py",
)

CEFR = LLMTask(
    "cefr", "CEFR and topic of an opened article", "user-initiated assessment, uploaded articles", "read",
    ((models.SIMPLIFICATION, "main"), (models.DEEPSEEK_GENERAL, "fallback")),
    "Fallback when the main model raises or returns nothing.",
    ("find_or_create_article", "article_upload_promote", "assess_llm"),
    "core/llm_services/simplification_service.py",
)

CEFR_OWN_TEXT = LLMTask(
    "cefr_own_text", "CEFR of an own text", "own texts, texts sent to a colleague", "read",
    ((models.DEEPSEEK_GENERAL, "main"), (models.SIMPLIFICATION, "flag")),
    "No fallback on errors. The other model is used only when the DeepSeek key is missing.",
    ("upload_own_text", "send_article_to_colleague"),
    "core/llm_services/simplification_service.py",
)


# --- Words and exercises ---

EXAMPLES = LLMTask(
    "examples", "Example sentences", "exercises, word page, nightly prefetch", "words",
    ((models.ANTHROPIC_GENERAL, "main"), (models.DEEPSEEK_GENERAL, "fallback")),
    "Fallback when the main model raises, including a reply still in the wrong language "
    "after one retry. The LLM_PROVIDER env var can change the order.",
    ("alternative_sentences", "generate_examples_for_word", "task:prefetch_sentences"),
    "core/llm_services/llm_service.py",
)

LEARNING_CARD = LLMTask(
    "learning_card", "Learning card", "when a word is added to learning", "words",
    ((models.ANTHROPIC_GENERAL, "main"), (models.DEEPSEEK_GENERAL, "fallback")),
    "Fallback when the main model raises (after a 120 s timeout and 2 retries).",
    ("add_word_to_learning", "preview_learning_card"),
    "core/llm_services/llm_service.py",
)

VALIDATE = LLMTask(
    "validate", "Translation validation", "plus frequency, phrase type, duplicate check", "words",
    ((models.TRANSLATION_VALIDATION, "main"),),
    "No fallback model. On error it fails open: the translation counts as valid.",
    ("report_exercise_outcome", "submit_answer", "add_custom_word", "set_user_word_exercise_preference",
     "add_word_to_learning", "update_lesson_state", "generate_daily_lesson",
     "task:daily_audio_lessons", "task:prefetch_sentences"),
    "core/llm_services/translation_validator.py",
)

CLOZE_JUDGE = LLMTask(
    "cloze_judge", "Cloze alternative judge", "does the word a learner typed also fit?", "words",
    ((models.CLOZE_ALTERNATIVE_JUDGE, "main"),),
    "No fallback. Past a 6 s timeout the answer is judged wrong, as before. "
    "Verdicts are stored, so each (meaning, typed word) is judged once.",
    ("judge_cloze_alternative",),
    "core/llm_services/cloze_alternative_judge.py",
)


# --- Audio lessons ---

AUDIO_SCRIPT = LLMTask(
    "audio_script", "Audio lesson scripts", "meaning lessons and dialogues", "audio",
    ((models.ANTHROPIC_GENERAL, "main"), (models.DEEPSEEK_GENERAL, "fallback")),
    "Fallback when the main model raises, e.g. at the monthly Anthropic cap. "
    "The lesson records which model wrote it.",
    ("generate_daily_lesson", "task:precompute_audio", "task:daily_audio_lessons"),
    "core/llm_services/llm_service.py, core/audio_lessons/script_generator.py",
)

TOPIC_CHECK = LLMTask(
    "topic_check", "Lesson topic check", "validates a learner's topic suggestion", "audio",
    ((models.ANTHROPIC_GENERAL, "main"), (models.DEEPSEEK_GENERAL, "fallback")),
    "Fallback when the main model raises. If both fail, the suggestion is allowed after basic cleaning.",
    ("generate_daily_lesson", "task:daily_audio_lessons"),
    "core/audio_lessons/suggestion_validator.py",
)


# --- Crawler ---

SUMMARY = LLMTask(
    "summary", "Summary simplification", "every crawled article: CEFR, summary and title per level, type, disturbing", "crawl",
    ((models.DEEPSEEK_GENERAL, "flag"), (models.SIMPLIFICATION, "flag")),
    "Chosen by flag, not by errors: the crawl passes --provider deepseek; the other model "
    "only if the DeepSeek key is missing. A DeepSeek outage leaves articles without summaries.",
    ("task:crawl",),
    "core/llm_services/simplification_and_classification.py",
)


# --- Off, dormant or manual ---

MEANING_FREQUENCY = LLMTask(
    "meaning_frequency", "Meaning frequency", "COMMON / RARE / ... for a meaning", "off",
    ((models.MEANING_FREQUENCY, "main"),),
    "No fallback.",
    (), "core/model/meaning_frequency_classifier.py", status="manual",
)

MWE_DETECTION = LLMTask(
    "mwe_detection", "MWE detection", "dormant: no language enabled", "off",
    ((models.MWE_DETECTION, "main"),),
    "HYBRID_LANGUAGES is empty.",
    (), "core/mwe/llm_mwe_detector.py", status="off",
)

GRAMMAR = LLMTask(
    "grammar", "Grammar correction", "of simplified text; off by default", "off",
    ((models.GRAMMAR_CORRECTION_ANTHROPIC, "main"), (models.GRAMMAR_CORRECTION_DEEPSEEK, "fallback")),
    "correct_grammar=False everywhere.",
    (), "core/llm_services/grammar_correction_service.py", status="off",
)

SIMPLIFY_AT_CRAWL = LLMTask(
    "simplify_at_crawl", "Full simplification at crawl", "old path; SIMPLIFY_AT_CRAWL is off", "off",
    ((models.DEEPSEEK_GENERAL, "flag"), (models.SIMPLIFICATION, "flag")),
    "Replaced by on-demand simplification. Same provider rules as Summary simplification.",
    (), "core/content_retriever/article_downloader.py", status="off",
)

TASKS = [
    ASK_LLM,
    EXPLAIN,
    SIMPLIFY,
    ADAPT,
    CEFR,
    CEFR_OWN_TEXT,
    EXAMPLES,
    LEARNING_CARD,
    VALIDATE,
    CLOZE_JUDGE,
    AUDIO_SCRIPT,
    TOPIC_CHECK,
    SUMMARY,
    MEANING_FREQUENCY,
    MWE_DETECTION,
    GRAMMAR,
    SIMPLIFY_AT_CRAWL,
]


def as_json():
    return {
        "models": MODEL_INFO,
        "groups": GROUPS,
        "tasks": [asdict(t) for t in TASKS],
    }


if __name__ == "__main__":
    print(json.dumps(as_json(), indent=1, ensure_ascii=False))
