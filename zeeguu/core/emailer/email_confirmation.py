from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer


def send_email_confirmation(to_email, code):
    body = "\r\n".join([
        "Hi there,",
        " ",
        "Please use this code to confirm your email: " + str(code) + ".",
        " ",
        "Cheers,",
        "The Zeeguu Team"
    ])

    emailer = ZeeguuMailer('Confirm your email', body, to_email)
    emailer.send()


def send_email_changed_notice(old_email, new_email):
    body = "\r\n".join([
        "Hi there,",
        " ",
        "The email address of your Zeeguu account was just changed to " + new_email + ".",
        "From now on, log in with that address.",
        " ",
        "If you did not do this, reply to this email and we will help you get your account back.",
        " ",
        "Cheers,",
        "The Zeeguu Team"
    ])

    emailer = ZeeguuMailer('Your Zeeguu email address was changed', body, old_email)
    emailer.send()
