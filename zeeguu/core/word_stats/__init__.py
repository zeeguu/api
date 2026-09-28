from wordstats import LanguageInfo, Word


def lang_info(lang_code):
    """The language's wordstats store, shared with Word.stats(): one cache, so
    the preload in create_app serves both, and a language is never held twice."""
    if lang_code not in Word.stats_dict:
        Word.stats_dict[lang_code] = LanguageInfo.load(lang_code)
    return Word.stats_dict[lang_code]
