import sqlalchemy

import zeeguu.core
from zeeguu.core.emailer.user_activity import send_new_user_account_email
from zeeguu.core.model.cohort import Cohort
from zeeguu.core.model.language import Language
from zeeguu.core.model.teacher import Teacher
from zeeguu.core.model.user import User
from zeeguu.core.model.user_language import UserLanguage


def valid_invite_code(user_provided_invite_code):
    if zeeguu.core.app.config["TESTING"]:
        return True

    invitation_codes = zeeguu.core.app.config.get("INVITATION_CODES")
    if invitation_codes:
        # Make invite code validation case-insensitive
        invite_code_lower = user_provided_invite_code.lower()
        for valid_code in invitation_codes:
            if invite_code_lower == valid_code.lower():
                return True

    if Cohort.exists_with_invite_code(user_provided_invite_code):
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
):
    cohort_name = ""
    if password is None or len(password) < 4:
        raise Exception("Password should be at least 4 characters long")

    if not valid_invite_code(invite_code):
        raise Exception("Invitation code is not recognized. Please contact us.")

    # Case-insensitive search for cohort
    from sqlalchemy import func

    cohort = Cohort.query.filter(
        func.lower(Cohort.inv_code) == func.lower(invite_code)
    ).first()
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
            learned_language=learned_language,
            native_language=native_language,
        )
        db_session.add(new_user)
        if cohort_name != "":
            new_user.add_user_to_cohort(cohort, db_session)
        new_user.create_default_user_preference()
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


def create_basic_account(db_session, username, password, invite_code, email):
    cohort_name = ""
    if password is None or len(password) < 4:
        raise Exception("Password should be at least 4 characters long")

    if not valid_invite_code(invite_code):
        raise Exception("Invitation code is not recognized. Please contact us.")

    # Case-insensitive search for cohort
    from sqlalchemy import func

    cohort = Cohort.query.filter(
        func.lower(Cohort.inv_code) == func.lower(invite_code)
    ).first()
    if cohort:
        if cohort.cohort_still_has_capacity():
            cohort_name = cohort.name
        else:
            raise Exception(
                "No more places in this class. Please contact us (zeeguu.team@gmail.com)."
            )

    try:
        new_user = User(
            email, username, password, invitation_code=invite_code, cohort=cohort
        )

        db_session.add(new_user)
        if "merle" in invite_code.lower():
            new_user.create_default_user_preference()

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
