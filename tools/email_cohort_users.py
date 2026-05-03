"""
Send a personalized email to every user in a given cohort.

Interactive: previews each email and asks before sending.
Idempotent: every send / skip-forever is appended to <template>.sent.log;
re-runs skip any user already logged for the same SUBJECT.

Usage:
    source $GH_FOLDER/zeeguu/api/.venv/bin/activate
    python -m tools.email_cohort_users --cohort pg25 --template tools/polyglots-2026.txt

Template format: first non-empty line is the subject, blank line, then the body.
Placeholders available in subject and body: {first_name}, {hello}.

Note: ZeeguuMailer silently no-ops unless SEND_NOTIFICATION_EMAILS is True
in the active config. The script prints which mode it is in at startup.
"""

import argparse
import json
import os
import sys
from datetime import datetime

from zeeguu.api.app import create_app
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from zeeguu.core.model.cohort import Cohort

app = create_app()
app.app_context().push()


HELLO = {
    "da": "Hej", "en": "Hi", "fr": "Bonjour", "nl": "Hallo", "pl": "Cześć",
    "ro": "Salut", "zh-CN": "你好", "tr": "Merhaba", "ku": "Silav", "ar": "مرحبا",
    "so": "Salaan", "de": "Hallo", "sv": "Hej", "sq": "Përshëndetje", "es": "Hola",
    "it": "Ciao", "ja": "こんにちは", "sr": "Здраво", "pt": "Olá", "ru": "Привет",
    "uk": "Привіт", "vi": "Xin chào", "hu": "Szia", "lv": "Sveiki", "ind": "Halo",
    "ur": "ہیلو", "ta": "வணக்கம்", "bn": "হ্যালო", "el": "Γεια",
}


def load_template(path):
    """First non-empty line is the subject; the rest is the body."""
    if not os.path.exists(path):
        print(f"Template file not found: {path}")
        print("Format: subject on first line, blank line, then body.")
        print("Placeholders: {first_name}, {hello}")
        sys.exit(1)
    with open(path) as f:
        lines = f.read().splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i == len(lines):
        print(f"Template file is empty: {path}")
        sys.exit(1)
    subject = lines[i].strip()
    body = "\n".join(lines[i + 1:]).lstrip("\n")
    return subject, body


def load_sent_log(log_path, subject):
    """Return user_ids to skip and counts per status, scoped to this subject."""
    locked_ids = set()
    counts = {"sent": 0, "skipped_forever": 0}
    if not os.path.exists(log_path):
        return locked_ids, counts
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("subject") != subject:
                continue
            locked_ids.add(rec.get("user_id"))
            status = rec.get("status", "sent")
            if status in counts:
                counts[status] += 1
    return locked_ids, counts


def append_sent_log(log_path, rec):
    with open(log_path, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def derive_first_name(user):
    parts = (user.name or "").split()
    return parts[0].title() if parts else "there"


def render(user, first_name, subject_tpl, body_tpl):
    lang_code = user.native_language.code if user.native_language else "en"
    hello = HELLO.get(lang_code, "Hello")
    return (
        subject_tpl.format(first_name=first_name, hello=hello),
        body_tpl.format(first_name=first_name, hello=hello),
    )


def prompt_first_name(default):
    """Returns ('name', str) | ('skip', None) | ('skip_forever', None) | ('quit', None)."""
    ans = input(
        f"First name to use [{default}] (n=skip, f=skip forever, q=quit): "
    ).strip()
    if ans == "n":
        return ("skip", None)
    if ans == "f":
        return ("skip_forever", None)
    if ans == "q":
        return ("quit", None)
    return ("name", ans or default)


def prompt_send():
    """Returns 'send' | 'skip' | 'skip_forever' | 'quit'."""
    while True:
        ans = input("Send? [y/N/f/q] (f=skip forever): ").strip().lower()
        if ans == "y":
            return "send"
        if ans == "f":
            return "skip_forever"
        if ans == "q":
            return "quit"
        if ans in ("n", ""):
            return "skip"


def parse_args():
    p = argparse.ArgumentParser(description="Send a personalized email to every user in a cohort.")
    p.add_argument("--cohort", required=True, help="Cohort invitation code (e.g. pg25)")
    p.add_argument("--template", required=True, help="Path to the template file")
    return p.parse_args()


def main():
    import zeeguu

    args = parse_args()
    template_path = os.path.abspath(args.template)
    log_path = template_path + ".sent.log"
    cohort_code = args.cohort

    subject_tpl, body_tpl = load_template(template_path)
    locked_ids, counts = load_sent_log(log_path, subject_tpl)

    live = zeeguu.core.app.config.get("SEND_NOTIFICATION_EMAILS", False)
    print(f"Mode: {'LIVE — emails will be sent' if live else 'SIMULATED (SEND_NOTIFICATION_EMAILS=False) — nothing will go out'}")
    print(f"From: {zeeguu.core.app.config.get('SMTP_EMAIL')}")
    print(f"Template: {template_path}")
    print(f"Sent log: {log_path}  "
          f"(prior for this subject: sent={counts['sent']}, skipped_forever={counts['skipped_forever']})")
    print()

    cohort = Cohort.find_by_code(cohort_code)
    users = cohort.get_students()
    pending = [u for u in users if u.id not in locked_ids]
    print(f"Cohort '{cohort_code}' (id={cohort.id}, name={cohort.name!r}): "
          f"{len(users)} users, {len(pending)} pending, {len(users) - len(pending)} locked-in.\n")

    sent = skipped = 0
    for i, user in enumerate(pending, 1):
        native_code = user.native_language.code if user.native_language else "?"
        print("=" * 70)
        print(f"[{i}/{len(pending)}]  on file: {user.name!r} <{user.email}>  native={native_code}")

        action, first_name = prompt_first_name(derive_first_name(user))
        if action == "quit":
            print("Quitting.")
            break
        if action == "skip":
            print("Skipped (this run).\n")
            skipped += 1
            continue
        if action == "skip_forever":
            append_sent_log(log_path, {
                "status": "skipped_forever",
                "user_id": user.id,
                "email": user.email,
                "name": user.name,
                "cohort_code": cohort_code,
                "subject": subject_tpl,
                "ts": datetime.utcnow().isoformat() + "Z",
            })
            print("Skipped forever (logged).\n")
            skipped += 1
            continue

        subject, body = render(user, first_name, subject_tpl, body_tpl)
        print(f"Subject: {subject}")
        print("-" * 70)
        print(body)
        print("-" * 70)

        action = prompt_send()
        if action == "quit":
            print("Quitting.")
            break
        if action == "skip":
            print("Skipped (this run).\n")
            skipped += 1
            continue
        if action == "skip_forever":
            append_sent_log(log_path, {
                "status": "skipped_forever",
                "user_id": user.id,
                "email": user.email,
                "name": user.name,
                "cohort_code": cohort_code,
                "subject": subject_tpl,
                "ts": datetime.utcnow().isoformat() + "Z",
            })
            print("Skipped forever (logged).\n")
            skipped += 1
            continue

        ZeeguuMailer(subject, body, user.email).send()
        append_sent_log(log_path, {
            "status": "sent",
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "first_name_used": first_name,
            "cohort_code": cohort_code,
            "subject": subject_tpl,
            "rendered_subject": subject,
            "live": bool(live),
            "ts": datetime.utcnow().isoformat() + "Z",
        })
        print(f"Sent to {user.email}.\n")
        sent += 1

    print()
    print(f"Done. Sent: {sent}.  Skipped: {skipped}.  "
          f"Remaining in cohort: {len(pending) - sent - skipped}.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
