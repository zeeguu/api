"""
Service for classifying meaning frequencies using Anthropic API.
"""

import os

from anthropic import Anthropic

from zeeguu.core.llm_services.prompts.meaning_frequency_classifier import (
    create_meaning_frequency_and_type_prompt,
    create_batch_meaning_frequency_and_type_prompt,
)
from zeeguu.core.model.meaning import MeaningFrequency
from zeeguu.core.model.meaning import PhraseType
from zeeguu.logging import log, logp


class MeaningFrequencyClassifier:
    """Classifies meaning frequencies using Claude API."""

    MODEL_NAME = "claude-sonnet-4-5-20250929"  # Latest model (September 2025)

    def __init__(self):
        """Initialize with Anthropic client."""
        api_key = os.environ.get("ANTHROPIC_WORD_CLASSIFICATION_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_WORD_CLASSIFICATION_KEY environment variable not set"
            )
        self.client = Anthropic(api_key=api_key)

    def classify_meanings_batch(self, meanings):
        """
        Classify multiple meanings' frequency and phrase type in a single API call.

        Args:
            meanings: List of Meaning objects to classify

        Returns:
            list: List of tuples (MeaningFrequency, PhraseType) or (None, None) for failed items
                  Order matches input meanings list
        """
        if not meanings:
            return []

        # Map frequency and phrase type strings to enums
        frequency_map = {
            "unique": MeaningFrequency.UNIQUE,
            "common": MeaningFrequency.COMMON,
            "uncommon": MeaningFrequency.UNCOMMON,
            "rare": MeaningFrequency.RARE,
        }

        phrase_type_map = {
            "single_word": PhraseType.SINGLE_WORD,
            "collocation": PhraseType.COLLOCATION,
            "idiom": PhraseType.IDIOM,
            "expression": PhraseType.EXPRESSION,
            "arbitrary_multi_word": PhraseType.ARBITRARY_MULTI_WORD,
        }

        try:
            prompt = create_batch_meaning_frequency_and_type_prompt(meanings)

            # Calculate tokens needed: ~15 tokens per result line
            max_tokens = len(meanings) * 20

            response = self.client.messages.create(
                model=self.MODEL_NAME,
                max_tokens=max_tokens,
                temperature=0,  # Deterministic
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract and validate response
            result_text = response.content[0].text.strip()
            result_lines = [
                line.strip() for line in result_text.split("\n") if line.strip()
            ]

            if len(result_lines) != len(meanings):
                log(
                    f"Batch classification: Expected {len(meanings)} lines, got {len(result_lines)}"
                )
                # Return None for all if count mismatch
                return [(None, None)] * len(meanings)

            # Parse each line
            results = []
            for i, line in enumerate(result_lines):
                if "," not in line:
                    log(
                        f"Batch classification line {i+1}: Invalid format (no comma): {line}"
                    )
                    results.append((None, None))
                    continue

                frequency_str, phrase_type_str = line.split(",", 1)
                frequency_str = frequency_str.strip().lower()
                phrase_type_str = phrase_type_str.strip().lower()

                frequency = frequency_map.get(frequency_str)
                phrase_type = phrase_type_map.get(phrase_type_str)

                if frequency is None:
                    log(
                        f"Batch classification line {i+1}: Invalid frequency: {frequency_str}"
                    )
                if phrase_type is None:
                    log(
                        f"Batch classification line {i+1}: Invalid phrase type: {phrase_type_str}"
                    )

                results.append((frequency, phrase_type))

            return results

        except Exception as e:
            log(f"Error in batch classification: {str(e)}")
            return [(None, None)] * len(meanings)

    def classify_meaning(self, meaning):
        """
        Classify a single meaning's frequency and phrase type.
        Uses dedicated single-item prompt for better reliability.

        Args:
            meaning: Meaning object to classify

        Returns:
            tuple: (MeaningFrequency, PhraseType) or (None, None) if classification fails
        """
        # Map frequency and phrase type strings to enums
        frequency_map = {
            "unique": MeaningFrequency.UNIQUE,
            "common": MeaningFrequency.COMMON,
            "uncommon": MeaningFrequency.UNCOMMON,
            "rare": MeaningFrequency.RARE,
        }

        phrase_type_map = {
            "single_word": PhraseType.SINGLE_WORD,
            "collocation": PhraseType.COLLOCATION,
            "idiom": PhraseType.IDIOM,
            "expression": PhraseType.EXPRESSION,
            "arbitrary_multi_word": PhraseType.ARBITRARY_MULTI_WORD,
        }

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

    def classify_and_update_meanings_batch(self, meanings, session):
        """
        Classify and update multiple meanings in a single API call.

        Args:
            meanings: List of Meaning objects to classify and update
            session: Database session

        Returns:
            dict: Statistics about the batch classification
        """
        stats = {
            "total": len(meanings),
            "classified": 0,
            "failed": 0,
            "arbitrary_multi_word": 0,
        }

        # Classify all meanings in one API call
        results = self.classify_meanings_batch(meanings)

        # Update each meaning with its result
        for meaning, (frequency, phrase_type) in zip(meanings, results):
            if frequency and phrase_type:
                meaning.frequency = frequency
                meaning.phrase_type = phrase_type
                meaning.frequency_manually_validated = False

                session.add(meaning)
                stats["classified"] += 1

                # Track arbitrary multi-word
                if phrase_type == PhraseType.ARBITRARY_MULTI_WORD:
                    stats["arbitrary_multi_word"] += 1

            elif frequency:
                # Update only frequency if phrase type failed
                meaning.frequency = frequency
                meaning.frequency_manually_validated = False

                session.add(meaning)
                stats["classified"] += 1
            else:
                stats["failed"] += 1

        # Commit all updates
        if stats["classified"] > 0:
            session.commit()

            # Update fit_for_study for all user words referencing these meanings
            for meaning in meanings:
                if meaning.frequency or meaning.phrase_type:
                    self._update_user_words_fit_for_study(meaning, session)

        return stats

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
        user_words = (
            session.query(UserWord).filter(UserWord.meaning_id == meaning.id).all()
        )

        for user_word in user_words:
            user_word.update_fit_for_study(session)

        if user_words:
            session.commit()
            logp(
                f"Updated fit_for_study for {len(user_words)} user words referencing meaning {meaning.id}"
            )

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
