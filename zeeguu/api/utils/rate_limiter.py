# Rate limiting utilities for security-sensitive endpoints
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Global limiter instance - initialized in create_app()
limiter = None

# Rate limit definitions for security-sensitive endpoints
RATE_LIMITS = {
    # Login endpoints - prevent brute force attacks
    "api.get_session": "5 per minute;20 per hour",
    "api.get_anon_session": "5 per minute;20 per hour",

    # Password reset endpoints - prevent abuse
    "api.send_code": "3 per minute;10 per hour",
    "api.reset_password": "5 per minute;20 per hour",

    # Account creation endpoints - prevent mass registration
    "api.add_user": "5 per hour",
    "api.add_basic_user": "5 per hour",
    "api.add_anon_user": "10 per hour",
}


def init_limiter(app):
    """
    Initialize the rate limiter with the Flask app.
    Call this from create_app() after app is created.

    Rate limits are applied to specific security-sensitive endpoints:
    - Login: 5 per minute, 20 per hour (prevent brute force)
    - Password reset: 3 per minute, 10 per hour (prevent abuse)
    - Account creation: 5 per hour (prevent mass registration)
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

    for endpoint, limit_string in RATE_LIMITS.items():
        try:
            limiter.limit(limit_string, key_func=get_remote_address)(
                app.view_functions.get(endpoint)
            )
        except Exception as e:
            # Don't fail startup if an endpoint doesn't exist (e.g., during testing)
            pass


def get_limiter():
    """Get the global limiter instance."""
    global limiter
    return limiter
