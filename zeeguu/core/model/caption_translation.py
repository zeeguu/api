"""A single translated caption — translated text for one original Caption inside a set.

Timing (time_start / time_end) is read from the original Caption; we only store the new text.
"""
from zeeguu.core.model.db import db
from zeeguu.core.model.caption import Caption
from zeeguu.core.model.new_text import NewText


class CaptionTranslation(db.Model):
    __tablename__ = "caption_translation"
    __table_args__ = (
        db.UniqueConstraint("set_id", "caption_id", name="uq_caption_translation_set_caption"),
        {"mysql_collate": "utf8_bin"},
    )

    id = db.Column(db.Integer, primary_key=True)

    set_id = db.Column(
        db.Integer, db.ForeignKey("caption_translation_set.id"), nullable=False
    )
    translation_set = db.relationship(
        "CaptionTranslationSet", back_populates="translations"
    )

    caption_id = db.Column(db.Integer, db.ForeignKey(Caption.id), nullable=False)
    caption = db.relationship(Caption, foreign_keys="CaptionTranslation.caption_id")

    text_id = db.Column(db.Integer, db.ForeignKey(NewText.id), nullable=False)
    text = db.relationship(NewText, foreign_keys="CaptionTranslation.text_id")

    def __init__(self, translation_set, caption, text):
        self.translation_set = translation_set
        self.caption = caption
        self.text = text

    def __repr__(self):
        return f"<CaptionTranslation set={self.set_id} caption={self.caption_id}>"

    def get_content(self):
        return self.text.get_content()

    @classmethod
    def create(cls, session, translation_set, caption, translated_text: str):
        text_row = NewText.find_or_create(session, translated_text, False)
        row = cls(translation_set=translation_set, caption=caption, text=text_row)
        session.add(row)
        return row
