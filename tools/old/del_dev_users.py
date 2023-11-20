from zeeguu.core.model import User

import zeeguu.core

from sqlalchemy.orm.exc import NoResultFound

db_session = zeeguu.core.model.db.session

from zeeguu.core.model import (
    SearchSubscription,
    TopicFilter,
    TopicSubscription,
    Teacher,
    TeacherCohortMap,
    Session,
    User,
    UserActivityData,
    Bookmark,
    UserArticle,
    UserReadingSession,
    UserExerciseSession,
)
from zeeguu.core.model import Article

tables_to_modify = [
    SearchSubscription,
    TopicFilter,
    TopicSubscription,
    Session,
    Teacher,
    TeacherCohortMap,
    Bookmark,
    UserActivityData,
    UserArticle,
    UserReadingSession,
    UserExerciseSession,
]

# users that are developer accounts
# they should be deleted before doing data analysis
user_ids_to_delete = [
    3416,
    19,
    20,
    3011,
    2945,
    3405,
    2838,
    2230,
    2231,
    2232,
    62,
    1859,
    154,
    1,
    2643,
]


def delete_user(subject):
    articles = Article.uploaded_by(subject.id)
    print(f"articles to update uploaded id in:")
    for a in articles:
        a.uploader_id = None
        db_session.add(a)
    db_session.commit()

    print(f"Deleting user {subject.name}...")
    for each_table in tables_to_modify:
        subject_related = each_table.query.filter_by(user_id=subject.id).all()

        print(f"{each_table.__tablename__}: {len(subject_related)}")

        for each in subject_related:
            db_session.delete(each)
        db_session.commit()

    print(f"Done deleting user {subject.id}")
    db_session.delete(subject)
    db_session.commit()


for id in user_ids_to_delete:
    try:
        subject = User.find_by_id(id)
        delete_user(subject)
    except NoResultFound:
        print(f"Inexistent user: {id}")

# delete all anonymous users
for user in User.find_all():
    if "anon.zeeguu" in user.email:
        delete_user(user)
