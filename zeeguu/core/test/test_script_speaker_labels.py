"""
Dialogue lines labeled with the characters' names are never spoken.

Production dialogue 525 (Danish, A1, 18 Nov 2026) labeled its dialogue
"Mads:" and "Sofie:"; parse_script found no voice on those lines and the
learner heard only the challenges. No Flask app context or DB needed.
"""

from unittest.mock import patch

import pytest

from zeeguu.core.audio_lessons import script_generator
from zeeguu.core.audio_lessons.script_parser import parse_script, unknown_speaker_labels

# Abridged from production dialogue 525.
NAMED_SPEAKERS = """Two Friends Compare Beach and Mountain Holidays

Teacher: Two friends, Mads and Sofie, are planning their holidays. Listen to how they talk. [0.5 seconds]

[1 seconds]

Mads: Hej Sofie! Hvordan har du det? [1 seconds]

Sofie: Hej Mads! Jeg har det godt, tak. Og du? [1 seconds]

Mads: Jeg har det fint. Jeg tænker på ferie. [1 seconds]

Teacher: Now let's practice some key phrases from the conversation. [0.5 seconds]

Teacher: Tell your friend that you are thinking about a holiday. [5 seconds]
Man: Jeg tænker på ferie. [3 seconds]
Man: Jeg tænker på ferie. [3 seconds]
"""

LABELED = NAMED_SPEAKERS.replace("Mads:", "Man:").replace("Sofie:", "Woman:")


def test_named_speakers_are_reported():
    assert unknown_speaker_labels(NAMED_SPEAKERS) == ["Mads", "Sofie"]


def test_named_speakers_are_what_the_parser_drops():
    spoken = [text for voice, text, _ in parse_script(NAMED_SPEAKERS) if text]
    assert "Hej Sofie! Hvordan har du det?" not in spoken


def test_a_well_labeled_script_has_nothing_to_report():
    assert unknown_speaker_labels(LABELED) == []


def test_the_title_before_the_first_voice_line_is_not_a_speaker():
    script = "Holidays: Beach or Mountains?\n\n" + LABELED.split("\n", 1)[1]
    assert unknown_speaker_labels(script) == []


def test_a_colon_inside_a_voice_line_is_not_a_speaker():
    script = "Teacher: You will hear the word: [0.2 seconds]\nTeacherL2: hyggelig [0.5 seconds]"
    assert unknown_speaker_labels(script) == []


def test_a_bold_voice_label_is_spoken_not_reported():
    script = "Teacher: Listen. [1 seconds]\n**Woman:** Hej! [1 seconds]\n**Man**: Hej! [1 seconds]"
    assert unknown_speaker_labels(script) == []
    assert [voice for voice, _, _ in parse_script(script)] == ["teacher", "woman", "man"]


def test_a_bold_name_label_is_reported_without_its_stars():
    assert unknown_speaker_labels("Teacher: Listen.\n**Mads:** Hej!") == ["Mads"]


def test_named_speakers_before_any_voice_line_are_reported():
    script = (
        "A Title\n\nMads: Hej Sofie!\nSofie: Hej Mads!\nMads: Hvordan går det?\n"
        "Sofie: Godt!\nTeacher: Now practice. [1 seconds]"
    )
    assert unknown_speaker_labels(script) == ["Mads", "Sofie"]


def test_a_header_before_any_voice_line_is_not_a_speaker():
    script = "Here is your lesson.\nTopic: Ordering coffee\nLevel: A1\n\nTeacher: Listen. [1 seconds]\nMan: Hej!"
    assert unknown_speaker_labels(script) == []


def test_numbered_speakers_are_reported():
    assert unknown_speaker_labels("Teacher: Listen.\nMan 1: Hej!\nSpeaker 2: Hej!") == ["Man 1", "Speaker 2"]


def test_any_number_of_stars_around_a_label():
    script = "Teacher: Listen.\n*Woman:* Hej!\n***Man:*** Hej!\n*Mads:* Hej!"
    assert unknown_speaker_labels(script) == ["Mads"]
    assert [voice for voice, _, _ in parse_script(script)] == ["teacher", "woman", "man"]


def test_a_wrapped_line_with_a_time_is_not_a_speaker():
    script = "Teacher: Say that the train leaves at\nklokken 10:30. [5 seconds]\nMan: Toget kører klokken 10:30."
    assert unknown_speaker_labels(script) == []


def _generate(scripts):
    """generate_script_in_languages, with the model answering `scripts` in turn."""
    answers = iter(scripts)
    prompts = []

    def model(prompt, **kwargs):
        prompts.append(prompt)
        return next(answers), "model"

    with patch.object(script_generator, "generate_audio_lesson_script", model), patch.object(
        script_generator, "find_language_mismatches", lambda *a, **k: []
    ):
        result = script_generator.generate_script_in_languages(
            "PROMPT", target_language="da", source_language="en", context="test"
        )
    return result, prompts


def test_named_speakers_are_rewritten_with_a_note_naming_them():
    (script, _), prompts = _generate([NAMED_SPEAKERS, LABELED])
    assert script == LABELED
    assert prompts[0] == "PROMPT"
    assert "'Mads:'" in prompts[1] and "'Sofie:'" in prompts[1]


def test_named_speakers_every_time_are_refused():
    with pytest.raises(Exception, match="Mads"):
        _generate([NAMED_SPEAKERS] * script_generator.LANGUAGE_ATTEMPTS)


def test_synthesis_refuses_a_script_with_named_speakers():
    from zeeguu.core.audio_lessons.voice_synthesizer import VoiceSynthesizer

    synthesizer = object.__new__(VoiceSynthesizer)  # no TTS clients needed to refuse
    with pytest.raises(ValueError, match="Mads"):
        synthesizer._synthesize_script_to_file(NAMED_SPEAKERS, "/dev/null", "da", "en", variety=None)


def test_llm_service_defines_each_class_once():
    """A botched splice once left two UnifiedLLMService classes in the module;
    Python silently used the second."""
    import ast
    import zeeguu.core.llm_services.llm_service as module

    tree = ast.parse(open(module.__file__).read())
    names = [n.name for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))]
    assert len(names) == len(set(names)), [n for n in names if names.count(n) > 1]
