import sqlalchemy
from sqlalchemy import func

import zeeguu.core
from zeeguu.core.model.user_avatar import UserAvatar
from zeeguu.core.emailer.user_activity import send_new_user_account_email
from zeeguu.core.emailer.email_confirmation import send_email_confirmation
from zeeguu.core.model import Cohort, User, Teacher, Language, UserLanguage
from zeeguu.core.model.unique_code import UniqueCode
from zeeguu.logging import log


# How many times to retry the User INSERT when the username UNIQUE constraint
# fires because of a concurrent signup. See _commit_new_user_with_retry.
_USERNAME_RETRY_ATTEMPTS = 3


def _commit_new_user_with_retry(db_session, build_user, extra_adds=None):
    """
    Add and commit a new User row, retrying with a freshly-generated username
    on username UNIQUE collisions.

    Background: User.generate_unique_username() does a SELECT before returning
    to check that its pick is free, but there is a microscopic window between
    that check and the commit during which a concurrent signup could grab the
    same name. At current signup volume (~20/month) this is near-zero, but the
    cost of hardening is a tight loop around build+commit.

    Email collisions are NOT retried — a duplicate email indicates a real
    conflict, not a transient race, and re-generating a username won't help.

    Args:
        build_user: zero-arg callable returning (new_user, animal). Called
            fresh each attempt so the username is regenerated.
        extra_adds: optional callable taking `new_user` that adds sibling
            rows (e.g. Teacher) to the same transaction.

    Returns:
        (new_user, animal) once the commit succeeds.

    Raises:
        sqlalchemy.exc.IntegrityError if the email is the real conflict, or
        after _USERNAME_RETRY_ATTEMPTS collisions in a row.
    """
    last_error = None
    for _ in range(_USERNAME_RETRY_ATTEMPTS):
        # Capture the email up-front: if an IntegrityError fires from inside
        # extra_adds (some helpers like add_user_to_cohort and
        # UserLanguage.find_or_create commit internally, so the race can
        # materialize before our own commit() line), we still need to know
        # what email we were trying to register.
        attempted_email = None
        try:
            new_user, animal = build_user()
            attempted_email = new_user.email
            db_session.add(new_user)
            if extra_adds is not None:
                extra_adds(new_user)
            db_session.commit()
            return new_user, animal
        except sqlalchemy.exc.IntegrityError as e:
            db_session.rollback()
            last_error = e
            # Re-checking email_exists (rather than parsing the driver error)
            # keeps this portable across MySQL driver versions.
            if attempted_email is not None and User.email_exists(attempted_email):
                raise
            # Otherwise assume it's the username UNIQUE and loop.
    raise last_error


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
    username, # TODO: this should be name (and add username too)
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

    # TODO Implement this when username is implemented
    # normalized_username = _normalize_username(username)
    # if normalized_username and len(normalized_username) > 50:
    #     raise Exception("Username can be at most 50 characters")
    # if User.username_exists(normalized_username):
    #     raise Exception("Username already in use")

    if User.email_exists(email):
        raise Exception("There is already an account for this email.")

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

        def build_user():
            generated_username, animal = User.generate_unique_username()
            user = User(
                email,
                username,
                password,
                username=generated_username,
                invitation_code=invite_code,
                learned_language=learned_language,
                native_language=native_language,
                creation_platform=creation_platform,
            )
            user.email_verified = False  # Require email verification
            return user, animal

        def add_siblings(user):
            if cohort_name != "":
                user.add_user_to_cohort(cohort, db_session)
            user.create_default_user_preference()
            user_language = UserLanguage.find_or_create(db_session, user, learned_language)
            user_language.cefr_level = int(learned_cefr_level)
            user_language.declared_level_min = 0
            user_language.declared_level_max = 11
            db_session.add(user_language)
            if cohort and cohort.is_cohort_of_teachers:
                db_session.add(Teacher(user))

        new_user, animal = _commit_new_user_with_retry(db_session, build_user, add_siblings)

        # TODO Only run this if username is not provided, but rather auto-generated. Implement it when username is implemented
        character_color, background_color = UserAvatar.random_colors()
        user_avatar = UserAvatar(new_user.id, animal, character_color, background_color)
        db_session.add(user_avatar)

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

    # TODO: Implement this when username is implemented
    # normalized_username = _normalize_username(username)
    # if User.username_exists(normalized_username):
    #     raise Exception("Username already in use")

    if User.email_exists(email):
        raise Exception("There is already an account for this email.")

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
        def build_user():
            generated_username, animal = User.generate_unique_username()
            user = User(
                email,
                username,
                password,
                generated_username,
                invitation_code=invite_code,
                creation_platform=creation_platform,
            )
            user.email_verified = False  # Require email verification
            return user, animal

        def add_siblings(user):
            if cohort and cohort.is_cohort_of_teachers:
                db_session.add(Teacher(user))

        new_user, animal = _commit_new_user_with_retry(db_session, build_user, add_siblings)

        # TODO Only run this if username is not provided, but rather auto-generated. Implement it when username is implemented
        character_color, background_color = UserAvatar.random_colors()
        user_avatar = UserAvatar(new_user.id, animal, character_color, background_color)
        db_session.add(user_avatar)

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
