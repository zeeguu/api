from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer


def send_password_reset_email(to_email, code):
    body = "\r\n".join([
        "Hi there,",
        " ",
        "Please use this code to reset your password: " + str(code) + ".",
        " ",
        "Cheers,",
        "The Zeeguu Team"
    ])

    emailer = ZeeguuMailer('Reset your password', body, to_email)
    emailer.send()