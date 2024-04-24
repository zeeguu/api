from zeeguu.api.app import create_app
from zeeguu.core.model import User, ArticleDifficultyFeedback, PersonalCopy, SearchFilter, UserPreference

import zeeguu.core
from zeeguu.core.model.starred_article import StarredArticle

app = create_app()
app.app_context().push()

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
    StarredArticle,
    ArticleDifficultyFeedback,
    PersonalCopy,
    SearchFilter,
    UserPreference
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


# delete all anonymous users
for user in User.find_all():
    if "anon.zeeguu" in user.email:
        delete_user(user)

for user in User.query.filter_by(is_dev=True):
    print("deleting ... " + user.name)
    delete_user(user)

print("Remaining users: " + str(len(User.find_all())))
