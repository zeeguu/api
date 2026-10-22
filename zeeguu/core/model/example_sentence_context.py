from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.db import db
from zeeguu.core.model.example_sentence import ExampleSentence
import sqlalchemy
from zeeguu.core.model.race_safe import find_or_create


class ExampleSentenceContext(db.Model):
    """
    Maps a bookmark to an example sentence context.
    This follows the same pattern as VideoTitleContext, ArticleFragmentContext, etc.
    """

    __table_args__ = (
        # At most one context row per (bookmark, example sentence) — see find_or_create.
        db.UniqueConstraint(
            "bookmark_id",
            "example_sentence_id",
            name="uq_esc_bookmark_example",
        ),
        {"mysql_collate": "utf8_bin"},
    )

    id = db.Column(db.Integer, primary_key=True)

    bookmark_id = db.Column(
        db.Integer, db.ForeignKey(Bookmark.id, ondelete="CASCADE"), nullable=False
    )
    bookmark = db.relationship(Bookmark)

    example_sentence_id = db.Column(db.Integer, db.ForeignKey(ExampleSentence.id), nullable=False)
    example_sentence = db.relationship(ExampleSentence)

    def __init__(
        self,
        bookmark,
        example_sentence,
    ):
        self.bookmark = bookmark
        self.example_sentence = example_sentence

    def __repr__(self):
        return f"<ExampleSentenceContext es:{self.example_sentence_id}, b:{self.bookmark_id}>"

    @classmethod
    def find_by_bookmark(cls, bookmark):
        try:
            return cls.query.filter(cls.bookmark == bookmark).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_or_create(
        cls,
        session,
        bookmark,
        example_sentence,
        commit=True,
    ):
        return find_or_create(
            session,
            cls,
            dict(bookmark=bookmark, example_sentence=example_sentence),
            lambda: cls(bookmark, example_sentence),
            commit=commit,
        )

    @classmethod
    def get_all_user_bookmarks_for_example(
        cls, user_id: int, example_sentence_id: int, as_json_serializable: bool = True
    ):
        from zeeguu.core.model.user_word import UserWord

        result = (
            Bookmark.query.join(ExampleSentenceContext)
            .join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(ExampleSentenceContext.example_sentence_id == example_sentence_id)
            .filter(UserWord.user_id == user_id)
        ).all()

        return [each.to_json(True) if as_json_serializable else each for each in result]