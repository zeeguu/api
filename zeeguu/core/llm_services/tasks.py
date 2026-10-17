"""
Every task Zeeguu gives an LLM, with the models it uses and where it runs.

models.py says which model each role uses; this says which tasks there are and
how each one falls back. The "Models" view of the live component map is built
from it:

    python -m zeeguu.core.llm_services.tasks > llm_tasks.json

test_llm_tasks.py fails when models.py gains a role that no task here uses, so a
new LLM feature can't ship without showing up on the map. The fallback order is
written here by hand: when you change it in a service, change it here too.

Fields:
  models       (model ID, "main" | "fallback" | "flag") in the order they are tried;
               "flag" means chosen by a setting or a missing key, not by errors.
  entry_points Sentry transaction names minus "endpoints.": API endpoint
               functions, and "task:<name>" for cron jobs (run_task.sh names).
  status       "live", "manual" (run by hand) or "off".
"""

import json
from dataclasses import asdict, dataclass

from zeeguu.core.llm_services import models

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


TASKS = [
    # --- Reading ---
    LLMTask(
        "ask_llm", "Ask LLM translation", "a word or phrase in its context", "read",
        ((models.WORD_TRANSLATION, "main"), (models.MWE_TRANSLATION, "main")),
        "No fallback: the reader shows \"try again\".",
        ("ask_llm_translation", "get_multiple_translations", "get_translations_stream"),
        "core/llm_services/mwe_translation_service.py",
    ),
    LLMTask(
        "explain", "Word explanation", "explain a selected word", "read",
        ((models.WORD_EXPLANATION, "main"), (models.WORD_EXPLANATION_FALLBACK, "fallback")),
        "The fallback answers when the main model raises. DeepSeek is first on purpose: "
        "it was measured more reliable on Danish compounds (see models.py).",
        ("explain_selection", "explain_selection_endpoint"),
        "core/llm_services/llm_service.py",
    ),
    LLMTask(
        "simplify", "On-demand simplification", "an easier level of an article or own text", "read",
        ((models.DEEPSEEK_GENERAL, "main"), (models.SIMPLIFICATION, "fallback")),
        "Fallback on an error, an empty reply, a reply still in the wrong language "
        "after one retry, or a missing DeepSeek key.",
        ("simplify_article", "simplify_own_text", "article_upload_simplify", "share_article_with_friend"),
        "core/llm_services/simplification_service.py",
    ),
    LLMTask(
        "adapt", "Translate and adapt", "an article into another language", "read",
        ((models.DEEPSEEK_GENERAL, "main"), (models.SIMPLIFICATION, "fallback")),
        "Fallback on an error or a reply in the wrong language.",
        ("translate_and_adapt_article", "article_upload_translate_and_adapt", "share_article_with_friend"),
        "core/llm_services/simplification_service.py",
    ),
    LLMTask(
        "cefr", "CEFR and topic of an opened article", "user-initiated assessment, uploaded articles", "read",
        ((models.SIMPLIFICATION, "main"), (models.DEEPSEEK_GENERAL, "fallback")),
        "Fallback when the main model raises or returns nothing.",
        ("find_or_create_article", "article_upload_promote", "assess_llm"),
        "core/llm_services/simplification_service.py",
    ),
    LLMTask(
        "cefr_own_text", "CEFR of an own text", "own texts, texts sent to a colleague", "read",
        ((models.DEEPSEEK_GENERAL, "main"), (models.SIMPLIFICATION, "flag")),
        "No fallback on errors. The other model is used only when the DeepSeek key is missing.",
        ("upload_own_text", "send_article_to_colleague"),
        "core/llm_services/simplification_service.py",
    ),
    # --- Words and exercises ---
    LLMTask(
        "examples", "Example sentences", "exercises, word page, nightly prefetch", "words",
        ((models.ANTHROPIC_GENERAL, "main"), (models.DEEPSEEK_GENERAL, "fallback")),
        "Fallback when the main model raises, including a reply still in the wrong language "
        "after one retry. The LLM_PROVIDER env var can change the order.",
        ("alternative_sentences", "generate_examples_for_word", "task:prefetch_sentences"),
        "core/llm_services/llm_service.py",
    ),
    LLMTask(
        "learning_card", "Learning card", "when a word is added to learning", "words",
        ((models.ANTHROPIC_GENERAL, "main"), (models.DEEPSEEK_GENERAL, "fallback")),
        "Fallback when the main model raises (after a 120 s timeout and 2 retries).",
        ("add_word_to_learning", "preview_learning_card"),
        "core/llm_services/llm_service.py",
    ),
    LLMTask(
        "validate", "Translation validation", "plus frequency, phrase type, duplicate check", "words",
        ((models.TRANSLATION_VALIDATION, "main"),),
        "No fallback model. On error it fails open: the translation counts as valid.",
        ("report_exercise_outcome", "submit_answer", "add_custom_word", "set_user_word_exercise_preference",
         "add_word_to_learning", "update_lesson_state", "generate_daily_lesson",
         "task:daily_audio_lessons", "task:prefetch_sentences"),
        "core/llm_services/translation_validator.py",
    ),
    LLMTask(
        "cloze_judge", "Cloze alternative judge", "does the word a learner typed also fit?", "words",
        ((models.CLOZE_ALTERNATIVE_JUDGE, "main"),),
        "No fallback. Past a 6 s timeout the answer is judged wrong, as before. "
        "Verdicts are stored, so each (meaning, typed word) is judged once.",
        ("judge_cloze_alternative",),
        "core/llm_services/cloze_alternative_judge.py",
    ),
    # --- Audio lessons ---
    LLMTask(
        "audio_script", "Audio lesson scripts", "meaning lessons and dialogues", "audio",
        ((models.ANTHROPIC_GENERAL, "main"), (models.DEEPSEEK_GENERAL, "fallback")),
        "Fallback when the main model raises, e.g. at the monthly Anthropic cap. "
        "The lesson records which model wrote it.",
        ("generate_daily_lesson", "task:precompute_audio", "task:daily_audio_lessons"),
        "core/llm_services/llm_service.py, core/audio_lessons/script_generator.py",
    ),
    LLMTask(
        "topic_check", "Lesson topic check", "validates a learner's topic suggestion", "audio",
        ((models.ANTHROPIC_GENERAL, "main"), (models.DEEPSEEK_GENERAL, "fallback")),
        "Fallback when the main model raises. If both fail, the suggestion is allowed after basic cleaning.",
        ("generate_daily_lesson", "task:daily_audio_lessons"),
        "core/audio_lessons/suggestion_validator.py",
    ),
    # --- Crawler ---
    LLMTask(
        "summary", "Summary simplification", "every crawled article: CEFR, summary and title per level, type, disturbing", "crawl",
        ((models.DEEPSEEK_GENERAL, "flag"), (models.SIMPLIFICATION, "flag")),
        "Chosen by flag, not by errors: the crawl passes --provider deepseek; the other model "
        "only if the DeepSeek key is missing. A DeepSeek outage leaves articles without summaries.",
        ("task:crawl",),
        "core/llm_services/simplification_and_classification.py",
    ),
    # --- Off, dormant or manual ---
    LLMTask(
        "meaning_frequency", "Meaning frequency", "COMMON / RARE / ... for a meaning", "off",
        ((models.MEANING_FREQUENCY, "main"),),
        "No fallback.",
        (), "core/model/meaning_frequency_classifier.py", status="manual",
    ),
    LLMTask(
        "mwe_detection", "MWE detection", "dormant: no language enabled", "off",
        ((models.MWE_DETECTION, "main"),),
        "HYBRID_LANGUAGES is empty.",
        (), "core/mwe/llm_mwe_detector.py", status="off",
    ),
    LLMTask(
        "grammar", "Grammar correction", "of simplified text; off by default", "off",
        ((models.GRAMMAR_CORRECTION_ANTHROPIC, "main"), (models.GRAMMAR_CORRECTION_DEEPSEEK, "fallback")),
        "correct_grammar=False everywhere.",
        (), "core/llm_services/grammar_correction_service.py", status="off",
    ),
    LLMTask(
        "simplify_at_crawl", "Full simplification at crawl", "old path; SIMPLIFY_AT_CRAWL is off", "off",
        ((models.DEEPSEEK_GENERAL, "flag"), (models.SIMPLIFICATION, "flag")),
        "Replaced by on-demand simplification. Same provider rules as Summary simplification.",
        (), "core/content_retriever/article_downloader.py", status="off",
    ),
]


def as_json():
    return {
        "models": MODEL_INFO,
        "groups": GROUPS,
        "tasks": [asdict(t) for t in TASKS],
    }


if __name__ == "__main__":
    print(json.dumps(as_json(), indent=1, ensure_ascii=False))
