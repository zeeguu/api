"""
/status — a dev-only "server tamagotchi" health page.

The API container shares the `api_zeeguu_backend` network with Prometheus
(see ops/running/monitoring/docker-compose.yml), so we query it directly at
http://prometheus:9090 — no tunnel, no exposed port, no extra password. Access
is gated by @requires_session + @only_admins (same as the admin dashboards).

Container health is the headline signal: restarts, OOM kills, and memory as a
fraction of each container's own limit. Mood is rule-based (instant, no LLM);
the reasoning "speech bubble" can later be fed by the daily digest job.
"""

import json
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import flask
import requests
from markupsafe import escape

from . import api
from zeeguu.api.utils.route_wrappers import requires_session, only_admins

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")

# Per-query timeout. All queries run concurrently, so worst-case page latency is
# ~one timeout, not the sum — see _gather().
REQUEST_TIMEOUT = 3

# The afternoon watch (on the Mac) reasons over the day's capture and drops its
# one-line verdict here — /home/zeeguu/data is mounted into this container as
# /zeeguu-data — so the phone (page + widget) can show the reasoned briefing
# (incl. the log analysis), not just live vitals. See ADR 028.
DIGEST_PATH = os.environ.get("HEALTH_DIGEST_PATH", "/zeeguu-data/health-digest.json")


def _read_daily():
    """The latest reasoned digest the afternoon watch published, or None."""
    try:
        with open(DIGEST_PATH) as f:
            d = json.load(f)
    except Exception:
        return None
    at = d.get("at")
    age_min = int((time.time() - at) / 60) if isinstance(at, (int, float)) else None
    return {
        "status": d.get("status"),
        "headline": d.get("headline"),
        "body": d.get("body"),
        "at": at,
        "age_min": age_min,
    }


# Ephemeral / uninteresting containers we don't want as pet organs.
def _skip_container(name):
    return (not name) or ("run_task-run-" in name) or name.startswith("buildx")


# ---------------------------------------------------------------------------
# Prometheus access
# ---------------------------------------------------------------------------
def _query(promql):
    """Return the result list, or None if Prometheus didn't answer successfully
    (unreachable, timeout, or a query-level error). None is the "no answer"
    signal used to distinguish a Prometheus outage from a genuinely-empty result."""
    try:
        r = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": promql},
            timeout=REQUEST_TIMEOUT,
        )
        data = r.json()
        if data.get("status") != "success":
            return None
        return data.get("data", {}).get("result", [])
    except Exception:
        return None


def _finite(value):
    """float() the raw Prometheus value string, dropping NaN/±Inf to None so no
    downstream round()/comparison ever sees a non-finite float."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _parse_scalar(res):
    if not res:
        return None
    try:
        return _finite(res[0]["value"][1])
    except (KeyError, IndexError):
        return None


def _parse_by_container(res):
    out = {}
    for r in res or []:
        name = r.get("metric", {}).get("name")
        if _skip_container(name):
            continue
        try:
            out[name] = _finite(r["value"][1])
        except (KeyError, IndexError):
            out[name] = None
    return out


def _parse_es(res):
    if res:
        return res[0].get("metric", {}).get("color", "unknown")
    return "unknown"


# name -> (promql, parser). All fired concurrently.
_QUERIES = {
    "disk": (
        '100*(1 - node_filesystem_avail_bytes{mountpoint="/",fstype!~"tmpfs|overlay"}'
        ' / node_filesystem_size_bytes{mountpoint="/",fstype!~"tmpfs|overlay"})',
        _parse_scalar,
    ),
    "mem": ("100*(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)", _parse_scalar),
    "load1": ("node_load1", _parse_scalar),
    "cores": ("count(count(node_cpu_seconds_total) by (cpu))", _parse_scalar),
    "restarts_24h": ('changes(container_start_time_seconds{name!=""}[24h])', _parse_by_container),
    "oom_24h": ('increase(container_oom_events_total{name!=""}[24h])', _parse_by_container),
    "mem_frac": (
        'container_memory_working_set_bytes{name!=""} '
        '/ (container_spec_memory_limit_bytes{name!=""} < 1e15)',
        _parse_by_container,
    ),
    "last_seen": ('time() - container_last_seen{name!=""}', _parse_by_container),
    "es": ("elasticsearch_cluster_health_status==1", _parse_es),
    "mysql_up": ("max(mysql_up)", _parse_scalar),
}


def _gather():
    with ThreadPoolExecutor(max_workers=len(_QUERIES)) as ex:
        futures = {name: ex.submit(_query, q) for name, (q, _) in _QUERIES.items()}
        raw = {name: fut.result() for name, fut in futures.items()}

    # Prometheus is "reachable" if any query got a successful answer (even empty).
    reachable = any(res is not None for res in raw.values())
    out = {"_reachable": reachable}
    for name, (_, parser) in _QUERIES.items():
        out[name] = parser(raw[name])
    return out


# ---------------------------------------------------------------------------
# Judge (rule-based mood)
# ---------------------------------------------------------------------------
SEV = {"green": 0, "yellow": 1, "red": 2}


def _container_verdict(name, v):
    # Persistent services (api-*, monitoring-*) are supposed to stay up, so a
    # restart loop or a disappearance is a real signal. Batch containers
    # (crawlers, one-shot cron jobs) legitimately start and exit on a schedule —
    # a finished crawler isn't "gone", and running 3x/day isn't "restarting". For
    # them only an OOM kill or nearing the mem limit means anything.
    persistent = name.startswith("api-") or name.startswith("monitoring-")
    oom = v["oom_24h"].get(name) or 0
    restarts = (v["restarts_24h"].get(name) or 0) if persistent else 0
    gone = v["last_seen"].get(name) if persistent else None
    # mem as a fraction of the container's own limit; cadvisor emits the
    # float64-max sentinel for "no limit", so anything physically impossible
    # (a live container can't exceed ~1x its limit) means "no real limit".
    frac = v["mem_frac"].get(name)
    if frac is not None and (not math.isfinite(frac) or frac > 8):
        frac = None

    if oom > 0 or restarts >= 3 or (frac is not None and frac >= 0.95) or (gone and gone > 300):
        status = "red"
    elif restarts >= 1 or (frac is not None and frac >= 0.85) or (gone and gone > 120):
        status = "yellow"
    else:
        status = "green"

    bits = []
    if restarts:
        bits.append(f"{int(restarts)} restart{'s' if restarts != 1 else ''}/24h")
    if oom:
        bits.append(f"{int(oom)} OOM")
    if frac is not None:
        bits.append(f"mem {round(frac * 100)}% of limit")
    if gone and gone > 120:
        bits.append(f"last seen {round(gone)}s ago")
    return status, ", ".join(bits) or "healthy"


def _judge(v):
    """Return (overall_status, headline, [(name, status, detail), ...])."""
    names = set()
    for key in ("restarts_24h", "oom_24h", "mem_frac", "last_seen"):
        names.update(v[key].keys())
    roster = []
    for name in sorted(names):
        st, detail = _container_verdict(name, v)
        roster.append((name, st, detail))
    roster.sort(key=lambda x: (-SEV[x[1]], x[0]))

    if not v["_reachable"]:
        return "unknown", "can't reach Prometheus", roster

    issues = []  # (severity, message)
    for name, st, detail in roster:
        if st != "green":
            issues.append((SEV[st], f"{name}: {detail}"))

    d, m = v["disk"], v["mem"]
    if d is not None and d >= 90:
        issues.append((2, f"disk {round(d)}%"))
    elif d is not None and d >= 75:
        issues.append((1, f"disk {round(d)}%"))
    if m is not None and m >= 95:
        issues.append((2, f"memory {round(m)}%"))
    elif m is not None and m >= 85:
        issues.append((1, f"memory {round(m)}%"))
    if v["mysql_up"] is not None and v["mysql_up"] != 1:
        issues.append((2, "mysql down"))
    # A single-node cluster is permanently "yellow": the default 1 replica can't
    # be allocated with no second node to hold it. That's expected here and has
    # been the steady state for years, so only RED (an actual unassigned-primary
    # / red-index problem) is worth flagging — otherwise the pet is never green.
    if v["es"] == "red":
        issues.append((2, "elasticsearch RED"))

    if not issues:
        parts = []
        if d is not None:
            parts.append(f"disk {round(d)}%")
        if m is not None:
            parts.append(f"mem {round(m)}%")
        tail = f", {', '.join(parts)}" if parts else ""
        return "green", "all quiet — 0 restarts, 0 OOM" + tail, roster

    issues.sort(key=lambda x: -x[0])
    overall = "red" if issues[0][0] == 2 else "yellow"
    headline = "; ".join(msg for _, msg in issues[:3])
    return overall, headline, roster


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
_FACE = {
    "green": '<circle cx="40" cy="52" r="4.5" fill="#12261a"/><circle cx="64" cy="52" r="4.5" fill="#12261a"/><path d="M42 64 Q52 72 62 64" stroke="#12261a" stroke-width="3" fill="none" stroke-linecap="round"/>',
    "yellow": '<circle cx="40" cy="52" r="5" fill="#12261a"/><circle cx="64" cy="52" r="5" fill="#12261a"/><path d="M44 66 Q52 62 60 66" stroke="#12261a" stroke-width="3" fill="none" stroke-linecap="round"/><path d="M74 44 q4 8 0 12 q-4 -4 0 -12" fill="#5bc0e8"/>',
    "red": '<path d="M35 48 l9 8 M44 48 l-9 8" stroke="#12261a" stroke-width="2.6" stroke-linecap="round"/><path d="M59 48 l9 8 M68 48 l-9 8" stroke="#12261a" stroke-width="2.6" stroke-linecap="round"/><path d="M43 66 q9 -6 18 0" stroke="#12261a" stroke-width="3" fill="none" stroke-linecap="round"/>',
    "unknown": '<path d="M38 52 h6 M60 52 h6" stroke="#12261a" stroke-width="3" stroke-linecap="round"/><path d="M44 66 h16" stroke="#12261a" stroke-width="3" stroke-linecap="round"/>',
}
_INK = {"green": "#1f8a4c", "yellow": "#c98a1a", "red": "#c0392b", "unknown": "#7a7a7a"}
_DOT = {"green": "#2ec76a", "yellow": "#e0a52a", "red": "#e0533f", "unknown": "#9a9a9a"}
_SCREEN_BG = {"green": "#16301f", "yellow": "#332811", "red": "#341a1a", "unknown": "#222"}


def _pet_svg(status):
    ink = _INK[status]
    return (
        f'<svg viewBox="0 0 104 104" width="104" height="104">'
        f'<line x1="52" y1="16" x2="52" y2="26" stroke="{ink}" stroke-width="3"/>'
        f'<circle cx="52" cy="13" r="4" fill="{ink}"/>'
        f'<rect x="20" y="26" width="64" height="60" rx="18" fill="{ink}"/>'
        f'<rect x="26" y="40" width="52" height="40" rx="12" fill="#f4fff7"/>'
        f'{_FACE[status]}'
        f'<rect x="30" y="86" width="10" height="8" rx="3" fill="{ink}"/>'
        f'<rect x="64" y="86" width="10" height="8" rx="3" fill="{ink}"/>'
        f'</svg>'
    )


def _bar(label, pct, color):
    pct = 0 if pct is None else max(0, min(100, pct))
    return (
        f'<div class="stat"><span class="lbl">{label}</span>'
        f'<div class="bar"><i style="width:{pct:.0f}%;background:{color}"></i></div>'
        f'<span class="val">{pct:.0f}%</span></div>'
    )


def _brief_html(daily):
    """The afternoon watch's reasoned line + how long ago, or a placeholder."""
    if not (daily and daily.get("headline")):
        return '<span class="ago">no reasoned briefing yet today</span>'
    age = daily.get("age_min")
    when = ""
    if isinstance(age, int):
        when = f" <span class=\"ago\">· {age // 60}h ago</span>" if age >= 60 else f" <span class=\"ago\">· {age}m ago</span>"
    return f'&#128203; {escape(daily["headline"])}{when}'


def _render(v, overall, headline, roster, daily):
    disk = v["disk"]
    mem = v["mem"]
    load_pct = None
    if v["load1"] is not None and v["cores"]:
        load_pct = 100 * v["load1"] / v["cores"]
    greens = sum(1 for _, st, _ in roster if st == "green")
    hp = round(100 * greens / len(roster)) if roster else 0

    bc = {"green": "#2ec76a", "yellow": "#e0a52a", "red": "#e0533f"}.get(overall, "#9a9a9a")
    bars = _bar("DISK", disk, bc) + _bar("MEM", mem, bc) + _bar("LOAD", load_pct, bc) + _bar("HP", hp, bc)
    dots = "".join(
        f'<span class="dot" style="background:{_DOT[st]}" title="{escape(name)} — {escape(detail)}"></span>'
        for name, st, detail in roster
    )
    count = f"{greens}/{len(roster)} healthy" if roster else "no containers"

    # Single-pass substitution: a token that happens to appear inside a
    # substituted value (e.g. an oddly-named container) is NOT re-processed.
    subs = {
        "__SCREENBG__": _SCREEN_BG[overall],
        "__BUBBLE__": str(escape(headline)),
        "__PET__": _pet_svg(overall),
        "__BARS__": bars,
        "__DOTS__": dots,
        "__STATUS__": overall,
        "__COUNT__": count,
        "__BRIEF__": _brief_html(daily),
    }
    return re.sub(r"__[A-Z]+__", lambda mo: subs.get(mo.group(0), mo.group(0)), _PAGE)


_PAGE = """<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>server-gotchi</title>
<style>
  body{margin:0;background:#0d0f0e;color:#cfe;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    display:flex;justify-content:center;align-items:flex-start;padding:32px 16px;min-height:100vh;}
  .device{width:320px;background:#1a1d1b;border:1px solid #2c302e;border-radius:44% 44% 44% 44%/26px;
    padding:22px 24px 18px;box-shadow:0 6px 24px rgba(0,0,0,.4);}
  .brand{font-family:ui-monospace,monospace;font-size:10px;letter-spacing:.16em;color:#7d8a83;
    text-align:center;margin-bottom:12px;text-transform:uppercase;}
  .screen{border-radius:14px;padding:14px;border:2px solid #333;background:__SCREENBG__;min-height:250px;
    display:flex;flex-direction:column;transition:background .4s;}
  .bubble{font-family:ui-monospace,monospace;font-size:11px;line-height:1.4;background:rgba(0,0,0,.3);
    color:#e6f0ea;border:1px solid rgba(255,255,255,.1);border-radius:9px;padding:7px 9px;margin-bottom:8px;min-height:40px;}
  .pet{display:flex;justify-content:center;align-items:center;flex:1;padding:6px 0;}
  .pet svg{animation:bob 2.6s ease-in-out infinite;}
  @keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}
  .statgrid{display:grid;grid-template-columns:1fr 1fr;gap:5px 12px;margin-top:6px;}
  .stat{display:flex;align-items:center;gap:6px;}
  .lbl{font-family:ui-monospace,monospace;font-size:9px;width:30px;color:#9fb3a8;letter-spacing:.06em;}
  .bar{flex:1;height:7px;border-radius:4px;background:rgba(255,255,255,.12);overflow:hidden;}
  .bar i{display:block;height:100%;border-radius:4px;}
  .val{font-family:ui-monospace,monospace;font-size:9px;width:30px;text-align:right;color:#9fb3a8;}
  .roster{margin-top:12px;padding-top:10px;border-top:1px solid rgba(255,255,255,.08);}
  .dots{display:flex;flex-wrap:wrap;gap:6px;}
  .dot{width:11px;height:11px;border-radius:50%;cursor:help;}
  .count{font-family:ui-monospace,monospace;font-size:9px;color:#7d8a83;margin-top:8px;text-align:center;}
  .brief{font-family:ui-monospace,monospace;font-size:9px;line-height:1.4;color:#c9d6cf;margin-top:10px;
    padding-top:8px;border-top:1px solid rgba(255,255,255,.06);}
  .brief .ago{color:#7d8a83;}
  .foot{text-align:center;font-size:10px;color:#5a6560;margin-top:12px;font-family:ui-monospace,monospace;}
</style></head>
<body>
  <div class="device">
    <div class="brand">SERVER&#8226;GOTCHI &nbsp; zeeguu.org</div>
    <div class="screen">
      <div class="bubble">__BUBBLE__</div>
      <div class="pet">__PET__</div>
      <div class="statgrid">__BARS__</div>
      <div class="roster"><div class="dots">__DOTS__</div><div class="count">__COUNT__ &middot; __STATUS__</div></div>
      <div class="brief">__BRIEF__</div>
    </div>
    <div class="foot">live &middot; refreshes every 30s</div>
  </div>
</body></html>"""


def _summary(v, overall, headline, roster, daily):
    """The same verdict as the page, as a compact dict — for the phone widget
    (GET /status?format=json). No HTML, just the numbers a widget renders.
    `daily` is the afternoon watch's reasoned briefing (incl. log analysis)."""
    load_pct = 100 * v["load1"] / v["cores"] if (v["load1"] is not None and v["cores"]) else None
    greens = sum(1 for _, st, _ in roster if st == "green")
    rnd = lambda x: round(x) if x is not None else None
    return {
        "status": overall,
        "headline": headline,
        "daily": daily,
        "host": {
            "disk_pct": rnd(v["disk"]),
            "mem_pct": rnd(v["mem"]),
            "load_pct": rnd(load_pct),
            "hp": round(100 * greens / len(roster)) if roster else 0,
        },
        "containers": {
            "total": len(roster),
            "healthy": greens,
            "issues": [{"name": n, "status": s, "detail": d} for n, s, d in roster if s != "green"],
        },
        "datastores": {"elasticsearch": v["es"], "mysql_up": v["mysql_up"]},
    }


@api.route("/status", methods=["GET"])
@requires_session
@only_admins
def status():
    v = _gather()
    overall, headline, roster = _judge(v)
    daily = _read_daily()
    if flask.request.args.get("format") == "json":
        return flask.jsonify(_summary(v, overall, headline, roster, daily))
    return flask.Response(_render(v, overall, headline, roster, daily), mimetype="text/html")
