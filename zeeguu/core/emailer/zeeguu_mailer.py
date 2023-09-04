from smtplib import SMTP


import yagmail


class ZeeguuMailer(object):
    
    def __init__(self, message_subject, message_body, to_email):
        from zeeguu.api.app import app
        self.message_body = message_body
        self.to_email = to_email
        self.message_subject = message_subject
        self.server_name = app.config.get("SMTP_SERVER")
        self.our_email = app.config.get("SMTP_EMAIL")
        self.username = app.config.get("SMTP_USERNAME")
        self.password = app.config.get("SMTP_PASS")

    def old_send_smtp(self):
        message = self._content_of_email()
        # Send email
        server = SMTP(self.server_name)
        server.ehlo()
        server.starttls()
        server.login(user=self.username, password=self.password)
        server.sendmail(from_addr=self.our_email, to_addrs=self.to_email, msg=message)
        server.quit()


    def send_with_yagmail(self):
        yag = yagmail.SMTP(self.our_email, self.password)
        yag.send(self.to_email, self.message_subject, contents=self.message_body)

    def send(self):
        from zeeguu.api.app import app
        # disable the mailer during unit testing
        if not app.config.get("SEND_NOTIFICATION_EMAILS", False):
            return

        self.send_with_yagmail()


    def _content_of_email(self):
        from email.mime.text import MIMEText

        message = MIMEText(self.message_body)
        message["From"] = self.our_email
        message["To"] = self.to_email
        message["Subject"] = self.message_subject

        return message.as_string()

    @classmethod
    def send_feedback(cls, subject, context, message, user):
        from zeeguu.api.app import app
        print("sending feedback...")
        mailer = ZeeguuMailer(
            subject,
            f"Dear Zeeguu Team,\n\nWrt. **{context}** I'd like to report that: \n\n"
            + message
            + "\n\n"
            + "Cheers,\n"
            + f"{user.name} ({user.id}, {user.email})",
            app.config.get("SMTP_USERNAME"),
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
        from zeeguu.core import logger
        from zeeguu.api.app import app
        logger.info("Sending email...")
        body = "\r\n".join(content_lines)
        mailer = ZeeguuMailer(subject, body, app.config.get("SMTP_USERNAME"))
        mailer.send()

    @classmethod
    def send_content_retrieved_notification(cls, a, old_content):
        from zeeguu.api.app import app
        title = f"Updated Content for article {a.id}"
        content = f"https://www.zeeguu.org/read/article?id={a.id}"
        content += a.title + "\n"
        content += a.content
        content += "--------" + "\n"
        content += "--------" + "\n"
        content += "--------" + "\n"
        content += "--------" + "\n"
        content += "OLD CONTENT" + "\n"
        content += old_content

        mailer = ZeeguuMailer(
            title,
            content,
            app.config.get("SMTP_USERNAME"),
        )

        mailer.send()
