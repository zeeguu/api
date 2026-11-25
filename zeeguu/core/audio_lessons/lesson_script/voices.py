"""
The voices of a lesson script. Lowercase in all data; written as labels
("TeacherL2:") only at the start of a line of the written-out script.
"""

TEACHER = "teacher"  # the teacher, in the learner's own language
TEACHER_L2 = "teacherl2"  # the same teacher, saying words of the learned language
MAN = "man"
WOMAN = "woman"

TEACHERS = (TEACHER, TEACHER_L2)
PEOPLE = (MAN, WOMAN)  # the two people in the dialogue: the learner and the other person


def other_voice(learner):
    """The other person's voice: WOMAN for a learner who is MAN, and the other way round."""
    return WOMAN if learner == MAN else MAN


def label(voice):
    """How a voice is written at the start of a script line: "teacherl2" -> "TeacherL2"."""
    return "TeacherL2" if voice == TEACHER_L2 else voice.capitalize()
