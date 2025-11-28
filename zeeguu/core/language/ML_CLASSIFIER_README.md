# ML-Based CEFR Classifier

Per-language Random Forest classifiers for CEFR level assessment.

Used as a **smart fallback** when LLM assessment fails, providing much better accuracy than naive FK→CEFR conversion.

## Architecture

```
Article needs CEFR level
    ↓
Try LLM assessment (DeepSeek)
    ↓ (if fails/unavailable)
Try ML classifier (per-language Random Forest)
    ↓ (if no model exists)
Fall back to naive FK→CEFR
```

## Training Data

- **Original articles**: LLM-assessed RSS articles (weight: 1.0)
- **Simplified articles**: LLM-generated simplified versions (weight: 0.7)

Current coverage (as of Oct 2025):
- German: 93,476 articles (25k original, 68k simplified)
- Italian: 74,609 articles
- Spanish: 59,969 articles
- And 8 more languages with 20k-57k articles each

## Features (12 total)

Fast-to-compute linguistic features:

1. **FK difficulty** (already in DB)
2. **Word count** (already in DB)
3. **Average word length**
4. **Average chars per word**
5. **Average sentence length**
6. **Sentence length std dev**
7. **Type-token ratio** (vocabulary richness)
8. **Long word ratio** (words >7 chars)
9. **Punctuation complexity** (semicolons, colons, em-dashes)
10. **Average paragraph length**
11. **Interactive ratio** (questions/exclamations per sentence)
12. **Character count**

All features compute in <10ms, suitable for real-time use.

## Training Models

### Train all languages

```bash
cd api
source ~/.venvs/z_env/bin/activate
python -m tools.train_cefr_classifiers --all
```

### Train single language

```bash
python -m tools.train_cefr_classifiers --language de
python -m tools.train_cefr_classifiers --language es
```

### Train without simplified articles (originals only)

```bash
python -m tools.train_cefr_classifiers --all --no-simplified
```

## Usage

The classifier is automatically used as fallback! No code changes needed.

When `article.cefr_level` is NULL, the system automatically:
1. Tries ML classifier (if model exists)
2. Falls back to naive FK→CEFR

### Example

```python
from zeeguu.core.language.automatic_cefr_assessment import assess_cefr_level

# Old way (naive FK only)
level = assess_cefr_level(article.fk_difficulty)

# New way (ML-enhanced, automatic fallback)
level = assess_cefr_level(
    article.fk_difficulty,
    article.get_content(),
    article.language.code,
    article.get_word_count()
)
```

## Model Location

Trained models saved to:
```
zeeguu/core/language/ml_models/
    cefr_classifier_de.pkl
    cefr_classifier_es.pkl
    cefr_classifier_da.pkl
    ...
```

## Expected Accuracy

Based on test set evaluation (20% holdout):

- **With simplified articles**: 70-85% accuracy
- **Without simplified articles**: 65-75% accuracy
- **Naive FK→CEFR baseline**: ~40-50% accuracy

Much better at distinguishing:
- B1 vs B2 (most important distinction)
- Beginner (A1/A2) vs Intermediate
- Intermediate vs Advanced (C1/C2)

## Retraining Schedule

Retrain models monthly or when:
- New LLM assessments accumulated (>1000 per language)
- Accuracy drops below 70%
- Adding new language support

## Notes

- Models trained with sample weights (originals=1.0, simplified=0.7)
- Uses sklearn RandomForestClassifier (100 trees, depth 15)
- Handles class imbalance through weighted sampling
- Feature engineering based on readability research
- Language-specific models capture language structure differences

## Future Improvements

1. Add vocabulary frequency features (CEFR word lists)
2. Try XGBoost (might be more accurate)
3. Add grammar complexity features (POS tagging)
4. Ensemble multiple models per language
5. Active learning: retrain on crawler errors
