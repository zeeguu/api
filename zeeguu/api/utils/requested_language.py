def requested_language(user, lang_code):
    """Pick the language an endpoint should act on. Prefer an explicit code
    from the client (avoids races where the user just switched language and
    the server's learned_language hasn't caught up); fall back to
    user.learned_language for clients that don't send it yet.
    Returns the Language object, or None if the code is unknown."""
    from sqlalchemy.orm.exc import NoResultFound
    from zeeguu.core.model import Language

    code = (lang_code or "").strip()
    if not code:
        return user.learned_language
    if code == "cn":
        code = "zh-CN"
    try:
        return Language.find(code)
    except NoResultFound:
        return None
