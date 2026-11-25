"""
A0 lesson scripts: written by the model with markers, expanded by code.

The model writes each thing once and marks what kind of line it is; code adds
the repetitions and every pause. So pace and repetition are exactly what the
learner's tuning says (lesson_tuning.prompt_values), rather than what the
model made of "about 5 recalls" and "[4 seconds]". Design: docs
future-work/a0-lesson-script-functions.md.

    The model writes with roles, not voices: "Learner:" and "Other:". Code
    knows which voice (Man or Woman) the learner has, and relabels the lines
    (roles.roles_to_voices) before anything else reads them. Teacher lines
    are in the learner's own language and carry no marker. The learned
    language is marked by what the learner does with it:

    Learner: Kaffe. [drill]                  a word to SAY: slow once, then at
                                             normal speed, with time to repeat it
    Other: Hvad skal det være? [understand]  a line only to UNDERSTAND: slow
                                             once, then at normal speed
    Teacher: How do you say coffee?          a QUESTION: the Teacher asks
    Learner: En kaffe. [answer]              the answer, said twice

    An EXCHANGE: the Teacher sets it up, the Other person speaks, and the
    learner replies to them, as in a real conversation:

    Teacher: The shopkeeper tells you the price. Say okay, and ask for a ticket.
    Other: Den koster tolv kroner.           the PROMPT
    Learner: Okay. En billet, tak. [answer]

    The line right before an [answer] is its PROMPT: the Teacher's question,
    or the Other person's line in an exchange. Only a prompt gets the time to
    answer; every other line is followed by one second. There is no marker
    for it: a marker the model had to place ([ask]) was put in the wrong place
    in three different ways, and an answer placed after what it answers is
    the one thing the model gets right every time.

    [dialogue]                             this lesson's dialogue

The modules, in the order a script goes through them:

    roles           Learner/Other <-> Man/Woman
    markers         the line patterns the others share
    spoken_line     SpokenLine, one line of the expanded script; «chevrons»
    time_to_answer  how long the silence after a prompt is
    expand          the marked script -> the expanded script
    challenges      what the learner answered, kept for review
    review          how a review of earlier lessons is said, and where it goes

The expanded script is what is stored and synthesized: nothing downstream
knows about markers. What to review is chosen elsewhere (lesson_review.py).
"""
