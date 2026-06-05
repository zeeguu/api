from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

"""
    Helpers for cleaning up URLs before we store them.

    Some publishers (e.g. bt.dk via Google Discover / "Subscribe with Google")
    append long signed access tokens as query params: gaa_at, gaa_n, gaa_ts,
    gaa_sig. Together with the usual utm_*/fbclid/gclid analytics cruft these
    can push a URL well past 255 chars, which is the size of e.g. the
    user_activity_data.value column.
"""

# Param names (or prefixes) that carry no meaning for us and only bloat the URL.
_TRACKING_PARAM_PREFIXES = (
    "gaa_",  # Google Article Access tokens (Subscribe with Google / Discover)
    "utm_",  # analytics campaign tags
)
_TRACKING_PARAM_NAMES = {
    "fbclid",  # Facebook click id
    "gclid",  # Google Ads click id
    "_ga",  # Google Analytics
}


def _is_tracking_param(name: str) -> bool:
    return name in _TRACKING_PARAM_NAMES or name.startswith(_TRACKING_PARAM_PREFIXES)


def remove_tracking_query_params(url: str) -> str:
    """Drop known tracking query params, preserving everything else.

    Leaves non-URL strings untouched.
    """
    if not url or "://" not in url:
        return url

    parsed = urlparse(url)
    kept = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if not _is_tracking_param(k)]

    return urlunparse(parsed._replace(query=urlencode(kept)))
