def parse_optional_int(value):
    """
    Parse a form/JSON field that may be missing, an empty string, or an int.

    Returns None for None/empty input, and silently None for malformed input
    rather than 400-ing the whole request — used for hints (e.g. tap position)
    where a missing or junk value just disables an optimization.
    """
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
