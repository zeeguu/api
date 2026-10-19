from zeeguu.api.test.fixtures import logged_in_client as client
from zeeguu.core.model import UniqueCode, User
from zeeguu.core.model.db import db

NEW_EMAIL = "new.address@school.nl"
PASSWORD = "test"  # LoggedInClient's


def _request(client, new_email=NEW_EMAIL, password=PASSWORD):
    return client.response_from_post(
        "/request_email_change", data=dict(new_email=new_email, password=password)
    )


def _confirm(client, code, new_email=NEW_EMAIL, password=PASSWORD):
    return client.response_from_post(
        "/confirm_email_change",
        data=dict(new_email=new_email, password=password, code=code),
    )


def _mailed_code(email=NEW_EMAIL):
    return UniqueCode.last_code(email, UniqueCode.CHANGE_EMAIL)


def test_change_email_with_the_code_mailed_to_the_new_address(client):
    assert _request(client).status_code == 200

    response = _confirm(client, _mailed_code())

    assert response.status_code == 200
    user = User.find(NEW_EMAIL)
    assert user.email_verified
    assert UniqueCode.all_codes_for(NEW_EMAIL) == []
    # still logged in: the session belongs to the account, not the address
    assert client.get("/get_user_details")["email"] == NEW_EMAIL


def test_request_changes_nothing_until_confirmed(client):
    _request(client)
    assert User.find(client.email)
    assert not User.email_exists(NEW_EMAIL)


def test_new_address_is_normalised(client):
    _request(client, new_email="  New.Address@School.NL ")
    assert _confirm(client, _mailed_code(), new_email="New.Address@School.NL").status_code == 200
    assert User.email_exists(NEW_EMAIL)


def test_wrong_password_is_refused_on_request(client):
    assert _request(client, password="nope").status_code == 400
    assert _mailed_code() is None


def test_wrong_password_is_refused_on_confirm(client):
    # The code only proves the inbox; the password is checked again here.
    code = UniqueCode(NEW_EMAIL, UniqueCode.CHANGE_EMAIL)
    db.session.add(code)
    db.session.commit()

    assert _confirm(client, code.code, password="nope").status_code == 400
    assert User.find(client.email)


def test_wrong_code_is_refused(client):
    _request(client)
    wrong = "0000" if _mailed_code() != "0000" else "1111"
    assert _confirm(client, wrong).status_code == 400
    assert not User.email_exists(NEW_EMAIL)


def test_a_code_minted_for_another_purpose_is_refused(client):
    # /request_email_verification mints a verify code for any unused address
    # to any session; it must not work here.
    code = UniqueCode(NEW_EMAIL, UniqueCode.VERIFY)
    db.session.add(code)
    db.session.commit()

    assert _confirm(client, code.code).status_code == 400
    assert not User.email_exists(NEW_EMAIL)


def test_address_of_another_account_is_refused(client):
    client.client.post("/add_user/taken@school.nl", data=dict(username="other", password="pass1234"))

    response = _request(client, new_email="taken@school.nl")

    assert response.status_code == 400
    assert "already in use" in response.json["message"]


def test_address_taken_between_request_and_confirm_is_refused(client):
    _request(client)
    code = _mailed_code()
    client.client.post(f"/add_user/{NEW_EMAIL}", data=dict(username="fast", password="pass1234"))

    assert _confirm(client, code).status_code == 400
    assert User.find(client.email)


def test_unverified_user_can_fix_a_mistyped_address(client):
    user = User.find(client.email)
    user.email_verified = False
    db.session.commit()

    assert _request(client).status_code == 200
    assert _confirm(client, _mailed_code()).status_code == 200
    assert User.find(NEW_EMAIL).email_verified


def test_existing_endpoints_are_untouched(client):
    # Native builds freeze the wire: the new flow adds endpoints, renames none.
    for endpoint in ("/confirm_email", "/resend_verification_code", "/request_email_verification"):
        assert client.response_from_post(endpoint).status_code != 404


def test_user_settings_still_accepts_the_unchanged_email(client):
    # Every client posts its whole user-details object back, email included;
    # installed app builds will keep doing that.
    response = client.response_from_post(
        "/user_settings", data=dict(email=client.email.upper(), name="Renamed")
    )
    assert response.status_code == 200
    assert User.find(client.email).name == "Renamed"


def test_user_settings_no_longer_changes_the_email_unverified(client):
    response = client.response_from_post("/user_settings", data=dict(email=NEW_EMAIL))

    assert response.status_code == 400
    assert "Change email" in response.json["message"]
    assert not User.email_exists(NEW_EMAIL)
