"""
The model writes roles, not voices: "Learner:" and "Other:". Code knows which
voice (Man or Woman) the learner has, and relabels the lines before anything
else reads them; the dialogue shown to the model is relabeled the other way.
"""

import re

_ROLE_LABEL = re.compile(r"^(\s*)\**\s*(Learner|Other)\s*\**\s*:\s*\**\s*", re.IGNORECASE)
_VOICE_LABEL = re.compile(r"^(\s*)(Man|Woman)\s*:", re.IGNORECASE)


def other_voice(learner):
    """The other person's voice: "woman" for a learner who is "man", and the other way round."""
    return "woman" if learner == "man" else "man"


def roles_to_voices(script, learner):
    """The script with "Learner:" and "Other:" relabeled as the voices they are."""
    voices = {"learner": learner.capitalize(), "other": other_voice(learner).capitalize()}
    return "\n".join(
        _ROLE_LABEL.sub(lambda m: f"{m.group(1)}{voices[m.group(2).lower()]}: ", line)
        for line in (script or "").split("\n")
    )


def voices_to_roles(script, learner):
    """A dialogue with its Man/Woman lines relabeled "Learner:" and "Other:", for the prompt."""
    def role(m):
        return f"{m.group(1)}{'Learner' if m.group(2).lower() == learner else 'Other'}:"
    return "\n".join(_VOICE_LABEL.sub(role, line) for line in (script or "").split("\n"))
