from zeeguu.core.model.db import db
from zeeguu.core.model.user import User
from zeeguu.core.util.time import server_now


class OnboardingFunnelEvent(db.Model):
    """
    One step a newcomer reached on the way into Zeeguu: the landing page, the
    language choice, the account form, a rejected invite code, the first
    article. The last step a funnel reached is where its visitor dropped out;
    the detail and the device fields are there to say why.

    Most rows are written before an account exists, so they hang together by
    funnel_id, a random id the client keeps in local storage. When an event
    arrives with a session, the user is known, and the funnel's earlier
    anonymous rows are claimed for that user as well (claim_funnel).

    Nothing the visitor typed is stored, and neither is the IP or the raw
    User-Agent; see zeeguu.core.util.user_agent.

    Not to be confused with OnboardingMessage, which is the tips shown to
    learners who already have an account.
    """

    __tablename__ = "onboarding_funnel_event"

    id = db.Column(db.Integer, primary_key=True)

    funnel_id = db.Column(db.String(64), nullable=False, index=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=True)
    user = db.relationship(User)

    # e.g. "account_form_shown", "invite_code_rejected"; the client names the
    # steps, the endpoint only checks their shape.
    step = db.Column(db.String(64), nullable=False)

    # Small step-specific facts: which field failed validation, which error the
    # API returned, how many seconds the step took.
    detail = db.Column(db.JSON, nullable=True)

    # How this visitor came in: landing page, shared article, invite, app.
    entry_point = db.Column(db.String(32), nullable=True)

    # Same codes as everywhere else, see zeeguu.core.constants.PLATFORM_NAMES.
    platform = db.Column(db.SmallInteger, nullable=True)
    app_version = db.Column(db.String(32), nullable=True)
    os = db.Column(db.String(32), nullable=True)
    os_version = db.Column(db.String(16), nullable=True)
    browser = db.Column(db.String(32), nullable=True)
    browser_version = db.Column(db.String(16), nullable=True)
    device_model = db.Column(db.String(64), nullable=True)
    viewport_w = db.Column(db.SmallInteger, nullable=True)
    viewport_h = db.Column(db.SmallInteger, nullable=True)
    # The browser's locale ("da-DK"), not a learned or native language: it is
    # often one Zeeguu doesn't offer, which is the point of recording it.
    ui_language = db.Column(db.String(16), nullable=True)
    online = db.Column(db.Boolean, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=server_now)

    @classmethod
    def claim_funnel(cls, funnel_id, user_id):
        """Attribute the funnel's anonymous rows to the user it turned into."""
        cls.query.filter_by(funnel_id=funnel_id, user_id=None).update(
            {"user_id": user_id}, synchronize_session=False
        )
