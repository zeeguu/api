"""A correction of a translation, shared with everyone who looks up the same
word in the same sentence afterwards: the logged-in reader, the public article
page and the alternatives menu.

Started from zeeguu.org/read/O0ZRCFNonB (2026-11-03): a reader corrected
"er frosset til" from the machine's "is frozen to" to "are frozen solid", and
every other reader of the song kept getting "is frozen to".

Anchored on the sentence and the pair: ``context`` is the BookmarkContext,
which find_or_create deduplicates by sentence text, and ``meaning`` holds the
word and its translation. Token positions would drift with re-tokenization
(#618); a sentence anchor also carries over to the same sentence in another
article (a republished story, the same lyrics posted twice).

Who is believed: a teacher's or an admin's correction counts at once
(TRUSTED_USER) and no LLM is asked when it is made; anyone else's waits as
PENDING until the nightly run of tools/validate_translation_corrections.py,
where the validator accepts it (VALIDATOR) or not (REJECTED). The same run
audits trusted corrections without changing their status, only recording the
verdict.
"""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, and_, func, or_
from sqlalchemy.orm import aliased, relationship

from zeeguu.core.model.bookmark_context import BookmarkContext
from zeeguu.core.model.db import db
from zeeguu.core.model.meaning import Meaning


class TranslationCorrection(db.Model):
    __tablename__ = "translation_correction"
    __table_args__ = (
        UniqueConstraint("context_id", "meaning_id", name="uq_translation_correction"),
        {"mysql_collate": "utf8mb4_unicode_ci"},
    )

    PENDING, ACCEPTED, REJECTED = "PENDING", "ACCEPTED", "REJECTED"
    VALIDATOR, TRUSTED_USER = "VALIDATOR", "TRUSTED_USER"

    id = Column(Integer, primary_key=True)
    context_id = Column(Integer, ForeignKey(BookmarkContext.id, ondelete="CASCADE"), nullable=False)
    context = relationship(BookmarkContext)
    meaning_id = Column(Integer, ForeignKey(Meaning.id, ondelete="CASCADE"), nullable=False)
    meaning = relationship(Meaning)
    # Where the correction was made, not what makes it true: it outlives the
    # bookmark (SET NULL, not CASCADE) when the teacher removes the word from
    # their list, the learner deletes a word they know, or MySQL deletes the
    # bookmark itself (the validator's fix orphans a user word, and
    # bookmark.user_word_id cascades). None of these says the pair was wrong.
    bookmark_id = Column(Integer, ForeignKey("bookmark.id", ondelete="SET NULL"))
    # SET NULL too: a deleted account's corrections still serve other readers
    user_id = Column(Integer, ForeignKey("user.id", ondelete="SET NULL"))
    status = Column(Enum(PENDING, ACCEPTED, REJECTED), nullable=False, default=PENDING)
    accepted_by = Column(Enum(VALIDATOR, TRUSTED_USER))
    verdict = Column(String(32))
    reason = Column(Text)
    created_at = Column(DateTime, nullable=False, default=func.now())
    judged_at = Column(DateTime)

    @classmethod
    def record(cls, session, bookmark):
        """The learner changed the translation of a bookmark: remember the new
        pair in the bookmark's sentence. A teacher's or admin's counts at once; anyone
        else's waits for the nightly validator. A user's earlier correction of
        the same word in the same sentence is dropped. Does not commit."""
        from zeeguu.core.model.teacher import Teacher

        if not bookmark.context_id:
            return None
        meaning = bookmark.user_word.meaning
        user = bookmark.user_word.user

        earlier = (
            cls.query.join(Meaning, cls.meaning_id == Meaning.id)
            .filter(
                cls.context_id == bookmark.context_id,
                cls.user_id == user.id,
                Meaning.origin_id == meaning.origin_id,
                cls.meaning_id != meaning.id,
            )
            .all()
        )
        for row in earlier:
            session.delete(row)

        row = cls.query.filter_by(context_id=bookmark.context_id, meaning_id=meaning.id).first()
        if row is None:
            row = cls(context_id=bookmark.context_id, meaning_id=meaning.id)
        if row.status == cls.ACCEPTED:
            return row  # someone already got this exact pair accepted here

        row.bookmark_id = bookmark.id
        row.user_id = user.id
        # Admins too: on 2026-11-03 an admin's correction waited for the
        # nightly validator because the account had no teacher row. Trust
        # beyond staff (native-speaker volunteers, per language) would get a
        # table of its own.
        if user.is_admin or Teacher.exists(user):
            row.status, row.accepted_by = cls.ACCEPTED, cls.TRUSTED_USER
        else:
            row.status, row.accepted_by = cls.PENDING, None
        session.add(row)
        return row

    @classmethod
    def best_for(cls, word, sentence, from_language_id, to_language_id):
        """The accepted translation of ``word`` in ``sentence``, or None.

        Matches the corrections of this word whose sentence is part of this
        one: the reader sends a sentence cut to ~28 words around the word, and
        the public page the whole sentence, so the texts need not be equal.
        The newest correction wins."""
        from zeeguu.core.model.phrase import Phrase

        word = (word or "").strip()
        sentence = _normalized(sentence)
        # a sentence that is only the word would match every sentence with it
        if not word or len(sentence) <= len(word):
            return None

        Origin = aliased(Phrase)
        Translation = aliased(Phrase)
        rows = (
            cls.query.join(Meaning, cls.meaning_id == Meaning.id)
            .join(Origin, Meaning.origin_id == Origin.id)
            .join(Translation, Meaning.translation_id == Translation.id)
            .filter(
                cls.status == cls.ACCEPTED,
                Origin.content.in_({word, word.lower()}),
                Origin.language_id == from_language_id,
                Translation.language_id == to_language_id,
            )
            .order_by(cls.created_at.desc(), cls.id.desc())
            .limit(50)
            .all()
        )
        for row in rows:
            context_text = _normalized(row.context.get_content())
            if context_text and (context_text in sentence or sentence in context_text):
                return row
        return None

    @property
    def translation(self):
        return self.meaning.translation.content


def _normalized(text):
    return " ".join((text or "").split())


def corrections_to_judge():
    """What the nightly run asks the validator about: corrections waiting for
    a verdict, and teachers' corrections not audited yet."""
    C = TranslationCorrection
    return (
        C.query.filter(
            or_(
                C.status == C.PENDING,
                and_(C.accepted_by == C.TRUSTED_USER, C.judged_at.is_(None)),
            )
        )
        .order_by(C.id)
        .all()
    )


def judge(session, correction, validator):
    """The validator's verdict on a correction in its own sentence. A
    learner's becomes ACCEPTED on VALID and REJECTED otherwise; a teacher's
    keeps its status and only records the verdict, so we can see how often
    teachers and the validator disagree before trusting either more. No
    verdict leaves it as it was, to be asked again the next night. Commits.
    Returns the verdict, or None."""
    from datetime import datetime

    meaning = correction.meaning
    result = validator.validate_translation(
        word=meaning.origin.content,
        translation=meaning.translation.content,
        context=correction.context.get_content(),
        source_lang=meaning.origin.language.code,
        target_lang=meaning.translation.language.code,
    )
    if result is None:
        return None

    correction.verdict = result.verdict
    correction.reason = result.reason
    correction.judged_at = datetime.now()
    if correction.accepted_by != TranslationCorrection.TRUSTED_USER:
        if result.is_valid:
            correction.status = TranslationCorrection.ACCEPTED
            correction.accepted_by = TranslationCorrection.VALIDATOR
        else:
            correction.status = TranslationCorrection.REJECTED
    session.add(correction)
    session.commit()
    return result.verdict
