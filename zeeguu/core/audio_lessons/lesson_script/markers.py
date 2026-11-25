"""The line patterns that expand and challenges both read."""

import re

# A voice line, once roles are voices: "Woman: En kaffe. [answer]".
VOICE_LINE = re.compile(r"^(Teacher|TeacherL2|Man|Woman):\s*(.*)$")
# The marker at the end of a line.
LINE_MARKER = re.compile(r"\s*\[(drill|answer|understand)\]\s*$", re.IGNORECASE)
# The one marker that stands on a line of its own: where the dialogue is played.
DIALOGUE_LINE = re.compile(r"^\[dialogue\]$", re.IGNORECASE)
