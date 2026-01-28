class UserWordExPreference(object):
    # Defines user preference to use word in exercises
    BAD_TRANSLATION = -100  # bad translation - permanent exclusion
    DECLARED_KNOWN = -6  # freshly declared known, erodes with re-translations (-6 → -4 → -2 → 0)
    DONT_USE_IN_EXERCISES = -1  # other reasons - permanent exclusion
    NO_PREFERENCE = 0
    USE_IN_EXERCISES = 1  # user explicitly opted in (overrides quality checks)

    @classmethod
    def is_declared_known(cls, preference):
        """Declared known uses even negative values: -6, -4, -2"""
        return (
            preference is not None
            and preference <= -2
            and preference >= -6
            and preference % 2 == 0
        )
