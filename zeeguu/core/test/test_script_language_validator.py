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

# Abridged from production dialogue 235 (Danish, A2, generated 2026-08-16). The
# opening conversation — the part a learner hears first, and for two solid minutes —
# is entirely English; the practice phrases after it are correctly Danish. The whole
# script scores 71% Danish, so checking it as one blob passes it.
DANISH_LESSON_ENGLISH_DIALOGUE_DANISH_PRACTICE = """
Teacher: Today, we will listen to a conversation about strength training. [0.5 seconds]
Man: I think we should do strength training at home. It is easy and cheap. [1 seconds]
Woman: That is a good idea. But what exercises can we do here? [1 seconds]
Man: We can do push-ups and squats. They are very good for the body. [1 seconds]
Woman: I like squats. But push-ups are hard for me. [1 seconds]
Man: That is okay. You can start with a few and do more later. [1 seconds]
Woman: How many times a week should we train? [1 seconds]
Man: I think three times a week is good for us. [1 seconds]
Woman: Should we use weights too? [1 seconds]
Man: Yes, we can use small weights for our arms. [1 seconds]
Woman: I do not have weights at home. Can we buy some? [1 seconds]
Man: Yes, we can buy two small weights at the sports shop. [1 seconds]
Woman: Great. And what about rest days? [1 seconds]
Man: Rest days are important. Our muscles need time to grow stronger. [1 seconds]
Woman: That makes sense. Let us start on Monday then. [1 seconds]
Man: Perfect. We will train together and help each other. [1 seconds]
Teacher: Let us practice some key phrases from the conversation. [1 seconds]
Teacher: Tell your partner that you like squats. [5 seconds]
Man: Jeg kan godt lide squats. [3 seconds]
Teacher: Ask your partner how many times a week you should train. [5 seconds]
Woman: Hvor mange gange om ugen skal vi træne? [3 seconds]
Teacher: Say that you think three times a week is good for you. [5 seconds]
Man: Jeg synes, tre gange om ugen er godt for os. [3 seconds]
Teacher: Tell your partner that push-ups are hard for you. [5 seconds]
Woman: Armstrækninger er svære for mig. [3 seconds]
Teacher: Ask your partner if you should use weights. [5 seconds]
Man: Skal vi bruge vægte? [3 seconds]
Teacher: Say that rest days are important for your muscles. [5 seconds]
Woman: Hviledage er vigtige for vores muskler. [3 seconds]
Teacher: Tell your partner that you can start with a few exercises. [5 seconds]
Man: Jeg kan starte med et par øvelser. [3 seconds]
Teacher: Ask your partner if you can buy small weights at the shop. [5 seconds]
Woman: Kan vi købe små vægte i butikken? [3 seconds]
Teacher: Tell your friend that you want to get stronger. [5 seconds]
Man: Jeg vil gerne blive stærkere. [3 seconds]
Teacher: Ask your friend if they have a training mat. [5 seconds]
Woman: Har du en træningsmåtte? [3 seconds]
"""

# Abridged from production lesson 1043 (English course, Ukrainian-speaking teacher).
# This script is CORRECT. The teacher's lines are bilingual by design — a Ukrainian
# lead-in plus the exact English sentence the listener must produce — so the teacher
# reads as English by volume. Checking the teacher would fail a good lesson.
ENGLISH_LESSON_WITH_UKRAINIAN_TEACHER = """
Teacher: У наступній розмові ви почуєте слово: [0.2 seconds]
TeacherL2: says [0.5 seconds]
Teacher: зі значенням говорить. [1 seconds]
Man: The news says it will rain tomorrow evening. [1 seconds]
Woman: Really? My weather app says something completely different. [1 seconds]
Man: It says the temperature will drop too, quite sharply. [1 seconds]
Woman: Well, the forecast is never very accurate around here. [1 seconds]
Man: True. My friend always says the news is more accurate. [1 seconds]
Woman: Maybe. What does your app say about the weekend? [1 seconds]
Teacher: Давайте попрактикуємо ключові фрази. [1 seconds]
Teacher: Скажіть, the news says it will rain tomorrow. [5 seconds]
Man: The news says it will rain tomorrow. [3 seconds]
Teacher: Спробуйте, it says the temperature will drop too. [5 seconds]
Man: It says the temperature will drop too. [3 seconds]
Teacher: Тепер скажіть, my weather app says something different. [5 seconds]
Man: My weather app says something different. [3 seconds]
Teacher: Запитайте, what does your app say? [5 seconds]
Man: What does your app say? [3 seconds]
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
    assert mismatches[0].label == "Man/Woman/TeacherL2"
    assert mismatches[0].expected == "da"
    assert mismatches[0].detected == "en"


def test_english_dialogue_followed_by_danish_practice_is_caught():
    # Production dialogue 235: the half a learner hears first was English. Checking
    # the target-language lines as one blob scores 71% Danish and passes, which is
    # how this reached a real daily lesson.
    mismatches = find_language_mismatches(
        DANISH_LESSON_ENGLISH_DIALOGUE_DANISH_PRACTICE, "da", "en"
    )
    assert len(mismatches) == 1
    assert mismatches[0].expected == "da"
    assert mismatches[0].detected == "en"


def test_bilingual_teacher_lines_do_not_fail_a_good_lesson():
    # Production lesson 1043. The teacher's challenges embed the English target
    # sentence, so the teacher's lines read as English even though the lesson is
    # correct. Only the target-language voices are judged.
    assert find_language_mismatches(ENGLISH_LESSON_WITH_UKRAINIAN_TEACHER, "en", "uk") == []


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
