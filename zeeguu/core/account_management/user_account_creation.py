import sqlalchemy

import zeeguu.core
from zeeguu.core.emailer.user_activity import send_new_user_account_email
from zeeguu.core.model import Cohort, User, Teacher, Language, UserLanguage


def valid_invite_code(invite_code):
    if zeeguu.core.app.config["TESTING"]:
        return True

    if zeeguu.core.app.config.get(
            "INVITATION_CODES"
    ) and invite_code in zeeguu.core.app.config.get("INVITATION_CODES"):
        return True

    if Cohort.exists_with_invite_code(invite_code):
        return True

    return False


def create_account(
        db_session,
        username,
        password,
        invite_code,
        email,
        learned_language_code,
        native_language_code,
        learned_cefr_level,
):
    cohort_name = ""
    if password is None or len(password) < 4:
        raise Exception("Password should be at least 4 characters long")

    if not valid_invite_code(invite_code):
        raise Exception("Invitation code is not recognized. Please contact us.")

    cohort = Cohort.query.filter_by(inv_code=invite_code).first()
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
            invitation_code=invite_code,
            cohort=cohort,
            learned_language=learned_language,
            native_language=native_language,
        )

        db_session.add(new_user)

        learned_language = UserLanguage.find_or_create(
            db_session, new_user, learned_language
        )
        learned_language.cefr_level = int(learned_cefr_level)
        # TODO: although these are required... they should simply
        # be functions of CEFR level so at some further point should
        # removed
        learned_language.declared_level_min = 0
        learned_language.declared_level_max = 11

        db_session.add(learned_language)

        if cohort:
            if cohort.is_cohort_of_teachers:
                teacher = Teacher(new_user)
                db_session.add(teacher)

        db_session.commit()

        send_new_user_account_email(username, invite_code, cohort_name)

        return new_user

    except sqlalchemy.exc.IntegrityError:
        raise Exception("There is already an account for this email.")
    except Exception as e:
        print(e)
        raise Exception("Could not create the account")
