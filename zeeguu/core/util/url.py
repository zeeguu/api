from urllib.parse import urlparse, urlunparse

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
    """Drop known tracking query params (gaa_*, utm_*, fbclid, ...).

    Surgical by design: operates on the raw query string and only the
    matched ``key=value`` segments are removed. Surviving params keep their
    exact original encoding, and a URL with no tracking params is returned
    byte-for-byte unchanged. This matters because the result is used as a DB
    key (url.path) and is reconstructed into URLs served back to the client
    (image/CDN URLs, articleURL=... wrappers) — re-encoding would corrupt
    signed values and break lookups against already-stored rows.

    Leaves non-URL strings untouched.
    """
    if not url or "://" not in url:
        return url

    parsed = urlparse(url)
    if not parsed.query:
        return url

    # Split the *raw* query (no decode) and drop only the tracking segments.
    segments = parsed.query.split("&")
    kept = [s for s in segments if not _is_tracking_param(s.split("=", 1)[0])]
    if len(kept) == len(segments):
        return url  # nothing stripped — don't touch the original encoding

    return urlunparse(parsed._replace(query="&".join(kept)))
