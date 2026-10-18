from flask import Response

# The admin dashboards are hand-built HTML: inline <style> blocks and style=""
# attributes, no scripts, no external resources. So the policy only allows
# inline styles, and forbids scripts and framing outright.
ADMIN_HTML_CSP = (
    "default-src 'none'; "
    "style-src 'unsafe-inline'; "
    "img-src 'self' data:; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'none'"
)


def admin_html_response(html, status=200):
    """A text/html Response for an admin-only page, with a restrictive CSP."""
    response = Response(html, status=status, mimetype="text/html")
    response.headers["Content-Security-Policy"] = ADMIN_HTML_CSP
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
