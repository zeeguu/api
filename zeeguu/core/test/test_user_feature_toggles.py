from types import SimpleNamespace


def _stub_user(invitation_code=None, cohorts=None):
    return SimpleNamespace(
        id=1,
        is_admin=False,
        is_dev=False,
        invitation_code=invitation_code,
        cohorts=cohorts or [],
        is_member_of_cohort=lambda cohort_id: False,
        isTeacher=lambda: False,
    )


def test_verbal_flashcards_feature_defaults_to_disabled_when_no_allowlist(monkeypatch):
    from zeeguu.core.user_feature_toggles import _verbal_flashcards

    monkeypatch.delenv("VERBAL_FLASHCARDS_INVITE_CODES", raising=False)
    user = _stub_user()

    assert _verbal_flashcards(user) is False


def test_verbal_flashcards_feature_uses_invite_code_allowlist(monkeypatch):
    from zeeguu.core.user_feature_toggles import _verbal_flashcards

    monkeypatch.setenv("VERBAL_FLASHCARDS_INVITE_CODES", "beta-one, teacherpilot ")

    allowed_user = _stub_user("TeacherPilot")
    blocked_user = _stub_user("someone-else")

    assert _verbal_flashcards(allowed_user) is True
    assert _verbal_flashcards(blocked_user) is False


def test_verbal_flashcards_feature_ignores_matching_cohort_invite_code(monkeypatch):
    from zeeguu.core.user_feature_toggles import _verbal_flashcards

    monkeypatch.setenv("VERBAL_FLASHCARDS_INVITE_CODES", "beta-one, teacherpilot ")
    cohort_membership = SimpleNamespace(cohort=SimpleNamespace(inv_code="beta-one"))
    allowed_user = _stub_user(invitation_code="classe2019", cohorts=[cohort_membership])

    assert _verbal_flashcards(allowed_user) is False


def test_verbal_flashcards_feature_does_not_bypass_allowlist_for_admins(monkeypatch):
    from zeeguu.core.user_feature_toggles import _verbal_flashcards

    monkeypatch.delenv("VERBAL_FLASHCARDS_INVITE_CODES", raising=False)
    admin_user = SimpleNamespace(
        id=1,
        is_admin=True,
        is_dev=False,
        invitation_code=None,
        cohorts=[],
        is_member_of_cohort=lambda cohort_id: False,
        isTeacher=lambda: False,
    )

    assert _verbal_flashcards(admin_user) is False
