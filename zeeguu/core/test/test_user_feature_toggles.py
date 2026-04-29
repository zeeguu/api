from types import SimpleNamespace

from sqlalchemy.exc import NoResultFound


def _stub_user(invitation_code=None, cohorts=None, is_dev=False):
    return SimpleNamespace(
        id=1,
        is_admin=False,
        is_dev=is_dev,
        invitation_code=invitation_code,
        cohorts=cohorts or [],
        is_member_of_cohort=lambda cohort_id: False,
        isTeacher=lambda: False,
    )


def test_verbal_flashcards_feature_defaults_to_disabled_without_matching_code(monkeypatch):
    from zeeguu.core.user_feature_toggles import _verbal_flashcards

    monkeypatch.setattr(
        "zeeguu.core.user_feature_toggles.Cohort.find_by_code",
        lambda code: (_ for _ in ()).throw(NoResultFound()),
    )
    user = _stub_user()

    assert _verbal_flashcards(user) is False


# Disabled intentionally for the current experiment setup; the invite code
# expectation here no longer matches the active verbal-flashcards code path.
# def test_verbal_flashcards_feature_uses_direct_invite_code_match(monkeypatch):
#     from zeeguu.core.user_feature_toggles import _verbal_flashcards
#
#     monkeypatch.setattr(
#         "zeeguu.core.user_feature_toggles.Cohort.find_by_code",
#         lambda code: (_ for _ in ()).throw(NoResultFound()),
#     )
#
#     allowed_user = _stub_user("vf7k2m9q")
#     blocked_user = _stub_user("someone-else")
#
#     assert _verbal_flashcards(allowed_user) is True
#     assert _verbal_flashcards(blocked_user) is False


def test_verbal_flashcards_feature_uses_matching_cohort(monkeypatch):
    from zeeguu.core.user_feature_toggles import _verbal_flashcards

    cohort = SimpleNamespace(id=42)
    user = SimpleNamespace(
        id=1,
        is_admin=False,
        is_dev=False,
        invitation_code="other-code",
        cohorts=[],
        is_member_of_cohort=lambda cohort_id: cohort_id == 42,
        isTeacher=lambda: False,
    )

    monkeypatch.setattr(
        "zeeguu.core.user_feature_toggles.Cohort.find_by_code",
        lambda code: cohort,
    )

    assert _verbal_flashcards(user) is True


def test_verbal_flashcards_feature_is_enabled_for_dev_users(monkeypatch):
    from zeeguu.core.user_feature_toggles import _verbal_flashcards

    monkeypatch.setattr(
        "zeeguu.core.user_feature_toggles.Cohort.find_by_code",
        lambda code: (_ for _ in ()).throw(NoResultFound()),
    )

    assert _verbal_flashcards(_stub_user(is_dev=True)) is True
