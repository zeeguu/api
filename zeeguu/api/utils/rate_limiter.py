# Rate limiting utilities for security-sensitive endpoints
import flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Global limiter instance - initialized in create_app()
limiter = None

# Endpoint names are "<blueprint>.<view function>". Every route below lives on
# the single blueprint declared in zeeguu/api/endpoints/__init__.py, which is
# *named* "endpoints" even though the variable holding it is called `api`. Keys
# written as "api.*" resolve to nothing, which is how every limit in this file
# sat inert from the day it was added; apply_rate_limits_to_endpoints now
# refuses to start rather than let that happen again.

# Limited per IP: nobody has a session yet at this point.
RATE_LIMITS = {
    # Login endpoints - prevent brute force attacks
    "endpoints.get_session": "5 per minute;20 per hour",
    "endpoints.get_anon_session": "5 per minute;20 per hour",

    # Password reset endpoints - prevent abuse
    "endpoints.send_code": "3 per minute;10 per hour",
    "endpoints.reset_password": "5 per minute;20 per hour",

    # Account creation - higher limits to allow classroom signups (shared IP via NAT)
    # Invite codes provide the primary protection against mass bot registration
    "endpoints.add_user": "100 per hour",
    "endpoints.add_basic_user": "100 per hour",
    "endpoints.add_anon_user": "200 per hour",
}

# Limited per session instead of per IP. These endpoints sit behind
# @requires_session, so an IP bucket would put a whole classroom behind one
# school NAT into a single quota — and "everyone add each other now" is a
# normal lesson, not an attack.
PER_SESSION_RATE_LIMITS = {
    # User search accepts a full email address as a search key. One lookup can
    # only confirm an address the searcher already typed, but without a ceiling
    # a script could still sweep a wordlist to find out which addresses have an
    # account. This is invisible to someone typing in the search box.
    "endpoints.search_by_search_term": "60 per minute;600 per hour",
}


def _session_key():
    """
    Rate-limit key for endpoints that require a session.

    Reads the session uuid the same way requires_session does, but does not
    validate it: an invalid uuid is going to be rejected by the view anyway,
    and for bucketing purposes any opaque per-account token will do. Falls
    back to the IP when no session is present.
    """
    session_uuid = flask.request.args.get("session") or flask.request.cookies.get("chocolatechip")
    return f"session:{session_uuid}" if session_uuid else get_remote_address()


def init_limiter(app, enabled=True):
    """
    Initialize the rate limiter with the Flask app.
    Call this from create_app() after the configuration has been loaded, so
    that RATELIMIT_STORAGE_URI is actually visible here.

    `enabled=False` (used by the test suite) keeps the limiter wired up but
    stops it counting, so that hundreds of tests logging in as the same user
    from the same address don't trip the login limit.
    """
    global limiter

    # Use Redis if available (for distributed rate limiting), otherwise use in-memory storage
    storage_uri = app.config.get("RATELIMIT_STORAGE_URI", "memory://")

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        storage_uri=storage_uri,
        # No default limits - we'll apply specific limits to sensitive endpoints
        default_limits=[],
        # Return standard HTTP 429 for rate-limited requests
        strategy="fixed-window",
    )
    limiter.enabled = enabled

    # Configure headers to inform clients about rate limits
    app.config.setdefault("RATELIMIT_HEADERS_ENABLED", True)

    return limiter


def apply_rate_limits_to_endpoints(app):
    """
    Apply rate limits to security-sensitive endpoints after blueprint registration.
    Call this from create_app() AFTER registering blueprints.
    """
    global limiter
    if limiter is None:
        return

    all_limits = {
        **{ep: (limit, get_remote_address) for ep, limit in RATE_LIMITS.items()},
        **{ep: (limit, _session_key) for ep, limit in PER_SESSION_RATE_LIMITS.items()},
    }

    missing = sorted(ep for ep in all_limits if ep not in app.view_functions)
    if missing:
        # Skipping these quietly is what made the whole file decorative: the
        # config kept claiming that login was throttled while it wasn't.
        raise RuntimeError(
            f"Rate limits configured for unknown endpoints: {', '.join(missing)}. "
            "Endpoint names are '<blueprint>.<view function>' and this app's "
            "blueprint is named 'endpoints'."
        )

    for endpoint, (limit_string, key_func) in all_limits.items():
        # The decorated function has to go back into the routing table. Calling
        # limiter.limit(...) for its side effect alone registers the limit
        # under a name that request dispatch never looks up, which enforces
        # nothing while still looking like a working call.
        app.view_functions[endpoint] = limiter.limit(limit_string, key_func=key_func)(
            app.view_functions[endpoint]
        )


def get_limiter():
    """Get the global limiter instance."""
    global limiter
    return limiter
