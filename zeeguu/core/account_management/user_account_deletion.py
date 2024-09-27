import sqlalchemy
from zeeguu.core.model import (
    User,
    ArticleDifficultyFeedback,
    PersonalCopy,
    SearchFilter,
    UserPreference,
    UserCohortMap,
)

import time
import zeeguu.core
from zeeguu.core.model.starred_article import StarredArticle

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
    UserPreference,
    UserCohortMap,
]


def delete_user_account(db_session, user_to_delete):
    try:
        start_time = time.time()
        total_rows_affected = 0
        articles = Article.uploaded_by(user_to_delete.id)
        print(f"Removing author from Articles:")
        for a in articles:
            a.uploader_id = None
            total_rows_affected += 1
            db_session.add(a)
        print(f"Total of {total_rows_affected} articles altered")
        db_session.commit()

        print(f"Deleting user {user_to_delete.name}...")
        for each_table in tables_to_modify:
            subject_related = each_table.query.filter_by(
                user_id=user_to_delete.id
            ).all()

            print(f"{each_table.__tablename__}: {len(subject_related)}")

            for each in subject_related:
                total_rows_affected += 1
                db_session.delete(each)
            db_session.commit()

        db_session.delete(user_to_delete)
        db_session.commit()
        end_time = time.time() - start_time
        print(
            f"A total of {total_rows_affected} rows were affected. The process took: {end_time:.2f} seconds."
        )
    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        print(e)
        raise Exception(f"Could not delete the user '{user_to_delete}'")


def delete_user_account_w_session(db_session, user_session_uuid):
    try:
        user_session = Session.find(user_session_uuid)
    except sqlalchemy.exc.IntegrityError:
        raise Exception("Integrity Error")
    except sqlalchemy.exc.NoResultFound:
        raise Exception(f"Couldn't find specified user session: '{user_session_uuid}'")
    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        print(e)
        raise Exception(
            f"Could not delete the user with session: '{user_session_uuid}'"
        )
    user_to_delete = User.find_by_id(user_session.user_id)
    delete_user_account(db_session, user_to_delete)
