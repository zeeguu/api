from unittest.mock import patch

import zeeguu.core
from fixtures import logged_in_client as client
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer


def _recipient_of_alert():
    sent = {}

    def capture(self, subject, body, to_email):
        sent["to"] = to_email

    with patch.object(ZeeguuMailer, "__init__", capture), patch.object(ZeeguuMailer, "send"):
        ZeeguuMailer.send_alert("⚠️ crawler stalled", ["details"])
    return sent["to"]


def test_alerts_go_to_alerts_email(client):
    with patch.dict(zeeguu.core.app.config, {"ALERTS_EMAIL": ["mlun@itu.dk"]}):
        assert _recipient_of_alert() == ["mlun@itu.dk"]


def test_alerts_fall_back_to_the_smtp_address(client):
    config = zeeguu.core.app.config
    with patch.dict(config, {"SMTP_EMAIL": "team@example.com"}):
        config.pop("ALERTS_EMAIL", None)
        assert _recipient_of_alert() == "team@example.com"
