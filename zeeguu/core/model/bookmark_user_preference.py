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
        if preference is None:
            return False
        # Handle string values from database (legacy data)
        try:
            pref = int(preference)
        except (ValueError, TypeError):
            return False
        return pref <= -2 and pref >= -6 and pref % 2 == 0
