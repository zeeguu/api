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
        )
        new_session = Session.create_for_user(new_user)
        db_session.add(new_session)
        db_session.commit()
        return new_session.uuid

    except Exception as e:
        log(f"Attemt to create user failed: {username} {password} {email}")
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

    try:
        new_user = create_basic_account(
            db_session, username, password, invite_code, email
        )
        new_session = Session.create_for_user(new_user)
        db_session.add(new_session)
        db_session.commit()
        return str(new_session.id)

    except Exception as e:
        log(f"Attemt to create user failed: {username} {password} {email}")
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

    # These two are optional
    language_code = request.form.get("learned_language_code", None)
    native_code = request.form.get("native_language_code", None)

    try:
        new_user = User.create_anonymous(uuid, password, language_code, native_code)
        db_session.add(new_user)
        db_session.commit()
    except ValueError as e:
        return bad_request("Could not create anon user.")
    except sqlalchemy.exc.IntegrityError as e:
        return bad_request("Could not create anon user. Maybe uuid already exists?")
    return get_anon_session(uuid)


@api.route("/send_code/<email>", methods=["POST"])
@cross_domain
def send_code(email):
    """
    This endpoint generates a unique code that will be used to allow
    the user to change his/her password. The unique code is send to
    the specified email address.
    """
    from zeeguu.core.emailer.password_reset import send_password_reset_email

    try:
        User.find(email)
    except sqlalchemy.orm.exc.NoResultFound:
        return bad_request("Email unknown")

    code = UniqueCode(email)
    db_session.add(code)
    db_session.commit()

    send_password_reset_email(email, code)

    return "OK"


@api.route("/reset_password/<email>", methods=["POST"])
@cross_domain
def reset_password(email):
    from zeeguu.logging import log
    
    log(f"PASSWORD RESET ATTEMPT: email='{email}'")
    
    code = request.form.get("code", None)
    submitted_pass = request.form.get("password", None)

    user = User.find(email)
    last_code = UniqueCode.last_code(email)

    if submitted_code_is_wrong(last_code, code):
        log(f"PASSWORD RESET FAILED: email='{email}' - Invalid code")
        return bad_request("Invalid code")
    if password_is_too_short(submitted_pass):
        log(f"PASSWORD RESET FAILED: email='{email}' - Password too short")
        return bad_request("Password is too short")
    if user is None:
        log(f"PASSWORD RESET FAILED: email='{email}' - Email unknown")
        return bad_request("Email unknown")

    log(f"PASSWORD RESET: email='{email}', user_id={user.id} - Updating password")
    user.update_password(submitted_pass)
    delete_all_codes_for_email(email)

    db_session.commit()
    
    log(f"PASSWORD RESET SUCCESS: email='{email}', user_id={user.id} - Password updated successfully")
    return "OK"


def bad_request(msg):
    return make_error(400, msg)


def submitted_code_is_wrong(submitted_code, db_code):
    return submitted_code != db_code


def password_is_too_short(password):
    return len(password) < 4


def delete_all_codes_for_email(email):
    for x in UniqueCode.all_codes_for(email):
        db_session.delete(x)
