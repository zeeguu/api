from zeeguu.core.model import User
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer

cheers_your_server = "\n\rCheers,\n\rYour Zeeguu Server ;)"


def send_new_user_account_email(username, invite_code="", cohort=""):
    ZeeguuMailer.send_mail(
        f"New Account: {username}",
        [f"Code: {invite_code} Class: {cohort}", cheers_your_server],
    )


def send_notification_article_feedback(
    feedback, user: User, article_title, article_url, article_id
):
    def detailed_article_info(user, article_id):
        info = "==Translations\n\n"

        bookmarks = user.bookmarks_for_article(
            article_id, with_context=True, with_title=True
        )

        for each in bookmarks:
            info += f"{each.origin.word} = {each.translation.word}"

        return info

    content_lines = feedback
    content_lines += detailed_article_info(user, article_id)
    content_lines += f"Detailed User Translations: https://www.zeeguu.org/bookmarks_for_article/{article_id}/{user.id}"
    content_lines += cheers_your_server

    ZeeguuMailer.send_mail(f"{user.name} - {article_title}", content_lines)
