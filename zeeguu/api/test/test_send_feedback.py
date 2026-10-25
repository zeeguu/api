from datetime import datetime, timezone
from unittest.mock import patch

from fixtures import logged_in_client as client
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from zeeguu.core.model.user_feedback import UserFeedback


def _activity(client, event, value=""):
    client.post(
        "/upload_user_activity_data",
        data=dict(
            time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            event=event,
            value=value,
            extra_data="",
        ),
    )


def _send_feedback(client, **form):
    sent = {}

    def capture(self, subject, body, to_email):
        sent.update(subject=subject, body=body)

    with patch.object(ZeeguuMailer, "__init__", capture), patch.object(ZeeguuMailer, "send"):
        response = client.post("/send_feedback", data=form)
    return response, sent


def test_mail_shows_message_origin_and_what_happened_before(client):
    _activity(client, "COMPLETED EXERCISES", "UMR")
    _activity(client, "SPEAK TEXT", "in")
    _activity(client, "KEEP EXERCISING", "UMR")
    _activity(client, "KEEP EXERCISING", "UMR")

    _, sent = _send_feedback(
        client,
        message="love it 💗",
        origin="Sidebar",
        feedbackComponentName="Exercises",
        currentUrl="https://www.zeeguu.org/exercises/summary",
    )
    print(sent["body"])

    body = sent["body"]
    assert body.startswith("love it 💗")
    assert "Exercises · Sidebar · https://www.zeeguu.org/exercises/summary" in body
    assert "Learning: " in body
    assert "completed exercises: UMR" in body
    assert "keep exercising ×2: UMR" in body
    assert "speak text" not in body
    assert UserFeedback.query.one().message == "Sidebar - love it 💗"


def test_feedback_is_mailed_even_when_storing_fails(client):
    with patch.object(UserFeedback, "create", side_effect=Exception("Incorrect string value")):
        response, sent = _send_feedback(client, message="love it 💗")

    assert response == b"OK"
    assert sent["body"].startswith("love it 💗")
