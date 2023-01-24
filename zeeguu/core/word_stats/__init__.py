from wordstats import LanguageInfo

lang_cache = {}


def lang_info(lang_code):
    if not lang_cache.get(lang_code):
        print(f"loading word stats for {lang_code}")
        lang_cache[lang_code] = LanguageInfo.load(lang_code)
    return lang_cache[lang_code]


# lang_info("da")
# lang_info("de")
# lang_info("nl")
