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
