from zeeguu.core.audio_lessons.script_parser import DialogueLine, dialogue_lines

A0_SCRIPT = """Teacher: You are at a bus station. You are the woman.
[1 seconds]
Woman: Hej! Jeg skal have en billet, tak. [1 seconds]
Man: Hvor skal du hen? [1 seconds]
Woman: Til centrum. [slow] [1 seconds]
Teacher: How do you say "hello"? [5 seconds]
Woman: Hej. [3 seconds]
Woman: Hej. [3 seconds]
"""


def test_the_dialogue_is_the_first_run_of_man_and_woman_lines():
    assert dialogue_lines(A0_SCRIPT) == [
        DialogueLine("Woman", "Hej! Jeg skal have en billet, tak."),
        DialogueLine("Man", "Hvor skal du hen?"),
        DialogueLine("Woman", "Til centrum."),
    ]


def test_a_single_line_before_the_real_dialogue_is_skipped():
    # Lesson 529 in production: the model started the dialogue, had the
    # Teacher interrupt it, then played the real one.
    script = """Teacher: You are at a bus station.
Man: Hej! Hvad skal du have? [1 seconds]
Teacher: Sorry, that is not the conversation. Listen to the real one.
Woman: Hej! Jeg skal have en billet, tak. [1 seconds]
Man: Selvfølgelig. [1 seconds]
Teacher: Now a new word.
"""
    assert [line.speaker for line in dialogue_lines(script)] == ["Woman", "Man"]


def test_a_dialogue_running_to_the_end_of_the_script():
    assert len(dialogue_lines("Teacher: Listen.\nMan: Hej.\nWoman: Hej.")) == 2


def test_no_dialogue():
    assert dialogue_lines("Teacher: Hello.\nMan: Hej.\nTeacher: Bye.") == []


def test_a_line_left_empty_by_its_markers_is_skipped():
    script = "Teacher: Listen.\nMan: Hej! [1 seconds]\nWoman: [1 seconds]\nWoman: Hej."
    assert dialogue_lines(script) == [DialogueLine("Man", "Hej!"), DialogueLine("Woman", "Hej.")]


def test_a_challenge_answer_is_not_a_dialogue():
    script = """Teacher: Ask for the bill. [5 seconds]
Man: Regningen, tak. [3 seconds]
Man: Regningen, tak. [3 seconds]
Teacher: Bye.
"""
    assert dialogue_lines(script) == []


def test_a_dialogue_labelled_with_names_is_not_read():
    # Dialogue 525: the dialogue went unsaid, only the drills were voiced.
    script = """Teacher: Listen to Mads and Sofie.
Mads: Hej Sofie!
Sofie: Hej Mads!
Teacher: How do you say hello? [5 seconds]
Man: Hej. [3 seconds]
Woman: Hej. [3 seconds]
"""
    assert dialogue_lines(script) == []
