import hmac
import sqlalchemy
import flask

from flask import request
from zeeguu.core.model import Session
from zeeguu.core.model import User
from zeeguu.core.model.unique_code import UniqueCode
from zeeguu.api.endpoints.sessions import get_anon_session
from zeeguu.api.utils.abort_handling import make_error

from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from . import api, db_session

from zeeguu.logging import log


@api.route("/delete_user", methods=["POST"])
@cross_domain
@requires_session
def remove_user():
    from zeeguu.core.account_management.user_account_deletion import (
        delete_user_account_w_session,
    )

    try:
        delete_user_account_w_session(db_session, flask.g.session_uuid)
        return "OK"

    except Exception as e:
        from zeeguu.logging import print_and_log_to_sentry

        print_and_log_to_sentry(e)
        log(f"Attempt to delete user failed with session: '{flask.g.session_uuid}'")
        return make_error(400, str(e))


@api.route("/add_user/<email>", methods=["POST"])
@cross_domain
def add_user(email):
    """
    Creates user, then returns a session for that user
    """

    password = request.form.get("password")
    username = request.form.get("username")
    learned_language_code = request.form.get(
        "learned_language", "de"
    )  # default language; it's changed by the ui later
    native_language_code = request.form.get(
        "native_language", "en"
    )  # default language; it's changed by the ui later
    learned_cefr_level = request.form.get("learned_cefr_level", 0)
    invite_code = request.form.get("invite_code")
    platform = request.form.get("platform")

    from zeeguu.core.account_management.user_account_creation import create_account

    try:
        new_user = create_account(
            db_session,
            username,
            password,
            invite_code,
            email,
            learned_language_code,
            native_language_code,
            learned_cefr_level,
            creation_platform=platform,
        )
        new_session = Session.create_for_user(new_user)
        db_session.add(new_session)
        db_session.commit()
        return new_session.uuid

    except Exception as e:
        log(f"Account creation failed for email: {email}")
        log(e)
        return make_error(400, str(e))


@api.route("/add_basic_user/<email>", methods=["POST"])
@cross_domain
def add_basic_user(email):
    """
    Creates user, then returns a session for that user
    """

    from ...core.account_management.user_account_creation import create_basic_account

    password = request.form.get("password")
    username = request.form.get("username")
    invite_code = request.form.get("invite_code")
    platform = request.form.get("platform")

    try:
        new_user = create_basic_account(
            db_session, username, password, invite_code, email, creation_platform=platform
        )
        new_session = Session.create_for_user(new_user)
        db_session.add(new_session)
        db_session.commit()
        return str(new_session.id)

    except Exception as e:
        log(f"Basic account creation failed for email: {email}")
        log(e)
        return make_error(400, str(e))


@api.route("/add_anon_user", methods=["POST"])
@cross_domain
def add_anon_user():
    """

    Creates anonymous user, then redirects to the get_session
    endpoint. Returns a session

    """

    # These two are post parameters required by the method
    uuid = request.form.get("uuid", None)
    password = request.form.get("password", None)

    # These are optional
    language_code = request.form.get("learned_language_code", None)
    native_code = request.form.get("native_language_code", None)
    cefr_level = request.form.get("learned_cefr_level", None)
    platform = request.form.get("platform", None)

    try:
        new_user = User.create_anonymous(uuid, password, language_code, native_code, creation_platform=platform)
        db_session.add(new_user)
        db_session.commit()

        # Create UserLanguage record with CEFR level if provided
        if language_code and cefr_level:
            new_user.set_learned_language(language_code, int(cefr_level), db_session)
            db_session.commit()
    except ValueError as e:
        return bad_request("Could not create anon user.")
    except sqlalchemy.exc.IntegrityError as e:
        return bad_request("Could not create anon user. Maybe uuid already exists?")
    return get_anon_session(uuid)


@api.route("/upgrade_anon_user", methods=["POST"])
@cross_domain
@requires_session
def upgrade_anon_user():
    """
    Upgrade an anonymous account to a full account with email/username.
    Requires an active session from an anonymous user.
    Sends a confirmation email with a code.
    """
    from zeeguu.core.emailer.email_confirmation import send_email_confirmation

    email = request.form.get("email", None)
    username = request.form.get("username", None)
    password = request.form.get("password", None)  # Optional - keeps existing if not provided

    if not email or not username:
        return bad_request("Email and username are required")

    try:
        user = User.find_by_id(flask.g.user_id)
        user.upgrade_to_full_account(email, username, password)
        user.email_verified = False  # Requires confirmation
        db_session.commit()

        # Send confirmation email
        code = UniqueCode(email)
        db_session.add(code)
        db_session.commit()
        send_email_confirmation(email, code)

        return "OK"

    except ValueError as e:
        return bad_request(str(e))
    except Exception as e:
        log(f"Failed to upgrade anonymous user: {e}")
        return bad_request("Could not upgrade account")


@api.route("/confirm_email", methods=["POST"])
@cross_domain
@requires_session
def confirm_email():
    """
    Confirm email address using the code sent via email.
    """
    code = request.form.get("code", None)

    if not code:
        return bad_request("Code is required")

    try:
        user = User.find_by_id(flask.g.user_id)
        last_code = UniqueCode.last_code(user.email)

        if str(last_code) != str(code):
            return bad_request("Invalid code")

        user.email_verified = True
        # Clean up codes
        for c in UniqueCode.all_codes_for(user.email):
            db_session.delete(c)
        db_session.commit()

        return "OK"

    except Exception as e:
        log(f"Failed to confirm email: {e}")
        return bad_request("Could not confirm email")


@api.route("/send_code/<email>", methods=["POST"])
@cross_domain
def send_code(email):
    """
    This endpoint generates a unique code that will be used to allow
    the user to change his/her password. The unique code is send to
    the specified email address.

    Security: Always returns OK to prevent user enumeration.
    """
    from zeeguu.core.emailer.password_reset import send_password_reset_email

    try:
        User.find(email)
        # Only send email and create code if user exists
        code = UniqueCode(email)
        db_session.add(code)
        db_session.commit()
        send_password_reset_email(email, code)
    except sqlalchemy.orm.exc.NoResultFound:
        # Silently ignore non-existent emails to prevent user enumeration
        # Don't reveal whether the email exists in our system
        log(f"PASSWORD RESET: Attempted reset for non-existent email (not revealing to client)")
        pass

    # Always return OK to prevent user enumeration
    return "OK"


@api.route("/reset_password/<email>", methods=["POST"])
@cross_domain
def reset_password(email):
    from zeeguu.logging import log

    log(f"PASSWORD RESET ATTEMPT: email='{email}'")

    code = request.form.get("code", None)
    submitted_pass = request.form.get("password", None)

    # Security: Use generic error messages to prevent information disclosure
    code_obj = UniqueCode.find_last_code(email)

    if code_obj is None:
        log(f"PASSWORD RESET FAILED: email='{email}' - No reset code found")
        return bad_request("Invalid or expired code")
    if code_obj.is_expired():
        log(f"PASSWORD RESET FAILED: email='{email}' - Code expired")
        return bad_request("Invalid or expired code")
    if submitted_code_is_wrong(code_obj.code, code):
        log(f"PASSWORD RESET FAILED: email='{email}' - Invalid code")
        return bad_request("Invalid or expired code")
    if password_is_too_short(submitted_pass):
        log(f"PASSWORD RESET FAILED: email='{email}' - Password too short")
        return bad_request("Password is too short")

    try:
        user = User.find(email)
    except sqlalchemy.orm.exc.NoResultFound:
        log(f"PASSWORD RESET FAILED: email='{email}' - Email unknown")
        return bad_request("Invalid or expired code")

    log(f"PASSWORD RESET: email='{email}', user_id={user.id} - Updating password")
    user.update_password(submitted_pass)
    delete_all_codes_for_email(email)

    db_session.commit()

    log(f"PASSWORD RESET SUCCESS: email='{email}', user_id={user.id} - Password updated successfully")
    return "OK"


def bad_request(msg):
    return make_error(400, msg)


def submitted_code_is_wrong(submitted_code, db_code):
    # Use constant-time comparison to prevent timing attacks
    if submitted_code is None or db_code is None:
        return True
    return not hmac.compare_digest(str(submitted_code), str(db_code))


def password_is_too_short(password):
    return len(password) < 4


def delete_all_codes_for_email(email):
    for x in UniqueCode.all_codes_for(email):
        db_session.delete(x)
