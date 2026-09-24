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

    def __post_init__(self):
        # A misspelt count would fall through to charging every request, which
        # is the same species of silent misconfiguration this whole file exists
        # to stop. (A misspelt key already fails loudly, as a KeyError.)
        if self.count not in ("all", "failures"):
            raise ValueError(f"unknown count {self.count!r}: expected 'all' or 'failures'")


RATE_LIMITS = {
    # Login. Charged only for rejected attempts, so signing in normally is
    # free. The per-account limit is the one doing the work: it counts failures
    # against the account being guessed at, so rotating IPs -- which defeats any
    # per-IP number -- buys an attacker nothing. Ten wrong passwords per quarter
    # hour is more than a person who has forgotten theirs will use before
    # reaching for the reset link, and useless to anybody guessing.
    #
    # That is also what lets the IP ceiling be generous. A class of thirty
    # shares one school NAT, and once a bucket is spent flask-limiter turns away
    # every request on that key -- including the students typing the right
    # password. So an IP number tight enough to matter would lock the room out,
    # and the room is not what needs stopping. It stays only as a backstop
    # against one host spraying attempts across many accounts at once.
    "endpoints.get_session": (
        Limit("10 per 15 minutes", key="target_account", count="failures"),
        Limit("300 per minute;3000 per hour", count="failures"),
    ),
    "endpoints.get_anon_session": (
        Limit("10 per 15 minutes", key="target_account", count="failures"),
        Limit("300 per minute;3000 per hour", count="failures"),
    ),

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
    # a backstop against spraying one message at each of many addresses. It has
    # to clear a whole class clicking "forgot my password" in the same minute on
    # one school NAT, which 20 a minute would not: ten of thirty students would
    # be turned away.
    "endpoints.send_code": (
        Limit("5 per hour", key="target_email"),
        Limit("100 per minute;600 per hour"),
    ),

    # Submitting a code. A wrong code is a 400, so a legitimate reset costs
    # nothing. Per account for the same reason as login -- that is what stops
    # someone working through the code space for one address, and it leaves the
    # IP ceiling free to clear the class that just requested thirty codes and is
    # now typing them in, some of them wrongly.
    "endpoints.reset_password": (
        Limit("10 per hour", key="target_email", count="failures"),
        Limit("100 per minute;600 per hour", count="failures"),
    ),

    # Account creation. A whole school onboarding at once has to fit under
    # this, which is why it is generous: invite codes, not this limit, are the
    # primary protection against mass bot registration.
    "endpoints.add_user": Limit("500 per hour"),
    "endpoints.add_basic_user": Limit("500 per hour"),

    # Except here. add_anon_user passes its invite_code straight to
    # User.create_anonymous, which accepts it as an optional argument and never
    # validates it - so this is the one creation path with no second line of
    # defence, and its ceiling is the whole of it. Anonymous accounts also need
    # no email, which makes them the cheapest thing to mass-create.
    "endpoints.add_anon_user": Limit("200 per hour"),

    # User search accepts a full email address as a search key. One lookup can
    # only confirm an address the searcher already typed, but without a ceiling
    # a script could sweep a wordlist to find which addresses have an account.
    # Per session, so one student's searching can't lock out the next desk.
    "endpoints.search_by_search_term": Limit("60 per minute;600 per hour", key="session"),

    # Account-less reading of a shared article. No session means no account to
    # key on. The endpoint only translates words at positions in real articles
    # and caches every answer, so the real spend ceiling is the global
    # cache-miss budget charged inside the view (public_article.GLOBAL_MISS_LIMIT);
    # this per-IP limit just keeps one host from walking positions quickly. The
    # page's "10 words" is a separate, client-side nudge.
    "endpoints.public_translate": Limit("20 per minute;60 per hour;200 per day"),
    # Content fetch: cheap once the article is tokenized, but a cold article
    # triggers Stanza tokenization, so don't let one host walk the id space.
    "endpoints.public_article": Limit("60 per minute;600 per hour"),
    # Link lookups: codes are 62^10, so this isn't about guessing -- just the
    # same backstop as every other public endpoint.
    "endpoints.article_link_info": Limit("60 per minute;600 per hour"),
    "endpoints.article_share_link_info": Limit("60 per minute;600 per hour"),
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


def _target_account_key():
    """
    Rate-limit key for endpoints that authenticate an account named in the
    route, so failed attempts are counted against the account being guessed at
    rather than against whoever is asking.

    This is the limit that actually stops brute force. An IP bucket cannot:
    anyone willing to rotate addresses steps around it. It is also the one
    that makes the IP numbers safe to keep loose, because a class of thirty
    behind one school NAT is thirty separate buckets here, not one.

    /session/<email> names the account by address, /get_anon_session/<uuid> by
    uuid. Falling back to the IP when neither is present is deliberate: a
    constant would put every caller in a single bucket, which is the failure
    this file exists to prevent.
    """
    args = flask.request.view_args or {}
    email = args.get("email")
    if email:
        return f"account:{email.strip().lower()}"
    uuid = args.get("uuid")
    if uuid:
        # There is no uuid column on user: an anonymous account's uuid is the
        # local part of the address it was generated with, and
        # authorize_anonymous appends the domain back on. So this route and
        # /session/<uuid>@anon.zeeguu reach one account by two doors, and since
        # flask-limiter buckets per endpoint that account gets ten guesses at
        # each -- twenty rather than ten. Left alone deliberately: twenty wrong
        # passwords a quarter of an hour is no more use to someone guessing
        # than ten, and merging the buckets costs more than it buys.
        return f"account:{uuid.strip().lower()}"
    return get_remote_address()


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
        "target_account": _target_account_key,
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
