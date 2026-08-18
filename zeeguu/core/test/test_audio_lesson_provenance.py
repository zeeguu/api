"""
Recording which model and prompt produced an audio lesson script.

Both bugs these pin shipped in a green suite, because nothing constructed an
AudioLessonDialogue and nothing checked that a prompt version fits the column it
is stored in. They are cheap to hold: no LLM, no audio, no DB writes.
"""

from unittest.mock import MagicMock
from pathlib import Path

from zeeguu.core.audio_lessons.script_generator import prompt_version_of
from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue
from zeeguu.core.model.audio_lesson_meaning import AudioLessonMeaning

PROMPTS = Path(__file__).parent.parent / "audio_lessons" / "prompts"


def test_a_meaning_lesson_takes_the_generator_that_wrote_it():
    lesson = AudioLessonMeaning(
        meaning=MagicMock(id=1),
        script="Man: Hej",
        difficulty_level="A2",
        ai_generator=MagicMock(id=7),
    )
    assert lesson.ai_generator_id == 7


def test_a_dialogue_takes_the_generator_that_wrote_it():
    # daily_lesson_generator passes ai_generator=; the constructor used to
    # reference it without accepting it, so every dialogue raised TypeError.
    dialogue = AudioLessonDialogue(
        script="Man: Hej",
        canonical_suggestion="at the cafe",
        lesson_type="topic",
        language=MagicMock(id=1),
        ai_generator=MagicMock(id=7),
    )
    assert dialogue.ai_generator_id == 7


def test_a_lesson_without_a_generator_is_still_constructible():
    # Old rows and any path that does not know: the column is nullable.
    assert AudioLessonMeaning(meaning=MagicMock(id=1), script="x").ai_generator_id is None
    assert (
        AudioLessonDialogue(
            script="x", canonical_suggestion="s", lesson_type="topic",
            language=MagicMock(id=1),
        ).ai_generator_id
        is None
    )


def test_every_prompt_version_fits_the_column_it_is_stored_in():
    # The meaning prompt's filename is 62 characters against a VARCHAR(50); the
    # insert failed inside AIGenerator.find_or_create's own except: block, so
    # every meaning lesson would have failed to generate.
    limit = AIGenerator.__table__.columns["prompt_version"].type.length
    for prompt_file in PROMPTS.glob("*.txt"):
        version = prompt_version_of(prompt_file.name)
        assert len(version) <= limit, f"{prompt_file.name} -> {version} ({len(version)} > {limit})"


def test_the_recorded_version_survives_rewording_the_filename():
    # What identifies a prompt is its family and version. The description in the
    # middle names its strategy, and rewording that is a tidy-up, not a new
    # version — it must not look like one.
    assert prompt_version_of("meaning_lesson--teacher_challenges_both_dialogue_and_beyond-v4.txt") == "meaning_lesson-v4"
    assert prompt_version_of("meaning_lesson--something_much_shorter-v4.txt") == "meaning_lesson-v4"
    assert prompt_version_of("meaning_lesson--teacher_challenges_both_dialogue_and_beyond-v5.txt") == "meaning_lesson-v5"
