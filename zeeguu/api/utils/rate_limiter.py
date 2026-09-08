# Rate limiting utilities for security-sensitive endpoints
import flask
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Limit:
    """
    rate:  a flask-limiter rate string.
    key:   "ip" for endpoints reachable without a session, "session" for the
           ones behind @requires_session, where an IP bucket would put a whole
           class behind one school NAT into a single quota, and "target_email"
           for endpoints that act on an address named in the route.

           An endpoint may carry several limits with different keys: a tight
           one on what is being protected, and a looser per-IP backstop.
    count: "failures" charges the bucket only for requests the endpoint
           rejected. Successful logins are then free, which is what lets the
           ceiling be low enough to matter without a classroom ever reaching
           it: 60 students signing in correctly cost nothing at all.
    """

    rate: str
    key: str = "ip"
    count: str = "all"


RATE_LIMITS = {
    # Login. Charged only for rejected attempts, so a room full of people
    # signing in normally never touches this. What it caps is one host sitting
    # there guessing, which is the only thing an IP bucket can honestly cap:
    # anyone willing to rotate addresses walks around it regardless, and the
    # defence that actually stops them is a per-account limit (not yet here).
    "endpoints.get_session": Limit("100 per minute;1000 per hour", count="failures"),
    "endpoints.get_anon_session": Limit("100 per minute;1000 per hour", count="failures"),

    # Requesting a reset code. Deliberately answers "OK" even for addresses
    # that don't exist, so that it can't be used to enumerate users - which
    # means charging on failures would never charge anything at all, and the
    # limit would be decorative. Here the *successful* request is the costly
    # one: it puts real mail in someone's inbox on our SMTP bill.
    #
    # Keyed first on the address being mailed, because that inbox is what
    # needs protecting and the host doing the asking can move: an attacker
    # rotating IPs walks around any per-IP number, but cannot send a sixth
    # message this hour to someone who has already had five. Nobody legitimate
    # needs more, so there is no crowd to catch - a whole school forgetting
    # their passwords is still one request each. The per-IP limit stays on as
    # a backstop against spraying one message at each of many addresses.
    "endpoints.send_code": (
        Limit("5 per hour", key="target_email"),
        Limit("20 per minute;200 per hour"),
    ),

    # Submitting a code. A wrong code is a 400, so this caps guessing while a
    # legitimate reset costs nothing.
    "endpoints.reset_password": Limit("20 per minute;200 per hour", count="failures"),

    # Account creation. Invite codes are the primary protection against mass
    # bot registration; this is only a ceiling on how fast one host can try.
    # A whole school onboarding in one session has to fit under it.
    "endpoints.add_user": Limit("500 per hour"),
    "endpoints.add_basic_user": Limit("500 per hour"),
    "endpoints.add_anon_user": Limit("500 per hour"),

    # User search accepts a full email address as a search key. One lookup can
    # only confirm an address the searcher already typed, but without a ceiling
    # a script could sweep a wordlist to find which addresses have an account.
    # Per session, so one student's searching can't lock out the next desk.
    "endpoints.search_by_search_term": Limit("60 per minute;600 per hour", key="session"),
}


def _was_rejected(response):
    """Charge the bucket only when the endpoint turned the request away."""
    return response.status_code in (400, 401, 403, 404)


def _target_email_key():
    """
    Rate-limit key for endpoints that act on an address named in the route,
    so the limit protects the person on the receiving end rather than
    throttling whoever happens to be asking.
    """
    email = (flask.request.view_args or {}).get("email") or ""
    return f"email:{email.strip().lower()}"


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

    key_funcs = {
        "ip": get_remote_address,
        "session": _session_key,
        "target_email": _target_email_key,
    }

    missing = sorted(ep for ep in RATE_LIMITS if ep not in app.view_functions)
    if missing:
        # Skipping these quietly is what made the whole file decorative: the
        # config kept claiming that login was throttled while it wasn't.
        raise RuntimeError(
            f"Rate limits configured for unknown endpoints: {', '.join(missing)}. "
            "Endpoint names are '<blueprint>.<view function>' and this app's "
            "blueprint is named 'endpoints'."
        )

    for endpoint, limits in RATE_LIMITS.items():
        for limit in (limits,) if isinstance(limits, Limit) else limits:
            deduct_when = _was_rejected if limit.count == "failures" else None
            # The decorated function has to go back into the routing table.
            # Calling limiter.limit(...) for its side effect alone registers
            # the limit under a name that request dispatch never looks up,
            # which enforces nothing while still looking like a working call.
            app.view_functions[endpoint] = limiter.limit(
                limit.rate,
                key_func=key_funcs[limit.key],
                deduct_when=deduct_when,
            )(app.view_functions[endpoint])


def get_limiter():
    """Get the global limiter instance."""
    global limiter
    return limiter
