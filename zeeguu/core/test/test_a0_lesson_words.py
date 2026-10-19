"""
The words an A0 lesson taught the learner to say go on their study list once
they have heard the lesson. See zeeguu/core/audio_lessons/lesson_words.py.
"""

from types import SimpleNamespace

from zeeguu.core.audio_lessons import lesson_words
from zeeguu.core.bookmark_operations import add_word_to_study as adding

DIALOGUE = SimpleNamespace(
    id=1,
    script="Woman: Hej! Hvad vil du have?\nMan: En kaffe, tak.",
    language=SimpleNamespace(code="da"),
    teacher_language=SimpleNamespace(code="en"),
)


class _Llm:
    def __init__(self, answer):
        self.answer = answer

    def generate_text(self, *args, **kwargs):
        return self.answer


def _answering(monkeypatch, answer):
    import zeeguu.core.llm_services.llm_service as llm_service

    monkeypatch.setattr(llm_service, "get_llm_service", lambda *a, **k: _Llm(answer))


def test_reads_the_words_out_of_the_answer(monkeypatch):
    _answering(
        monkeypatch,
        'Here they are:\n[{"word": "kaffe", "translation": "coffee", "sentence": "En kaffe, tak."},'
        ' {"word": "tak", "translation": "thank you"}]',
    )
    assert lesson_words.words_taught_to_say(DIALOGUE) == [
        ("kaffe", "coffee", "En kaffe, tak."),
        ("tak", "thank you", "tak"),
    ]


def test_an_unreadable_answer_schedules_nothing(monkeypatch):
    _answering(monkeypatch, "[not json")
    assert lesson_words.words_taught_to_say(DIALOGUE) == []


class _Savepoint:
    def commit(self):
        pass

    def rollback(self):
        pass


def test_a_word_not_found_in_its_sentence_is_tried_on_its_own(monkeypatch):
    monkeypatch.setattr(
        lesson_words,
        "words_taught_to_say",
        lambda dialogue: [("kaffe", "coffee", "Hej!"), ("tak", "thank you", "En kaffe, tak.")],
    )
    tried = []

    def add(session, user, word, translation, from_code, to_code, context):
        tried.append((word, context))
        if word not in context.lower():
            raise adding.WordNotInContext("not_found", "not there")
        return None, None

    monkeypatch.setattr(adding, "add_word_to_study", add)
    session = SimpleNamespace(begin_nested=lambda: _Savepoint())

    assert lesson_words.schedule_words_from_lesson(session, SimpleNamespace(id=7), DIALOGUE) == 2
    assert tried == [("kaffe", "Hej!"), ("kaffe", "kaffe"), ("tak", "En kaffe, tak.")]
