from smtplib import SMTP

from zeeguu.api.app import app
from zeeguu.core import logger


class ZeeguuMailer(object):
    def __init__(self, message_subject, message_body, to_email):
        self.message_body = message_body
        self.to_email = to_email
        self.message_subject = message_subject
        self.server_name = app.config.get("SMTP_SERVER")
        self.our_email = app.config.get("SMTP_USERNAME")
        self.password = app.config.get("SMTP_PASSWORD")

    def send(self):

        # disable the mailer during unit testing
        if not app.config.get("SEND_NOTIFICATION_EMAILS", False):
            return

        message = self._content_of_email()
        # Send email
        server = SMTP(self.server_name)
        server.ehlo()
        server.starttls()
        server.login(user=self.our_email, password=self.password)
        server.sendmail(from_addr=self.our_email, to_addrs=self.to_email, msg=message)
        server.quit()

    def _content_of_email(self):
        from email.mime.text import MIMEText

        message = MIMEText(self.message_body)
        message["From"] = self.our_email
        message["To"] = self.to_email
        message["Subject"] = self.message_subject

        return message.as_string()

    @classmethod
    def send_feedback(cls, subject, context, message, user):
        mailer = ZeeguuMailer(
            subject,
            f"Dear Zeeguu Team,\n\nWrt. **{context}** I'd like to report that: \n\n"
            + message
            + "\n\n"
            + "Cheers,\n"
            + f"{user.name} ({user.id})",
            app.config.get("SMTP_USERNAME"),
        )

        mailer.send()

    @classmethod
    def notify_audio_experiment(cls, data, user):
        content = f"Dear Zeeguu Team,\n\nWrt. the ** audio exercises experiment** I'd like to report the following: \n\n"
        content += f"{user.name} ({user.email})\n"
        content += data.get("event", "")
        content += "\n"
        content += data.get("value", "")
        content += "\n\n"
        content += "Cheers,\n Your Friendly Zeeguu Server"

        at = "@i"
        for email in ["jkak", "gupe", "mlun"]:
            ZeeguuMailer(
                "Audio Experiment Event",
                content,
                email + at + "tu" + "." + "dk",
            ).send()

    @classmethod
    def send_mail(cls, subject, content_lines):
        logger.info("Sending email...")
        body = "\r\n".join(content_lines)
        mailer = ZeeguuMailer(subject, body, app.config.get("SMTP_USERNAME"))
        mailer.send()
