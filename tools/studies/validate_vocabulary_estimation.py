#!/usr/bin/env python
"""
Validate the vocabulary estimation theory:
"If a learner encounters a word N times without translating it, they know it."

Validation approach:
1. Track translation patterns for each user
2. Words translated once and never again → likely learned
3. Words re-translated after a gap → potential prediction failures
4. Calculate "stability rate" = % of words never re-translated

This gives us empirical validation of the P(know) estimation approach.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from zeeguu.api.app import create_app
from zeeguu.core.model import db
from sqlalchemy import text

app = create_app()
app.app_context().push()

from collections import defaultdict

def get_active_users():
    """Get users with sufficient reading and translation activity."""

    query = """
        SELECT
            u.id,
            u.name,
            l.code as language,
            l.id as language_id,
            COUNT(DISTINCT urs.article_id) as articles_read,
            (SELECT COUNT(DISTINCT b2.id)
             FROM bookmark b2
             JOIN user_word uw2 ON b2.user_word_id = uw2.id
             WHERE uw2.user_id = u.id) as total_bookmarks
        FROM user u
        JOIN user_reading_session urs ON u.id = urs.user_id
        JOIN article a ON urs.article_id = a.id
        JOIN language l ON a.language_id = l.id
        WHERE urs.duration > 30000
        GROUP BY u.id, u.name, l.code, l.id
        HAVING COUNT(DISTINCT urs.article_id) >= 15
        ORDER BY COUNT(DISTINCT urs.article_id) DESC
        LIMIT 30
    """

    return db.session.execute(text(query)).fetchall()


def analyze_retranslation_patterns(user_id, language_id):
    """
    Analyze translation patterns for a user.

    For each word, track:
    - How many times it was translated (different bookmark instances)
    - Time span between first and last translation
    - Whether it was re-translated after a gap

    Key insight: Words translated once and never again were likely learned.
    """

    query = """
        SELECT
            LOWER(p.content) as word,
            COUNT(DISTINCT b.id) as translation_count,
            MIN(b.time) as first_translation,
            MAX(b.time) as last_translation,
            DATEDIFF(MAX(b.time), MIN(b.time)) as days_span
        FROM bookmark b
        JOIN user_word uw ON b.user_word_id = uw.id
        JOIN meaning m ON uw.meaning_id = m.id
        JOIN phrase p ON m.origin_id = p.id
        WHERE uw.user_id = :user_id
        AND p.language_id = :language_id
        AND LENGTH(p.content) >= 3
        AND p.content NOT LIKE '%% %%'
        AND b.time IS NOT NULL
        GROUP BY LOWER(p.content)
        ORDER BY translation_count DESC
    """

    results = db.session.execute(
        text(query),
        {'user_id': user_id, 'language_id': language_id}
    ).fetchall()

    return results


def analyze_encounters_before_translation(user_id, language_id):
    """
    For words that were eventually translated, count how many articles
    contained that word BEFORE the first translation.

    This validates: "If you see a word N times without translating, you probably know it"
    by checking: "When people DO translate, how many times had they seen it before?"
    """

    # Get first translation time for each word
    first_translations_query = """
        SELECT
            LOWER(p.content) as word,
            MIN(b.time) as first_translation_time
        FROM bookmark b
        JOIN user_word uw ON b.user_word_id = uw.id
        JOIN meaning m ON uw.meaning_id = m.id
        JOIN phrase p ON m.origin_id = p.id
        WHERE uw.user_id = :user_id
        AND p.language_id = :language_id
        AND LENGTH(p.content) >= 3
        AND p.content NOT LIKE '%% %%'
        AND b.time IS NOT NULL
        GROUP BY LOWER(p.content)
    """

    first_translations = db.session.execute(
        text(first_translations_query),
        {'user_id': user_id, 'language_id': language_id}
    ).fetchall()

    # Get all articles read by this user with timestamps
    articles_query = """
        SELECT
            a.id,
            a.content,
            MIN(urs.start_time) as first_read_time
        FROM user_reading_session urs
        JOIN article a ON urs.article_id = a.id
        WHERE urs.user_id = :user_id
        AND a.language_id = :language_id
        AND urs.duration > 30000
        GROUP BY a.id, a.content
    """

    articles = db.session.execute(
        text(articles_query),
        {'user_id': user_id, 'language_id': language_id}
    ).fetchall()

    # For each translated word, count articles containing it before translation
    results = []
    for word_row in first_translations[:100]:  # Limit for performance
        word = word_row.word
        first_trans_time = word_row.first_translation_time

        # Count articles containing this word that were read before translation
        articles_before = 0
        for article in articles:
            if article.first_read_time and first_trans_time:
                if article.first_read_time < first_trans_time:
                    # Check if word appears in article (simple substring match)
                    if article.content and word.lower() in article.content.lower():
                        articles_before += 1

        results.append((word, articles_before, first_trans_time))

    return sorted(results, key=lambda x: x[1], reverse=True)


def main():
    print("=" * 100)
    print("VALIDATION: Vocabulary Estimation from Non-Translation Behavior")
    print("=" * 100)

    users = get_active_users()
    print(f"\nAnalyzing {len(users)} users with ≥15 articles read\n")

    # Aggregate statistics
    total_words = 0
    words_translated_once = 0
    words_translated_multiple = 0
    words_retranslated_after_7_days = 0
    words_retranslated_after_30_days = 0
    words_retranslated_after_90_days = 0

    user_summaries = []

    for user in users:
        results = analyze_retranslation_patterns(user.id, user.language_id)

        user_total = 0
        user_once = 0
        user_multiple = 0
        user_gap_7 = 0
        user_gap_30 = 0
        user_gap_90 = 0

        for row in results:
            user_total += 1
            if row.translation_count == 1:
                user_once += 1
            else:
                user_multiple += 1
                if row.days_span:
                    if row.days_span >= 7:
                        user_gap_7 += 1
                    if row.days_span >= 30:
                        user_gap_30 += 1
                    if row.days_span >= 90:
                        user_gap_90 += 1

        if user_total > 0:
            stability_rate = user_once / user_total * 100
            user_summaries.append({
                'name': user.name,
                'language': user.language,
                'articles': user.articles_read,
                'words': user_total,
                'once': user_once,
                'multiple': user_multiple,
                'gap_30': user_gap_30,
                'stability': stability_rate
            })

            total_words += user_total
            words_translated_once += user_once
            words_translated_multiple += user_multiple
            words_retranslated_after_7_days += user_gap_7
            words_retranslated_after_30_days += user_gap_30
            words_retranslated_after_90_days += user_gap_90

    # Print per-user summary
    print(f"{'User':<20} {'Lang':<8} {'Articles':>8} {'Words':>8} {'Once':>8} {'Multi':>8} {'Gap>30d':>8} {'Stability':>10}")
    print("-" * 100)

    for s in sorted(user_summaries, key=lambda x: x['words'], reverse=True)[:20]:
        print(f"{s['name']:<20} {s['language']:<8} {s['articles']:>8} {s['words']:>8} {s['once']:>8} {s['multiple']:>8} {s['gap_30']:>8} {s['stability']:>9.1f}%")

    # Aggregate summary
    print("\n" + "=" * 100)
    print("AGGREGATE VALIDATION RESULTS")
    print("=" * 100)

    if total_words > 0:
        print(f"\nAcross {len(user_summaries)} users:")
        print(f"  Total unique word translations:      {total_words:,}")
        print(f"  Translated only once (stable):       {words_translated_once:,} ({words_translated_once/total_words*100:.1f}%)")
        print(f"  Translated multiple times:           {words_translated_multiple:,} ({words_translated_multiple/total_words*100:.1f}%)")
        print(f"    - Re-translated after ≥7 days:     {words_retranslated_after_7_days:,} ({words_retranslated_after_7_days/total_words*100:.1f}%)")
        print(f"    - Re-translated after ≥30 days:    {words_retranslated_after_30_days:,} ({words_retranslated_after_30_days/total_words*100:.1f}%)")
        print(f"    - Re-translated after ≥90 days:    {words_retranslated_after_90_days:,} ({words_retranslated_after_90_days/total_words*100:.1f}%)")

        print(f"\n" + "-" * 80)
        print("INTERPRETATION FOR PAPER:")
        print("-" * 80)
        print(f"""
  FINDING 1: Word Stability Rate
  • {words_translated_once/total_words*100:.1f}% of words were translated once and never again
  • This suggests learners typically LEARN words from a single lookup
  • Supports the theory: if a word isn't translated, it's likely known

  FINDING 2: Re-translation as Validation Failure
  • Only {words_retranslated_after_30_days/total_words*100:.1f}% of words were re-translated after a 30+ day gap
  • These represent cases where our "known" prediction might fail
  • However, some re-translations may be due to:
    - Forgetting (expected with spaced repetition)
    - Different word sense/context
    - Verification lookups (checking understanding)

  FINDING 3: Threshold Recommendation
  • A word encountered without translation for 30+ days can be considered "known"
    with ~{100 - words_retranslated_after_30_days/total_words*100:.0f}% confidence
  • For more conservative estimates, use 90-day threshold
    (~{100 - words_retranslated_after_90_days/total_words*100:.0f}% confidence)
""")

    # Deeper analysis: encounters before first translation
    print("\n" + "=" * 100)
    print("VALIDATION 2: How many times do learners see a word BEFORE translating it?")
    print("=" * 100)

    # Pick a few representative users
    sample_users = [u for u in users if u.articles_read >= 30][:3]

    for user in sample_users:
        print(f"\n{user.name} ({user.language}, {user.articles_read} articles):")
        print("-" * 60)

        encounters = analyze_encounters_before_translation(user.id, user.language_id)

        if encounters:
            # Distribution of encounters before first translation
            bins = {'0': 0, '1-2': 0, '3-5': 0, '6-10': 0, '11-20': 0, '20+': 0}
            for word, count, _ in encounters:
                if count == 0:
                    bins['0'] += 1
                elif count <= 2:
                    bins['1-2'] += 1
                elif count <= 5:
                    bins['3-5'] += 1
                elif count <= 10:
                    bins['6-10'] += 1
                elif count <= 20:
                    bins['11-20'] += 1
                else:
                    bins['20+'] += 1

            total = len(encounters)
            print(f"  Articles containing word BEFORE first translation:")
            for bin_name, count in bins.items():
                pct = count / total * 100 if total > 0 else 0
                bar = "#" * int(pct / 2)
                print(f"    {bin_name:>6} articles: {count:4d} ({pct:5.1f}%) {bar}")

            # Show examples of words seen many times before translation
            high_exposure = [(w, c) for w, c, _ in encounters if c >= 5][:5]
            if high_exposure:
                print(f"\n  Examples of words seen 5+ times before translation:")
                for word, count in high_exposure:
                    print(f"    '{word}': seen in {count} articles before first lookup")


if __name__ == "__main__":
    main()
