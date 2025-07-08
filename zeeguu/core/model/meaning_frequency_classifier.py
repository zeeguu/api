"""
Service for classifying meaning frequencies using Anthropic API.
"""

import os
from anthropic import Anthropic
from zeeguu.core.model.meaning import MeaningFrequency
from zeeguu.core.prompts.meaning_frequency_classifier import (
    create_meaning_frequency_and_type_prompt,
)
from zeeguu.core.model.meaning import PhraseType
from zeeguu.logging import log


class MeaningFrequencyClassifier:
    """Classifies meaning frequencies using Claude API."""

    MODEL_NAME = "claude-3-5-sonnet-20241022"  # Most capable current model for accuracy

    def __init__(self):
        """Initialize with Anthropic client."""
        api_key = os.environ.get("ANTHROPIC_WORD_CLASSIFICATION_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_WORD_CLASSIFICATION_KEY environment variable not set"
            )
        self.client = Anthropic(api_key=api_key)

    def classify_meaning(self, meaning):
        """
        Classify a single meaning's frequency and phrase type.

        Args:
            meaning: Meaning object to classify

        Returns:
            tuple: (MeaningFrequency, PhraseType) or (None, None) if classification fails
        """
        try:
            prompt = create_meaning_frequency_and_type_prompt(meaning)

            response = self.client.messages.create(
                model=self.MODEL_NAME,
                max_tokens=20,  # Need space for "frequency,phrase_type"
                temperature=0,  # Deterministic
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract and validate response
            result = response.content[0].text.strip().lower()

            # Parse comma-separated response
            if "," not in result:
                log(f"Invalid response format (no comma): {result}")
                return None, None

            frequency_str, phrase_type_str = result.split(",", 1)
            frequency_str = frequency_str.strip()
            phrase_type_str = phrase_type_str.strip()

            # Map frequency to enum
            frequency_map = {
                "unique": MeaningFrequency.UNIQUE,
                "common": MeaningFrequency.COMMON,
                "uncommon": MeaningFrequency.UNCOMMON,
                "rare": MeaningFrequency.RARE,
            }

            # Map phrase type to enum
            phrase_type_map = {
                "single_word": PhraseType.SINGLE_WORD,
                "collocation": PhraseType.COLLOCATION,
                "idiom": PhraseType.IDIOM,
                "expression": PhraseType.EXPRESSION,
                "arbitrary_multi_word": PhraseType.ARBITRARY_MULTI_WORD,
            }

            frequency = frequency_map.get(frequency_str)
            phrase_type = phrase_type_map.get(phrase_type_str)

            if frequency is None:
                log(f"Invalid frequency response: {frequency_str}")
            if phrase_type is None:
                log(f"Invalid phrase type response: {phrase_type_str}")

            return frequency, phrase_type

        except Exception as e:
            log(f"Error classifying meaning: {str(e)}")
            return None, None

    def classify_and_update_meaning(self, meaning, session):
        """
        Classify and update a meaning's frequency and phrase type in the database.
        Also updates fit_for_study for all user words that reference this meaning.

        Args:
            meaning: Meaning object to classify and update
            session: Database session

        Returns:
            bool: True if successfully classified and updated
        """
        frequency, phrase_type = self.classify_meaning(meaning)

        if frequency and phrase_type:
            meaning.frequency = frequency
            meaning.phrase_type = phrase_type
            meaning.frequency_manually_validated = False

            session.add(meaning)
            session.commit()

            # Update fit_for_study for all user words that reference this meaning
            self._update_user_words_fit_for_study(meaning, session)

            log(
                f"Updated meaning {meaning.id}: frequency={frequency.value}, phrase_type={phrase_type.value}"
            )
            return True
        elif frequency:
            # Update only frequency if phrase type failed
            meaning.frequency = frequency
            meaning.frequency_manually_validated = False

            session.add(meaning)
            session.commit()

            # Update fit_for_study for all user words that reference this meaning
            self._update_user_words_fit_for_study(meaning, session)

            log(
                f"Updated meaning {meaning.id} frequency to {frequency.value} (phrase_type failed)"
            )
            return True

        return False

    def _update_user_words_fit_for_study(self, meaning, session):
        """
        Update fit_for_study for all user words that reference this meaning.
        
        Args:
            meaning: Meaning object that was updated
            session: Database session
        """
        from zeeguu.core.model.user_word import UserWord
        
        # Find all user words that reference this meaning
        user_words = session.query(UserWord).filter(UserWord.meaning_id == meaning.id).all()
        
        for user_word in user_words:
            user_word.update_fit_for_study(session)
            
        if user_words:
            session.commit()
            log(f"Updated fit_for_study for {len(user_words)} user words referencing meaning {meaning.id}")

    def mark_as_validated(self, meaning, session):
        """
        Mark a meaning's frequency as manually validated.

        Args:
            meaning: Meaning object to mark as validated
            session: Database session
        """
        meaning.frequency_manually_validated = True
        session.add(meaning)
        session.commit()
        log(f"Marked meaning {meaning.id} frequency as manually validated")


# Example batch processing script:
"""
from zeeguu.core.model import db, Meaning
from zeeguu.core.model.meaning_frequency_classifier import MeaningFrequencyClassifier

classifier = MeaningFrequencyClassifier()

# Process meanings without frequency or phrase type
unclassified = Meaning.query.filter(
    (Meaning.frequency.is_(None)) | (Meaning.phrase_type.is_(None))
).limit(100).all()

for meaning in unclassified:
    classifier.classify_and_update_meaning(meaning, db.session)
    # Add delay to respect rate limits if needed
"""
