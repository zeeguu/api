"""
Unit tests for the audio-lesson script language check.

No Flask app context or DB — the validator works on the raw script text.
"""

from zeeguu.core.audio_lessons.script_language_validator import (
    find_language_mismatches,
)

DANISH_LESSON = """
Teacher: In the following conversation you will hear the word: [0.2 seconds]
TeacherL2: hyggelig [0.5 seconds]
Teacher: with the meaning [0.2 seconds]
Teacher: cosy. [1 seconds]
Man: Hej Mette, skal vi mødes i aften? [1 seconds]
Woman: Ja, det lyder rigtig hyggeligt. Hvor skal vi mødes? [1 seconds]
Man: Vi kan mødes på den lille café ved havnen. [1 seconds]
Woman: Perfekt. Jeg synes altid at der er så hyggeligt der. [1 seconds]
Man: Vi kan sidde udenfor hvis vejret er godt. [1 seconds]
Woman: Det håber jeg. Jeg tager min søster med, hvis det er i orden. [1 seconds]
Man: Selvfølgelig, jo flere jo bedre. Vi ses klokken syv. [1 seconds]
Woman: Vi ses. Jeg glæder mig rigtig meget til i aften. [1 seconds]
Teacher: Let's practice some key phrases from the conversation. [1 seconds]
Teacher: Say, that sounds really cosy. [5 seconds]
Man: Det lyder rigtig hyggeligt. [3 seconds]
Teacher: Ask, where shall we meet? [5 seconds]
Man: Hvor skal vi mødes? [3 seconds]
Teacher: Now say, I am really looking forward to tonight. [5 seconds]
Man: Jeg glæder mig rigtig meget til i aften. [3 seconds]
"""

# The failure we're guarding against: a "Danish" lesson written entirely in English.
DANISH_LESSON_GONE_ENGLISH = """
Teacher: In the following conversation you will hear the word: [0.2 seconds]
TeacherL2: cosy [0.5 seconds]
Teacher: with the meaning [0.2 seconds]
Teacher: cosy. [1 seconds]
Man: Hi Mette, shall we meet tonight? [1 seconds]
Woman: Yes, that sounds really cosy. Where shall we meet? [1 seconds]
Man: We can meet at the little cafe by the harbour. [1 seconds]
Woman: Perfect. I always think it is so cosy there. [1 seconds]
Man: We can sit outside if the weather is good. [1 seconds]
Woman: I hope so. I will bring my sister if that is all right. [1 seconds]
Man: Of course, the more the merrier. See you at seven. [1 seconds]
Woman: See you. I am really looking forward to tonight. [1 seconds]
Teacher: Let's practice some key phrases from the conversation. [1 seconds]
Teacher: Say, that sounds really cosy. [5 seconds]
Man: That sounds really cosy. [3 seconds]
Teacher: Ask, where shall we meet? [5 seconds]
Man: Where shall we meet? [3 seconds]
"""

# The inverse: the teacher explains in the language being learned instead of the
# learner's native language.
GERMAN_LESSON_TEACHER_NOT_IN_ROMANIAN = """
Teacher: In der folgenden Unterhaltung hören Sie das Wort: [0.2 seconds]
TeacherL2: gemütlich [0.5 seconds]
Teacher: Das bedeutet, dass ein Ort angenehm und warm ist. [1 seconds]
Man: Hallo Anna, wollen wir heute Abend etwas trinken gehen? [1 seconds]
Woman: Ja, gerne. Wo möchtest du dich denn treffen? [1 seconds]
Man: Es gibt ein sehr gemütliches Café unten am Hafen. [1 seconds]
Woman: Das klingt gut. Ich komme um sieben Uhr dorthin. [1 seconds]
Man: Wunderbar, ich freue mich sehr auf heute Abend. [1 seconds]
Woman: Ich mich auch. Bis später dann, mein lieber Freund. [1 seconds]
Teacher: Lassen Sie uns jetzt einige wichtige Sätze üben. [1 seconds]
Teacher: Sagen Sie, wo möchtest du dich treffen? [5 seconds]
Man: Wo möchtest du dich treffen? [3 seconds]
Teacher: Fragen Sie, wollen wir heute Abend etwas trinken gehen? [5 seconds]
Man: Wollen wir heute Abend etwas trinken gehen? [3 seconds]
"""

GERMAN_LESSON_WITH_ROMANIAN_TEACHER = """
Teacher: În următoarea conversație veți auzi cuvântul: [0.2 seconds]
TeacherL2: gemütlich [0.5 seconds]
Teacher: cu sensul de confortabil și primitor. [1 seconds]
Man: Hallo Anna, wollen wir heute Abend etwas trinken gehen? [1 seconds]
Woman: Ja, gerne. Wo möchtest du dich denn treffen? [1 seconds]
Man: Es gibt ein sehr gemütliches Café unten am Hafen. [1 seconds]
Woman: Das klingt gut. Ich komme um sieben Uhr dorthin. [1 seconds]
Man: Wunderbar, ich freue mich sehr auf heute Abend. [1 seconds]
Woman: Ich mich auch. Bis später dann, mein lieber Freund. [1 seconds]
Teacher: Acum să exersăm câteva expresii din conversație. [1 seconds]
Teacher: Spuneți, unde vrei să ne întâlnim diseară? [5 seconds]
Man: Wo möchtest du dich treffen? [3 seconds]
Teacher: Întrebați, mergem să bem ceva diseară? [5 seconds]
Man: Wollen wir heute Abend etwas trinken gehen? [3 seconds]
"""


def test_correct_danish_lesson_passes():
    assert find_language_mismatches(DANISH_LESSON, "da", "en") == []


def test_danish_lesson_written_in_english_is_caught():
    mismatches = find_language_mismatches(DANISH_LESSON_GONE_ENGLISH, "da", "en")
    assert len(mismatches) == 1
    assert mismatches[0].voices == "Man/Woman/TeacherL2"
    assert mismatches[0].expected == "da"
    assert mismatches[0].detected == "en"


def test_teacher_speaking_the_learned_language_is_caught():
    mismatches = find_language_mismatches(
        GERMAN_LESSON_TEACHER_NOT_IN_ROMANIAN, "de", "ro"
    )
    assert [m.voices for m in mismatches] == ["Teacher"]
    assert mismatches[0].expected == "ro"
    assert mismatches[0].detected == "de"


def test_correct_german_lesson_with_romanian_teacher_passes():
    assert find_language_mismatches(GERMAN_LESSON_WITH_ROMANIAN_TEACHER, "de", "ro") == []


def test_scandinavian_neighbours_are_not_flagged_against_each_other():
    # langdetect regularly reads short Danish sentences as Norwegian or Swedish;
    # that must not fail a lesson.
    assert find_language_mismatches(DANISH_LESSON, "no", "en") == []


def test_language_langdetect_cannot_check_is_skipped():
    # Kurdish has no langdetect profile — we can't check it, so we don't block on it.
    assert find_language_mismatches(DANISH_LESSON_GONE_ENGLISH, "ku", "ku") == []


def test_too_short_to_judge_is_not_flagged():
    assert find_language_mismatches("Man: Hej. [1 seconds]", "da", "en") == []
