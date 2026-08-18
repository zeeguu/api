"""
Zeeguu language codes, and the names that go with them.

A leaf: everything that needs to turn a code into something a human (or an LLM)
reads goes through here, without importing the ORM to load.
"""


def language_name(zeeguu_code: str) -> str:
    """
    'da' -> 'Danish'. Falls back to the code itself for anything unknown.

    The names live on the Language model, which is imported lazily so that this
    module stays usable from anywhere — including the modules the model itself
    depends on.
    """
    try:
        from zeeguu.core.model.language import Language

        return Language.LANGUAGE_NAMES.get(zeeguu_code, zeeguu_code)
    except Exception:
        return zeeguu_code
