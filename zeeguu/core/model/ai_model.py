"""
AI Model entity for tracking which AI models were used for various tasks.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from zeeguu.core.model.db import db


class AIModel(db.Model):
    """
    Tracks AI models used for classification and generation tasks.
    Allows us to know which model generated what data and update when needed.
    """

    __tablename__ = "ai_models"
    __table_args__ = {"mysql_collate": "utf8mb4_unicode_ci"}

    id = Column(Integer, primary_key=True)
    model_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    def __init__(self, model_name, description=None):
        self.model_name = model_name
        self.description = description

    def __repr__(self):
        return f"<AIModel {self.model_name}>"

    @classmethod
    def find_or_create(cls, session, model_name, description=None):
        """
        Find existing model or create new one.

        Args:
            session: Database session
            model_name: Name of the AI model
            description: Optional description

        Returns:
            AIModel instance
        """
        try:
            model = cls.query.filter_by(model_name=model_name).one()
            # Update description if provided and different
            if description and model.description != description:
                model.description = description
                session.add(model)
                session.commit()
        except:
            model = cls(model_name, description)
            session.add(model)
            session.commit()

        return model

    @classmethod
    def get_current_classification_model(cls):
        """Get the current model used for meaning frequency classification."""
        return cls.query.filter_by(model_name="claude-3-5-sonnet-20241022").first()
