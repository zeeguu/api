import sqlalchemy
from sqlalchemy import func

import zeeguu.core
from zeeguu.core.emailer.user_activity import send_new_user_account_email
from zeeguu.core.emailer.email_confirmation import send_email_confirmation
from zeeguu.core.model import Cohort, User, Teacher, Language, UserLanguage
from zeeguu.core.model.unique_code import UniqueCode
from zeeguu.logging import log


def _normalize_username(username):
    return username.strip() if username else username


def valid_invite_code(invite_code):
    # Allow empty invite codes (for App Store / open signups)
    if not invite_code or invite_code.strip() == "":
        return True

    if zeeguu.core.app.config["TESTING"]:
        return True

    config_codes = zeeguu.core.app.config.get("INVITATION_CODES")
    if config_codes and invite_code.lower() in [c.lower() for c in config_codes]:
        return True

    if Cohort.exists_with_invite_code(invite_code):
        return True

    return False


# TODO: delete after the new onboarding of Iga is done
def create_account(
    db_session,
    username,
    password,
    invite_code,
    email,
    learned_language_code,
    native_language_code,
    learned_cefr_level,
    creation_platform=None,
):
    cohort_name = ""
    if password is None or len(password) < 4:
        raise Exception("Password should be at least 4 characters long")

    if not valid_invite_code(invite_code):
        raise Exception("Invitation code is not recognized. Please contact us.")

    normalized_username = _normalize_username(username)
    if User.username_exists(normalized_username):
        raise Exception("Username already in use")

    cohort = (
        Cohort.query.filter(func.lower(Cohort.inv_code) == invite_code.lower()).first()
        if invite_code
        else None
    )
    if cohort:
        if cohort.cohort_still_has_capacity():
            cohort_name = cohort.name
        else:
            raise Exception(
                "No more places in this class. Please contact us (zeeguu.team@gmail.com)."
            )

    try:
        learned_language = Language.find_or_create(learned_language_code)
        native_language = Language.find_or_create(native_language_code)
        new_user = User(
            email,
            username,
            password,
            username=normalized_username,
            invitation_code=invite_code,
            learned_language=learned_language,
            native_language=native_language,
            creation_platform=creation_platform,
        )
        new_user.email_verified = False  # Require email verification
        db_session.add(new_user)
        if cohort_name != "":
            new_user.add_user_to_cohort(cohort, db_session)
        new_user.create_default_user_preference()
        learned_language = UserLanguage.find_or_create(
            db_session, new_user, learned_language
        )
        learned_language.cefr_level = int(learned_cefr_level)
        learned_language.declared_level_min = 0
        learned_language.declared_level_max = 11

        db_session.add(learned_language)

        if cohort and cohort.is_cohort_of_teachers:
            teacher = Teacher(new_user)
            db_session.add(teacher)

        db_session.commit()

        send_new_user_account_email(username, invite_code, cohort_name)

        code = UniqueCode(email)
        db_session.add(code)
        db_session.commit()
        log(f"EMAIL VERIFICATION CODE for {email}: {code.code}")
        send_email_confirmation(email, code)

        return new_user

    except sqlalchemy.exc.IntegrityError:
        raise Exception("There is already an account for this email.")
    except Exception as e:
        print(e)
        raise Exception("Could not create the account")


def create_basic_account(
    db_session, username, password, invite_code, email, creation_platform=None
):
    cohort_name = ""
    if password is None or len(password) < 4:
        raise Exception("Password should be at least 4 characters long")

    if not valid_invite_code(invite_code):
        raise Exception("Invitation code is not recognized. Please contact us.")

    normalized_username = _normalize_username(username)
    if User.username_exists(normalized_username):
        raise Exception("Username already in use")

    cohort = (
        Cohort.query.filter(func.lower(Cohort.inv_code) == invite_code.lower()).first()
        if invite_code
        else None
    )
    if cohort:
        if cohort.cohort_still_has_capacity():
            cohort_name = cohort.name
        else:
            raise Exception(
                "No more places in this class. Please contact us (zeeguu.team@gmail.com)."
            )

    try:
        new_user = User(
            email,
            username,
            password,
            username=normalized_username,
            invitation_code=invite_code,
            creation_platform=creation_platform,
        )
        new_user.email_verified = False  # Require email verification

        db_session.add(new_user)

        if cohort and cohort.is_cohort_of_teachers:
            teacher = Teacher(new_user)
            db_session.add(teacher)

        db_session.commit()

        send_new_user_account_email(username, invite_code, cohort_name)

        code = UniqueCode(email)
        db_session.add(code)
        db_session.commit()
        log(f"EMAIL VERIFICATION CODE for {email}: {code.code}")
        send_email_confirmation(email, code)

        return new_user

    except sqlalchemy.exc.IntegrityError:
        raise Exception("There is already an account for this email.")
    except Exception as e:
        print(e)
        raise Exception("Could not create the account")
