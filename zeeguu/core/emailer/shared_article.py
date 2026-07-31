from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from zeeguu.core.model.user import User
from zeeguu.core.model.user_preference import UserPreference
from zeeguu.core.model.shared_article import SharedArticle
from zeeguu.logging import log

WEB_URL = "https://zeeguu.org"


def send_shared_article_notification(to_user_id, from_user_id, shared_article_id):
    """Email the recipient that a friend shared an article. Best-effort; meant to
    run off the request thread via run_in_background (re-fetches everything by id).

    Debounce without a cron or extra state: only the recipient's **first** unread
    share triggers an email. Once they have an unread share they've been told;
    further shares just accumulate in their inbox until they clear it, and then
    the next share re-notifies. That collapses a burst of shares into one email.

    Globally gated by SEND_NOTIFICATION_EMAILS (checked inside ZeeguuMailer.send),
    and per-user by the EMAIL_ON_ARTICLE_SHARED preference.
    """
    try:
        recipient = User.find_by_id(to_user_id)
        if not recipient or not recipient.email:
            return
        if not UserPreference.is_email_on_article_shared_enabled(recipient):
            return
        # Only the first unread share triggers an email; the rest batch in-app.
        if SharedArticle.unread_count_for(to_user_id) != 1:
            return

        sharer = User.find_by_id(from_user_id)
        shared = SharedArticle.find_by_id(shared_article_id)
        if not shared:
            return
        article_title = shared.article.title if shared.article else "an article"

        subject = f"{sharer.name} shared an article with you on Zeeguu"

        lines = [
            f"Hi {recipient.name},",
            "",
            f"{sharer.name} shared an article with you: “{article_title}”.",
        ]
        if shared.note:
            lines += ["", f"Their note: “{shared.note}”"]
        lines += [
            "",
            "Open it in the language you're learning, at your level:",
            f"{WEB_URL}/articles/shared",
            "",
            "— Zeeguu",
            "",
            f"You can turn these emails off in Settings: {WEB_URL}/account_settings/notifications",
        ]
        body = "\r\n".join(lines)

        ZeeguuMailer(subject, body, recipient.email).send()
        log(f"Sent shared-article notification email to user {to_user_id}")
    except Exception as e:
        from sentry_sdk import capture_exception

        log(f"Failed to send shared-article notification email: {e}")
        capture_exception(e)
