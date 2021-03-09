from zeeguu_core.model import User
from zeeguu_core.emailer.zeeguu_mailer import ZeeguuMailer

cheers_your_server = '\n\rCheers,\n\rYour Zeeguu Server ;)'


def send_new_user_account_email(username, invite_code='', cohort=''):
    ZeeguuMailer.send_mail(
        f'New Account: {username}',
        [
            f'Code: {invite_code} Class: {cohort}',
            cheers_your_server
        ])


def send_notification_article_feedback(feedback, user: User, article_title, article_url, article_id):
    cohort_id = user.cohort_id or 0

    content_lines = [
        f'{feedback}',
        f'User Translations: https://www.zeeguu.org/bookmarks_for_article/{article_id}/{user.id}',
        cheers_your_server
    ]

    ZeeguuMailer.send_mail(f'{user.name} - {article_title}', content_lines)
