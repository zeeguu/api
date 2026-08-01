from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from zeeguu.core.model.user import User
from zeeguu.core.model.user_preference import UserPreference
from zeeguu.core.model.shared_article import SharedArticle
from zeeguu.logging import log

WEB_URL = "https://zeeguu.org"

# Collapse a burst of shares to the same recipient into one email: a share is
# only skipped if an earlier one reached them within this window. Generous
# enough to cover a deliberate "share a few articles in one sitting" session,
# short enough that a genuinely later share re-notifies.
SHARE_EMAIL_DEBOUNCE_MINUTES = 10


def send_shared_article_notification(to_user_id, from_user_id, shared_article_id):
    """Email the recipient that a friend shared an article. Best-effort; meant to
    run off the request thread via run_in_background (re-fetches everything by id).

    Temporal debounce (no cron, no extra state): collapse a *burst* of shares to
    the same recipient into one email, while still notifying a genuinely new
    share later. We suppress only if an earlier share reached this recipient
    within the last SHARE_EMAIL_DEBOUNCE_MINUTES — unlike the old count-based
    rule, a single un-opened share no longer silences all future notifications.

    Globally gated by EMAIL_SENDING_ENABLED (checked inside ZeeguuMailer.send —
    the env-level "send real email at all" switch), and per-user by the
    EMAIL_ON_ARTICLE_SHARED preference.
    """
    try:
        recipient = User.find_by_id(to_user_id)
        if not recipient or not recipient.email:
            return
        if not UserPreference.is_email_on_article_shared_enabled(recipient):
            return

        sharer = User.find_by_id(from_user_id)
        shared = SharedArticle.find_by_id(shared_article_id)
        if not shared:
            return

        # Collapse a burst: skip the email if an earlier share reached this
        # recipient in the debounce window (that one already notified them).
        if SharedArticle.has_earlier_recent_share_to(
            to_user_id, shared.id, within_minutes=SHARE_EMAIL_DEBOUNCE_MINUTES
        ):
            return

        # Prefer the recipient's personalized copy: its title is in *their*
        # language (so a cross-language share isn't a foreign headline), and its
        # id deep-links straight to their adapted read. Fall back to the
        # canonical article if the derivative isn't there (plain crawl / failed).
        display_article = shared.delivery_article or shared.article
        article_title = display_article.title if display_article else "an article"
        open_id = shared.delivery_article_id or shared.article_id
        lang_clause = (
            f" in {shared.delivery_language.name}" if shared.delivery_language else ""
        )

        subject = f"{sharer.name} shared an article with you on Zeeguu"

        lines = [
            f"Hi {recipient.name},",
            "",
            f"{sharer.name} shared the following article with you:",
            "",
            f"“{article_title}”",
        ]
        if shared.note:
            lines += ["", f"Their note: “{shared.note}”"]
        lines += [
            "",
            f"We've prepared it for you{lang_clause}, at your level — open it here:",
            f"{WEB_URL}/read/article?id={open_id}&shared={shared.id}",
            "",
            "You'll also find any other articles friends have sent you",
            f"in your Shared inbox: {WEB_URL}/articles/shared",
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
