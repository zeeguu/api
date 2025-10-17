#!/usr/bin/env python
"""
Train Random Forest CEFR classifiers with word frequency features.

This extends the base classifier with additional vocabulary frequency features
based on CEFR word lists.

Models are saved to $ZEEGUU_DATA_FOLDER/ml_models/cefr_estimation/cefr_classifier_freq_{lang}.pkl

Usage:
    # Train all languages
    source ~/.venvs/z_env/bin/activate && python -m tools.ml.cefr_trainers.train_cefr_classifiers_with_frequency --all

    # Train single language
    python -m tools.ml.cefr_trainers.train_cefr_classifiers_with_frequency --language de
"""

import os
import argparse
import pickle
import re
import numpy as np
from collections import Counter
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

from zeeguu.api.app import create_app
from zeeguu.core.model import db, Article, Language
from zeeguu.core.language.ml_cefr_classifier import extract_features
from zeeguu.logging import log

# Create Flask app and push context
app = create_app()
app.app_context().push()

db_session = db.session


def extract_frequency_features(content, language_code):
    """
    Extract word frequency features from content.

    Additional features (6 total):
    13. Average word frequency rank
    14. % of A1 level words
    15. % of A2 level words
    16. % of B1 level words
    17. % of B2 level words
    18. % of C1+ level words

    Args:
        content: Article text
        language_code: ISO language code

    Returns:
        Array of 6 frequency features
    """
    # TODO: Load actual CEFR word lists for each language
    # For now, return placeholder features
    # This would be enhanced with real frequency data from:
    # - Kelly Project word lists
    # - English Vocabulary Profile (EVP)
    # - Language-specific CEFR word lists

    words = re.findall(r"\b\w+\b", content.lower())
    if not words:
        return np.array([0.0] * 6)

    # Placeholder implementation
    # In production, you would:
    # 1. Load CEFR word lists from $ZEEGUU_DATA_FOLDER/cefr_word_lists/{lang}.json
    # 2. Classify each word by CEFR level
    # 3. Calculate percentages

    # For now, return neutral features
    avg_freq_rank = 5000  # Placeholder
    pct_a1 = 0.2  # Placeholder
    pct_a2 = 0.2  # Placeholder
    pct_b1 = 0.2  # Placeholder
    pct_b2 = 0.2  # Placeholder
    pct_c1plus = 0.2  # Placeholder

    return np.array([avg_freq_rank, pct_a1, pct_a2, pct_b1, pct_b2, pct_c1plus])


def extract_features_with_frequency(content, fk_difficulty, word_count, language_code):
    """
    Extract all 18 features (12 basic + 6 frequency).

    Args:
        content: Article text
        fk_difficulty: Flesch-Kincaid difficulty
        word_count: Article word count
        language_code: ISO language code

    Returns:
        Array of 18 features
    """
    # Get basic 12 features
    basic_features = extract_features(content, fk_difficulty, word_count)

    # Get 6 frequency features
    freq_features = extract_frequency_features(content, language_code)

    # Concatenate
    return np.concatenate([basic_features, freq_features])


def get_training_data(language_code, include_simplified=True):
    """
    Fetch training data from database.

    Args:
        language_code: ISO language code (e.g., 'de', 'es')
        include_simplified: Whether to include simplified articles

    Returns:
        Tuple of (features, labels, weights)
    """
    language = Language.find(language_code)
    if not language:
        log(f"Language {language_code} not found")
        return None, None, None

    # Query articles with CEFR levels (LLM-assessed)
    query = db_session.query(Article).filter(
        Article.language_id == language.id,
        Article.cefr_level.isnot(None),
        Article.broken == 0,
    )

    if not include_simplified:
        query = query.filter(Article.parent_article_id.is_(None))

    articles = query.all()

    if len(articles) == 0:
        log(f"No training data found for {language_code}")
        return None, None, None

    log(f"Found {len(articles)} articles for {language_code}")

    # Extract features and labels
    features_list = []
    labels_list = []
    weights_list = []

    for article in articles:
        try:
            # Extract features (18 total: 12 basic + 6 frequency)
            features = extract_features_with_frequency(
                article.get_content(),
                article.get_fk_difficulty(),
                article.get_word_count(),
                language_code,
            )

            # Weight: originals=1.0, simplified=0.7
            weight = 0.7 if article.parent_article_id else 1.0

            features_list.append(features)
            labels_list.append(article.cefr_level)
            weights_list.append(weight)

        except Exception as e:
            log(f"Error extracting features for article {article.id}: {e}")
            continue

    if len(features_list) == 0:
        log(f"No valid features extracted for {language_code}")
        return None, None, None

    X = np.array(features_list)
    y = np.array(labels_list)
    weights = np.array(weights_list)

    log(f"Extracted {len(X)} feature vectors (18 features each)")
    log(f"  - Original articles: {sum(weights == 1.0)}")
    log(f"  - Simplified articles: {sum(weights == 0.7)}")

    return X, y, weights


def train_classifier(X, y, weights):
    """
    Train Random Forest classifier.

    Args:
        X: Feature matrix (n_samples, 18 features)
        y: Labels (CEFR levels)
        weights: Sample weights

    Returns:
        Trained model and test metrics
    """
    # Split data (80% train, 20% test)
    X_train, X_test, y_train, y_test, weights_train, weights_test = train_test_split(
        X, y, weights, test_size=0.2, random_state=42, stratify=y
    )

    log(f"Training set: {len(X_train)} samples")
    log(f"Test set: {len(X_test)} samples")

    # Train Random Forest
    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        random_state=42,
        class_weight="balanced",
        n_jobs=-1,
    )

    log("Training Random Forest classifier with frequency features...")
    clf.fit(X_train, y_train, sample_weight=weights_train)

    # Evaluate on test set
    y_pred = clf.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    log(f"\nTest Set Accuracy: {accuracy:.3f}")
    log("\nClassification Report:")
    log(classification_report(y_test, y_pred))

    log("\nConfusion Matrix:")
    log(confusion_matrix(y_test, y_pred))

    # Feature importances
    feature_names = [
        "FK difficulty",
        "Word count",
        "Avg word length",
        "Avg chars/word",
        "Avg sentence length",
        "Sentence length std",
        "Type-token ratio",
        "Long word ratio",
        "Punct complexity",
        "Avg paragraph length",
        "Interactive ratio",
        "Character count",
        "Avg freq rank",
        "% A1 words",
        "% A2 words",
        "% B1 words",
        "% B2 words",
        "% C1+ words",
    ]

    log("\nTop 5 Most Important Features:")
    importances = sorted(
        zip(feature_names, clf.feature_importances_), key=lambda x: x[1], reverse=True
    )
    for name, importance in importances[:5]:
        log(f"  {name}: {importance:.3f}")

    return clf, accuracy


def save_model(clf, language_code):
    """
    Save trained model to disk.

    Args:
        clf: Trained classifier
        language_code: ISO language code
    """
    data_folder = os.environ.get("ZEEGUU_DATA_FOLDER")
    if not data_folder:
        raise ValueError("ZEEGUU_DATA_FOLDER environment variable not set")

    models_dir = os.path.join(data_folder, "ml_models")
    os.makedirs(models_dir, exist_ok=True)

    # Note: Frequency models use different filename
    model_path = os.path.join(models_dir, f"cefr_classifier_freq_{language_code}.pkl")

    with open(model_path, "wb") as f:
        pickle.dump(clf, f)

    log(f"Model saved to: {model_path}")


def train_language(language_code, include_simplified=True):
    """
    Train classifier for a single language.

    Args:
        language_code: ISO language code
        include_simplified: Whether to include simplified articles

    Returns:
        Test accuracy or None if training failed
    """
    log("=" * 80)
    log(f"Training CEFR classifier (with frequency) for: {language_code.upper()}")
    log("=" * 80)

    # Get training data
    X, y, weights = get_training_data(language_code, include_simplified)
    if X is None:
        log(f"Skipping {language_code} - no training data")
        return None

    # Train model
    clf, accuracy = train_classifier(X, y, weights)

    # Save model
    save_model(clf, language_code)

    log(f"\n✓ Training complete for {language_code} (accuracy: {accuracy:.3f})")
    return accuracy


def train_all_languages(include_simplified=True):
    """
    Train classifiers for all languages with sufficient data.

    Args:
        include_simplified: Whether to include simplified articles
    """
    # Get all languages with LLM-assessed articles
    languages_query = (
        db_session.query(Language)
        .join(Article)
        .filter(Article.cefr_level.isnot(None), Article.broken == 0)
        .distinct()
    )

    languages = languages_query.all()

    log(f"Found {len(languages)} languages with CEFR-assessed articles")
    log("")

    results = {}
    for language in languages:
        accuracy = train_language(language.code, include_simplified)
        if accuracy:
            results[language.code] = accuracy
        log("")

    # Summary
    log("=" * 80)
    log("TRAINING SUMMARY (WITH FREQUENCY FEATURES)")
    log("=" * 80)
    log(f"Languages trained: {len(results)}")
    log("")

    if results:
        log("Accuracies by language:")
        for lang_code in sorted(results.keys(), key=lambda x: results[x], reverse=True):
            log(f"  {lang_code}: {results[lang_code]:.3f}")

        log("")
        log(f"Average accuracy: {np.mean(list(results.values())):.3f}")
        log("")
        log("NOTE: Frequency features are currently placeholders.")
        log("To enable real frequency features, add CEFR word lists to:")
        log("  $ZEEGUU_DATA_FOLDER/cefr_word_lists/{lang}.json")

    log("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Train Random Forest CEFR classifiers with word frequency features"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Train classifiers for all languages",
    )

    parser.add_argument(
        "--language",
        type=str,
        help="Train classifier for specific language (e.g., 'de', 'es')",
    )

    parser.add_argument(
        "--no-simplified",
        action="store_true",
        help="Exclude simplified articles from training",
    )

    args = parser.parse_args()

    if not args.all and not args.language:
        parser.error("Either --all or --language must be specified")

    include_simplified = not args.no_simplified

    if args.all:
        train_all_languages(include_simplified)
    elif args.language:
        train_language(args.language, include_simplified)
