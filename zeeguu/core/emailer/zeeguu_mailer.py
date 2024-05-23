from smtplib import SMTP

import yagmail
import zeeguu
from zeeguu.logging import logger, logp


class ZeeguuMailer(object):
    def __init__(self, message_subject, message_body, to_email):

        self.message_body = message_body
        self.to_email = to_email
        self.message_subject = message_subject

        self.server_name = zeeguu.core.app.config.get("SMTP_SERVER")
        self.our_email = zeeguu.core.app.config.get("SMTP_EMAIL")
        self.username = zeeguu.core.app.config.get("SMTP_USERNAME")
        self.password = zeeguu.core.app.config.get("SMTP_PASS")

    def send_with_yagmail(self):
        yag = yagmail.SMTP(self.our_email, self.password)
        yag.send(self.to_email, self.message_subject, contents=self.message_body)

    def send(self):
        # this next line disables the mailer also during unit testing
        if not zeeguu.core.app.config.get("SEND_NOTIFICATION_EMAILS", False):
            logp("returning without sending")
            return
        try:
            logp("sending email...")
            self.send_with_yagmail()
        except Exception as e:
            logp(f"Failed to send email: {e}")
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
    def send_feedback(cls, subject, context, message, user):

        print("sending feedback...")
        mailer = ZeeguuMailer(
            subject,
            f"Dear Zeeguu Team,\n\nWrt. **{context}** I'd like to report that: \n\n"
            + message
            + "\n\n"
            + "Cheers,\n"
            + f"{user.name} ({user.id}, {user.email})",
            zeeguu.core.app.config.get("SMTP_USERNAME"),
        )

        mailer.send()

    @classmethod
    def notify_audio_experiment(cls, data, user):
        content = f"{user.name} ({user.email})\n"
        content += data.get("event", "")
        content += "\n"
        content += data.get("value", "")
        content += "\n"
        content += data.get("extra_data", "")
        content += "\n"
        content += data.get("time", "")
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
    def send_mail(cls, subject, content_lines):

        logger.info("Sending email...")
        body = "\r\n".join(content_lines)
        mailer = ZeeguuMailer(
            subject, body, zeeguu.core.app.config.get("SMTP_USERNAME")
        )
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
        content += article.content

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
