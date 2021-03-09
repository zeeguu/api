from smtplib import SMTP

from zeeguu_api.app import app
from zeeguu_core import logger


class ZeeguuMailer(object):

    def __init__(self, message_subject, message_body, to_email):
        self.message_body = message_body
        self.to_email = to_email
        self.message_subject = message_subject
        self.server_name = app.config.get('SMTP_SERVER')
        self.our_email = app.config.get('SMTP_USERNAME')
        self.password = app.config.get('SMTP_PASSWORD')

    def send(self):

        # disable the mailer during unit testing
        if not app.config.get('SEND_NOTIFICATION_EMAILS', False):
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
        message['From'] = self.our_email
        message['To'] = self.to_email
        message['Subject'] = self.message_subject

        return message.as_string()

    @classmethod
    def send_mail(cls, subject, content_lines):
        logger.info("Sending email...")
        body = "\r\n".join(content_lines)
        mailer = ZeeguuMailer(subject, body, app.config.get('SMTP_USERNAME'))
        mailer.send()
