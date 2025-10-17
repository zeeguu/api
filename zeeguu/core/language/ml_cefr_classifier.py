"""
ML-Based CEFR Classifier (ML-1)

Per-language Random Forest classifiers for CEFR level assessment.
Uses 12 fast-to-compute linguistic features to predict CEFR levels.

Branded as "ML-1" in the UI to distinguish from future ML models (ML-2, etc.)

Models are trained on LLM-assessed articles and stored in $ZEEGUU_DATA_FOLDER/ml_models/cefr_estimation/
"""

import os
import re
import pickle
import numpy as np
from zeeguu.logging import log

# Module-level cache for loaded models (avoids disk I/O on every prediction)
_MODEL_CACHE = {}


def extract_features(content, fk_difficulty, word_count):
    """
    Extract 12 linguistic features from article content.

    Features:
    1. FK difficulty (already computed)
    2. Word count (already computed)
    3. Average word length
    4. Average chars per word
    5. Average sentence length
    6. Sentence length std dev
    7. Type-token ratio (vocabulary richness)
    8. Long word ratio (words >7 chars)
    9. Punctuation complexity (semicolons, colons, em-dashes)
    10. Average paragraph length
    11. Interactive ratio (questions/exclamations per sentence)
    12. Character count
    """

    if not content or len(content.strip()) == 0:
        # Return default features for empty content
        return np.array([fk_difficulty or 50, word_count or 0] + [0.0] * 10)

    # Basic counts
    char_count = len(content)

    # Word-level features
    words = re.findall(r"\b\w+\b", content.lower())
    if not words:
        return np.array([fk_difficulty or 50, word_count or 0] + [0.0] * 10)

    actual_word_count = len(words)
    avg_word_length = np.mean([len(w) for w in words])
    long_word_ratio = sum(1 for w in words if len(w) > 7) / actual_word_count

    # Vocabulary richness (type-token ratio)
    unique_words = len(set(words))
    type_token_ratio = unique_words / actual_word_count if actual_word_count > 0 else 0

    # Sentence-level features
    sentences = re.split(r"[.!?]+", content)
    sentences = [s.strip() for s in sentences if s.strip()]

    if sentences:
        sentence_lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences]
        avg_sentence_length = np.mean(sentence_lengths)
        sentence_length_std = (
            np.std(sentence_lengths) if len(sentence_lengths) > 1 else 0
        )

        # Interactive ratio (questions/exclamations)
        interactive_marks = content.count("?") + content.count("!")
        interactive_ratio = (
            interactive_marks / len(sentences) if len(sentences) > 0 else 0
        )
    else:
        avg_sentence_length = 0
        sentence_length_std = 0
        interactive_ratio = 0

    # Punctuation complexity
    complex_punct = content.count(";") + content.count(":") + content.count("—")
    punct_complexity = complex_punct / actual_word_count if actual_word_count > 0 else 0

    # Paragraph-level features
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    if paragraphs:
        paragraph_lengths = [len(re.findall(r"\b\w+\b", p)) for p in paragraphs]
        avg_paragraph_length = np.mean(paragraph_lengths)
    else:
        avg_paragraph_length = actual_word_count  # Treat entire text as one paragraph

    # Average chars per word (different from avg_word_length)
    avg_chars_per_word = char_count / actual_word_count if actual_word_count > 0 else 0

    features = np.array(
        [
            fk_difficulty or 50,  # 1. FK difficulty
            word_count or actual_word_count,  # 2. Word count
            avg_word_length,  # 3. Average word length
            avg_chars_per_word,  # 4. Average chars per word
            avg_sentence_length,  # 5. Average sentence length
            sentence_length_std,  # 6. Sentence length std dev
            type_token_ratio,  # 7. Type-token ratio
            long_word_ratio,  # 8. Long word ratio
            punct_complexity,  # 9. Punctuation complexity
            avg_paragraph_length,  # 10. Average paragraph length
            interactive_ratio,  # 11. Interactive ratio
            char_count,  # 12. Character count
        ]
    )

    return features


def load_model(language_code):
    """
    Load trained ML-1 (Random Forest) model for given language.

    Uses module-level cache to avoid repeated disk I/O - models are loaded once
    and reused for the lifetime of the Python process.

    Models are stored in $ZEEGUU_DATA_FOLDER/ml_models/cefr_estimation/cefr_classifier_{lang}.pkl

    Returns:
        model: Trained sklearn RandomForestClassifier, or None if not found
    """
    # Check cache first
    if language_code in _MODEL_CACHE:
        cached = _MODEL_CACHE[language_code]
        if cached is None:
            log(f"ML model for {language_code} is cached as unavailable")
        return cached

    try:
        data_folder = os.environ.get("ZEEGUU_DATA_FOLDER")
        log(f"ML classifier: ZEEGUU_DATA_FOLDER = {data_folder}")

        if not data_folder:
            log(
                f"ZEEGUU_DATA_FOLDER not set, ML classifier unavailable for {language_code}"
            )
            # Cache the None result to avoid repeated checks
            _MODEL_CACHE[language_code] = None
            return None

        model_path = os.path.join(
            data_folder,
            "ml_models",
            "cefr_estimation",
            f"cefr_classifier_{language_code}.pkl",
        )

        log(f"ML classifier: Looking for model at {model_path}")
        log(f"ML classifier: File exists: {os.path.exists(model_path)}")

        if os.path.exists(model_path):
            # Check permissions
            log(f"ML classifier: File is readable: {os.access(model_path, os.R_OK)}")
            try:
                file_size = os.path.getsize(model_path)
                log(f"ML classifier: File size: {file_size} bytes ({file_size / (1024*1024):.1f} MB)")
            except Exception as e:
                log(f"ML classifier: Could not get file size: {e}")

        if not os.path.exists(model_path):
            log(f"ML model not found for {language_code}: {model_path}")
            # Cache the None result to avoid repeated filesystem checks
            _MODEL_CACHE[language_code] = None
            return None

        log(f"Loading ML model for {language_code} from disk (first time)")
        with open(model_path, "rb") as f:
            log(f"ML classifier: File opened successfully, loading pickle...")
            data = pickle.load(f)
            log(f"ML classifier: Pickle loaded, type: {type(data)}")
            # Extract model from dict (pickle file contains metadata)
            model = data.get("model") if isinstance(data, dict) else data
            log(f"ML classifier: Model extracted, type: {type(model)}")

        # Cache the loaded model
        _MODEL_CACHE[language_code] = model
        log(f"ML classifier: Model for {language_code} cached successfully")
        return model

    except Exception as e:
        log(f"Failed to load ML model for {language_code}: {e}")
        import traceback
        log(f"ML classifier traceback: {traceback.format_exc()}")
        # Cache the None result to avoid repeated failed attempts
        _MODEL_CACHE[language_code] = None
        return None


def predict_cefr_level(content, language_code, fk_difficulty, word_count):
    """
    Predict CEFR level using ML-1 (language-specific Random Forest classifier).

    Args:
        content: Article text content
        language_code: ISO language code (e.g., 'de', 'es', 'it')
        fk_difficulty: Flesch-Kincaid difficulty score
        word_count: Article word count

    Returns:
        CEFR level string ('A1', 'A2', 'B1', 'B2', 'C1', 'C2') or None if model unavailable
    """
    log(f"ML classifier: predict_cefr_level called for language={language_code}, word_count={word_count}, fk={fk_difficulty}")

    # Load model for this language
    model = load_model(language_code)
    if model is None:
        log(f"ML classifier: Model not available for {language_code}, returning None")
        return None

    log(f"ML classifier: Model loaded successfully, extracting features...")

    # Extract features
    features = extract_features(content, fk_difficulty, word_count)
    log(f"ML classifier: Features extracted: {features}")

    # Reshape for sklearn (expects 2D array)
    features = features.reshape(1, -1)

    # Predict
    try:
        log(f"ML classifier: Making prediction...")
        prediction = model.predict(features)[0]
        log(f"ML classifier: Prediction successful: {prediction}")
        return prediction

    except Exception as e:
        log(f"ML prediction failed for {language_code}: {e}")
        import traceback
        log(f"ML classifier prediction traceback: {traceback.format_exc()}")
        return None
