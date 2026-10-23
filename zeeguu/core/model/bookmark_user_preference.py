class UserWordExPreference(object):
    # Defines user preference to use word in exercises
    BAD_TRANSLATION = -100  # bad translation - permanent exclusion
    DECLARED_KNOWN = -6  # freshly declared known, erodes with re-translations (-6 → -4 → -2 → 0)
    DONT_USE_IN_EXERCISES = -1  # other reasons - permanent exclusion
    NO_PREFERENCE = 0
    USE_IN_EXERCISES = 1  # user explicitly opted in (overrides quality checks)

    @classmethod
    def of(cls, preference):
        """
        The preference as an int. user_word.user_preference is TEXT in prod
        (the model says Integer), so it can come back as "1", and "1" != 1.
        """
        try:
            return int(preference or cls.NO_PREFERENCE)
        except (ValueError, TypeError):
            return cls.NO_PREFERENCE

    @classmethod
    def is_declared_known(cls, preference):
        """Declared known uses even negative values: -6, -4, -2"""
        pref = cls.of(preference)
        return pref <= -2 and pref >= -6 and pref % 2 == 0
