from zeeguu.core import events
from zeeguu.core.model.friend import Friend


@events.friend_streak_changed.connect
def on_friend_streak_changed(sender, user_id: int, db_session):
    friendships: list[Friend] = Friend.query.filter(
        (Friend.user_a_id == user_id) | (Friend.user_b_id == user_id)
    ).all()
    for friendship in friendships:
        friendship.update_friend_streak(session=db_session, commit=False)
