"""
Whether a user word is studied comes from two columns (roadmap 0b, 25 Oct
2026). They replace user_word.user_preference, one number that mixed the
learner's choice, a countdown and validator writes, so a validator fix could
pass for the learner opting in (#895).

- study_choice: what the learner chose. Only learner actions write it.
- unfit_reason: why the system keeps the word out. None when it may be studied.

The learner doesn't overrule the system: a STUDY choice lifts only the
LIFTABLE reasons, the quality heuristics the "+" button exists for.
"""


class StudyChoice:
    STUDY = "study"
    SKIP = "skip"
    KNOWN = "known"  # whether it still is, is for word knowledge to tell

    ALL = (STUDY, SKIP, KNOWN)


class UnfitReason:
    # Quality heuristics (negative_qualities), worked out again at every
    # update_fit_for_study
    RARE_FOR_BEGINNER = "rare_for_beginner"
    SAME_AS_TRANSLATION = "same_as_translation"
    TOO_SHORT = "too_short"
    TOO_MANY_WORDS = "too_many_words"
    ARBITRARY_MULTI_WORD = "arbitrary_multi_word"
    BAD_CONTEXTS = "bad_contexts"
    # Also worked out, but exercises can't show it at all
    SEPARATED_MWE = "separated_mwe"

    # Set when something happened; the next update_fit_for_study (a new
    # look-up, a star) judges the word again
    VALIDATOR_GAVE_UP = "validator_gave_up"
    NO_USABLE_CONTEXT = "no_usable_context"

    # Verdicts that stay until the pair changes
    VALIDATOR_INVALID = "validator_invalid"
    REPLACED_BY_FIX = "replaced_by_fix"
    DUPLICATE_MEANING = "duplicate_meaning"

    ALL = (
        RARE_FOR_BEGINNER, SAME_AS_TRANSLATION, TOO_SHORT, TOO_MANY_WORDS,
        ARBITRARY_MULTI_WORD, BAD_CONTEXTS, SEPARATED_MWE,
        VALIDATOR_GAVE_UP, NO_USABLE_CONTEXT,
        VALIDATOR_INVALID, REPLACED_BY_FIX, DUPLICATE_MEANING,
    )
    LIFTABLE = {
        RARE_FOR_BEGINNER, SAME_AS_TRANSLATION, TOO_SHORT, TOO_MANY_WORDS,
        ARBITRARY_MULTI_WORD, BAD_CONTEXTS,
    }
    STICKY = {VALIDATOR_INVALID, REPLACED_BY_FIX, DUPLICATE_MEANING}
