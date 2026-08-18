"""
AI Model entity for tracking which AI models were used for various tasks.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from zeeguu.core.model.db import db
from zeeguu.core.llm_services import models


class AIGenerator(db.Model):
    """
    Tracks AI generators (model + prompt version combinations) used for classification and generation tasks.
    Allows us to know which generator created what data and update when needed.
    """

    __tablename__ = "ai_generator"
    __table_args__ = {"mysql_collate": "utf8mb4_unicode_ci"}

    id = Column(Integer, primary_key=True)
    model_name = Column(String(100), nullable=False)
    prompt_version = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    def __init__(self, model_name, prompt_version=None, description=None):
        self.model_name = model_name
        self.prompt_version = prompt_version
        self.description = description

    def __repr__(self):
        return f"<AIGenerator {self.model_name}:{self.prompt_version}>"

    @classmethod
    def find_or_create(cls, session, model_name, prompt_version=None, description=None):
        """
        Find existing model or create new one.

        Flushes rather than commits, so the generator belongs to whatever unit of
        work the caller is in. It is almost always looked up while building the
        row that will reference it — a lesson, a simplified article — and
        committing here made a lookup quietly commit that half-built work too,
        past the point any later failure could roll back. Flushing still emits
        the INSERT, so the id is available immediately and a bad value still
        fails here rather than somewhere later.

        Every caller commits shortly after. The cost is that two processes
        creating the same generator concurrently can now both insert it; there is
        no unique constraint, so that was already possible, just in a narrower
        window, and a duplicate generator row is harmless.

        Args:
            session: Database session
            model_name: Name of the AI model
            prompt_version: Version of the prompt used
            description: Optional description

        Returns:
            AIGenerator instance
        """
        try:
            # Look for exact match with model_name and prompt_version
            query = cls.query.filter_by(model_name=model_name)
            if prompt_version:
                query = query.filter_by(prompt_version=prompt_version)
            else:
                query = query.filter_by(prompt_version=None)
            
            model = query.one()
            
            # Update description if provided and different
            if description and model.description != description:
                model.description = description
                session.add(model)
                session.flush()
        except:
            model = cls(model_name, prompt_version, description)
            session.add(model)
            session.flush()

        return model

    @classmethod
    def get_current_classification_model(cls):
        """Get the current model used for meaning frequency classification."""
        return cls.query.filter_by(model_name=models.MEANING_FREQUENCY).first()
