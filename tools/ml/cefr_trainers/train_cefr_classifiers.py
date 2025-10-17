#!/usr/bin/env python
"""
Train Random Forest CEFR classifiers for each language.

Uses LLM-assessed articles as training data:
- Original articles (weight: 1.0)
- Simplified articles (weight: 0.7)

Models are saved to $ZEEGUU_DATA_FOLDER/ml_models/cefr_estimation/cefr_classifier_{lang}.pkl

Usage:
    # Train all languages
    source ~/.venvs/z_env/bin/activate && python -m tools.ml.cefr_trainers.train_cefr_classifiers --all

    # Train single language
    python -m tools.ml.cefr_trainers.train_cefr_classifiers --language de

    # Train without simplified articles
    python -m tools.ml.cefr_trainers.train_cefr_classifiers --all --no-simplified
"""

import os
import argparse
import pickle
import numpy as np
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
            # Extract features
            features = extract_features(
                article.get_content(),
                article.get_fk_difficulty(),
                article.get_word_count(),
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

    log(f"Extracted {len(X)} feature vectors")
    log(f"  - Original articles: {sum(weights == 1.0)}")
    log(f"  - Simplified articles: {sum(weights == 0.7)}")

    return X, y, weights


def train_classifier(X, y, weights):
    """
    Train Random Forest classifier.

    Args:
        X: Feature matrix (n_samples, 12 features)
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

    log("Training Random Forest classifier...")
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

    model_path = os.path.join(models_dir, f"cefr_classifier_{language_code}.pkl")

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
    log(f"Training CEFR classifier for: {language_code.upper()}")
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
    log("TRAINING SUMMARY")
    log("=" * 80)
    log(f"Languages trained: {len(results)}")
    log("")

    if results:
        log("Accuracies by language:")
        for lang_code in sorted(results.keys(), key=lambda x: results[x], reverse=True):
            log(f"  {lang_code}: {results[lang_code]:.3f}")

        log("")
        log(f"Average accuracy: {np.mean(list(results.values())):.3f}")

    log("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Random Forest CEFR classifiers")

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
