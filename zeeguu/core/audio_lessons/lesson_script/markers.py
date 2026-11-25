"""The line patterns that expand and challenges both read."""

import re

# A voice line, once roles are voices: "Woman: En kaffe. [answer]".
VOICE_LINE = re.compile(r"^(Teacher|TeacherL2|Man|Woman):\s*(.*)$")
# The marker at the end of a line.
LINE_MARKER = re.compile(r"\s*\[(drill|answer|understand)\]\s*$", re.IGNORECASE)
# The markers that stand on a line of their own: where the dialogue is played,
# and where the review of earlier lessons goes.
DIALOGUE_MARKER = re.compile(r"^\[dialogue\]$", re.IGNORECASE)
REVIEW_MARKER = re.compile(r"^\[review\]$", re.IGNORECASE)
REVIEW_SLOT = "[review]"  # kept in the expanded lines until with_review fills it
