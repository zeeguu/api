from zeeguu.core.friends.friend_streak import update_streak
from zeeguu.core import events
from zeeguu.core.model.friendship import Friendship


@events.friend_streak_changed.connect
def on_friend_streak_changed(sender, user_id: int, db_session):
    friendships: list[Friendship] = db_session.query(Friendship).filter(
        (Friendship.user_a_id == user_id) | (Friendship.user_b_id == user_id)
    ).all()
    for friendship in friendships:
        update_streak(friendship, db_session, False)
