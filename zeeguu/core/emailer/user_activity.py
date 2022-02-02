from zeeguu.core.model import User
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from zeeguu.core.model.user_activitiy_data import UserActivityData

cheers_your_server = "\n\rCheers,\n\rYour Zeeguu Server ;)"


def send_new_user_account_email(username, invite_code="", cohort=""):
    ZeeguuMailer.send_mail(
        f"New Account: {username}",
        [f"Code: {invite_code} Class: {cohort}", cheers_your_server],
    )


def send_notification_article_feedback(
    feedback, user: User, article_title, article_url, article_id
):
    from datetime import datetime as dt

    def detailed_article_info(stream, user, article_id):

        bookmarks = user.bookmarks_for_article(
            article_id, with_context=True, with_title=True, json=False
        )

        stream.append(f"\n\n{len(bookmarks)} Translations:\n")

        for each in bookmarks:
            stream.append(f"- {each.origin.word} => {each.translation.word}")

        # user activity data
        stream.append("\n\nUser Interactions:\n")
        events = UserActivityData.find(article_id=article_id)
        prev_short_time = ""
        for event in events:
            short_time = dt.strftime(event.time, "%H:%M")
            event_name = event.event.replace("UMR - ", "")
            if short_time != prev_short_time:
                stream.append(f"  {short_time} {event_name.lower()} {event.value}")
            else:
                stream.append(f"       {event_name.lower()} {event.value}")
            if event_name == "ARTICLE LOST FOCUS":
                stream.append("")

            prev_short_time = short_time

        stream.append("\n\n")

    content_lines = [feedback]
    detailed_article_info(content_lines, user, article_id)

    content_lines.append(
        f"\n\nDetailed User Translations: https://www.zeeguu.org/bookmarks_for_article/{article_id}/{user.id}"
    )
    content_lines.append(cheers_your_server)

    ZeeguuMailer.send_mail(f"{user.name} - {article_title}", content_lines)
