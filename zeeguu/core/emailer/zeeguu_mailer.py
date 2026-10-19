from smtplib import SMTP

import yagmail
import zeeguu
from markupsafe import escape
from zeeguu.logging import logger, log


class ZeeguuMailer(object):
    def __init__(self, message_subject, message_body, to_email):

        self.message_body = message_body
        self.to_email = to_email
        self.message_subject = message_subject

        self.our_email = zeeguu.core.app.config.get("SMTP_EMAIL")
        self.password = zeeguu.core.app.config.get("SMTP_PASS")

    def send_with_yagmail(self):
        yag = yagmail.SMTP(self.our_email, self.password)
        yag.send(self.to_email, self.message_subject, contents=self.message_body)

    def send(self):
        # EMAIL_SENDING_ENABLED is the global "actually send email" switch: on in
        # prod, off in dev/test (this also disables the mailer during unit tests).
        # It gates ALL mail — user-facing (password reset, share notifications) and
        # team/monitoring alike; per-feature or per-user opt-outs are the caller's job.
        if not zeeguu.core.app.config.get("EMAIL_SENDING_ENABLED", False):
            log("returning without sending")
            return
        try:
            log("sending email...")
            self.send_with_yagmail()
        except Exception as e:
            log(f"Failed to send email: {e}")
            from sentry_sdk import capture_exception

            capture_exception(e)

    def _content_of_email(self):
        from email.mime.text import MIMEText

        message = MIMEText(self.message_body)
        message["From"] = self.our_email
        message["To"] = self.to_email
        message["Subject"] = self.message_subject

        return message.as_string()

    @classmethod
    def send_feedback(cls, subject, component, message, user, url=None, origin=None):
        where = " · ".join(escape(x) for x in [component, origin, url] if x)
        body = (
            f"{escape(message)}\n\n"
            + "—\n"
            + f"{escape(user.name)} ({user.id}) · {escape(user.email)}\n"
            + f"{where}\n"
            + _learner_line(user)
            + _recent_activity(user)
        )
        mailer = ZeeguuMailer(
            subject,
            body,
            # Gmail files mail it sends to itself under Sent only, never the
            # Inbox, so feedback goes to an address someone actually reads.
            zeeguu.core.app.config.get(
                "FEEDBACK_EMAIL", zeeguu.core.app.config.get("SMTP_EMAIL")
            ),
        )
        mailer.send()

    @classmethod
    def notify_audio_experiment(cls, data, user):
        content = f"{escape(user.name)} ({escape(user.email)}, {escape(user.invitation_code)})\n"
        content += f"{escape(data.get('event', ''))}"
        content += "\n"
        content += f"{escape(data.get('value', ''))}"
        content += "\n"
        content += f"{escape(data.get('extra_data', ''))}"
        content += "\n"
        content += f"{escape(data.get('time', ''))}"
        content += "\n\n"
        content += "Cheers,\n Your Friendly Zeeguu Server"

        prefix = "@i"
        for handle in ["jkak", "gupe", "mlun"]:
            ZeeguuMailer(
                "Audio Experiment Event",
                content,
                handle + prefix + "tu" + ".d" + "k",
            ).send()

    @classmethod
    def send_alert(cls, subject, content_lines):
        """Something is broken and someone should look now (crawler stalled,
        feeds failing). Goes to ALERTS_EMAIL (an address or a list): mail to
        SMTP_EMAIL, the team Gmail, lands in its Sent folder only."""
        body = "\r\n".join(content_lines)
        to = zeeguu.core.app.config.get(
            "ALERTS_EMAIL", zeeguu.core.app.config.get("SMTP_EMAIL")
        )
        ZeeguuMailer(subject, body, to).send()

    @classmethod
    def send_mail(cls, subject, content_lines):

        logger.info("Sending email...")
        body = "\r\n".join(content_lines)
        mailer = ZeeguuMailer(subject, body, zeeguu.core.app.config.get("SMTP_EMAIL"))
        mailer.send()

    @classmethod
    def send_content_retrieved_notification(cls, article, old_content=""):
        def flag(lang_code):
            flag_map = {"fr": "🇫🇷", "da": "🇩🇰", "de": "🇩🇪", "nl": "🇳🇱", "es": "🇪🇸"}

            return flag_map.get(lang_code, "")

        title = f"NEW ({flag(article.language.code)}) {article.title}"
        content = f"{article.url.as_string()}" + "\n"
        content += f"Published: {article.published_time}" + "\n"
        content += f"Difficulty: {article.fk_difficulty}" + "\n"
        content += f"Word Count: {article.word_count}" + "\n"
        content += f"Topics: {article.topics_as_string()}" + "\n"
        content += f"https://www.zeeguu.org/read/article?id={article.id}" + "\n\n"

        content += "\n\n" + article.title + "\n\n"
        content += article.get_content()

        if old_content:
            content += "\n\n\n\n\n\n\n\n\n\n\n\n"
            content += "--------" + "\n"
            content += "--------" + "\n"
            content += "--------" + "\n"
            content += "--------" + "\n"
            content += "OLD CONTENT" + "\n\n"
            content += old_content

        mailer = ZeeguuMailer(
            title,
            content,
            "zeeguu.team@gmail.com",
        )
        mailer.send()


def _learner_line(user):
    try:
        line = f"Learning: {user.learned_language.code} (from {user.native_language.code})"
        classes = [m.cohort.name for m in user.cohorts]
        if classes:
            line += " · Class: " + ", ".join(classes)
        return escape(line) + "\n"
    except Exception as e:
        log(f"feedback mail: no learner line: {e}")
        return ""


# Read aloud on every click; drowns out the events that say what happened
_NOISY_EVENTS = {"SPEAK TEXT"}


def _recent_activity(user, minutes=15, max_lines=12):
    """What the user did right before sending feedback, oldest first,
    with consecutive repeats of an event collapsed into one line."""
    from datetime import datetime, timedelta
    from zeeguu.core.model.user_activitiy_data import UserActivityData

    try:
        events = (
            UserActivityData.query.filter(UserActivityData.user_id == user.id)
            .filter(UserActivityData.time > datetime.utcnow() - timedelta(minutes=minutes))
            .filter(UserActivityData.event.notin_(_NOISY_EVENTS))
            .order_by(UserActivityData.time)
            .all()
        )
    except Exception as e:
        log(f"feedback mail: no recent activity: {e}")
        return ""

    lines = []
    for e in events:
        if lines and lines[-1]["event"] == e.event:
            lines[-1]["count"] += 1
            lines[-1]["value"] = e.value
            continue
        lines.append(dict(time=e.time, event=e.event, value=e.value, count=1))
    if not lines:
        return ""

    out = f"\nBefore (last {minutes} min, UTC):\n"
    for l in lines[-max_lines:]:
        count = f" ×{l['count']}" if l["count"] > 1 else ""
        value = f": {l['value'][:60]}" if l["value"] else ""
        out += f"{l['time']:%H:%M} {l['event'].lower()}{count}{value}\n"
    return escape(out)
