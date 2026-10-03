"""Coarse device facts from a User-Agent header, for the onboarding funnel.

Only the families and major versions are kept. The raw header, together with a
persistent funnel id, would be close to a fingerprint, and the question it has
to answer -- did people on this kind of device get stuck? -- needs no more.

In-app browsers are looked for before the general browsers on purpose: the
Instagram or Facebook browser also announces itself as Safari or Chrome, and it
is exactly the case worth telling apart, since sign-up forms tend to break in
them.
"""

import re

# (family, pattern). The first match wins, so order matters: iPadOS and iOS
# both say "like Mac OS X", and Android says "Linux".
_OS = [
    ("ios", re.compile(r"(?:iPhone|iPad|iPod).*? OS (\d+)")),
    ("android", re.compile(r"Android (\d+)")),
    ("windows", re.compile(r"Windows NT (\d+)")),
    ("chromeos", re.compile(r"CrOS")),
    ("macos", re.compile(r"Mac OS X (\d+)")),
    ("linux", re.compile(r"Linux")),
]

_BROWSERS = [
    # In-app browsers: before everything else, see the module docstring.
    ("instagram", re.compile(r"Instagram (\d+)")),
    ("facebook", re.compile(r"FB(?:AV|_IAB)/(\d+)")),
    ("messenger", re.compile(r"Messenger(?:ForiOS)?/?(\d+)?")),
    ("tiktok", re.compile(r"(?:musical_ly|BytedanceWebview)_?(\d+)?")),
    ("snapchat", re.compile(r"Snapchat/(\d+)")),
    ("linkedin", re.compile(r"LinkedInApp/?(\d+)?")),
    ("google_app", re.compile(r"GSA/(\d+)")),
    # General browsers. Edge and Opera also carry "Chrome/", Chrome on iOS
    # carries "Safari/", so each of those comes before the one it imitates.
    ("edge", re.compile(r"Edg(?:e|A|iOS)?/(\d+)")),
    ("opera", re.compile(r"OPR/(\d+)")),
    ("samsung", re.compile(r"SamsungBrowser/(\d+)")),
    ("firefox", re.compile(r"(?:Firefox|FxiOS)/(\d+)")),
    ("android_webview", re.compile(r"; wv\).*?Chrome/(\d+)")),
    ("chrome", re.compile(r"(?:Chrome|CriOS)/(\d+)")),
    ("safari", re.compile(r"Version/(\d+).*Safari/")),
    # WKWebView, which includes our own iOS app: WebKit with no Safari token.
    ("ios_webview", re.compile(r"\((?:iPhone|iPad|iPod).*AppleWebKit/(\d+)")),
]


def _match(table, user_agent):
    for family, pattern in table:
        found = pattern.search(user_agent)
        if found:
            version = found.group(1) if found.groups() else None
            return family, version
    return None, None


def parse_user_agent(user_agent):
    """{os, os_version, browser, browser_version}; None for anything unknown."""
    user_agent = user_agent or ""
    os, os_version = _match(_OS, user_agent)
    browser, browser_version = _match(_BROWSERS, user_agent)
    return {
        "os": os,
        "os_version": os_version,
        "browser": browser,
        "browser_version": browser_version,
    }
