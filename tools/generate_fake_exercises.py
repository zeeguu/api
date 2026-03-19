#!/usr/bin/env python
import argparse
import os
import random
import sys
from datetime import datetime, timedelta
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# REQUIRED: Initialize Flask app context for database access
from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model.user import User
from zeeguu.core.model.friend import Friend
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.phrase import Phrase
from zeeguu.core.model.language import Language
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.model.exercise_outcome import ExerciseOutcome
from zeeguu.core.model.exercise_source import ExerciseSource


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate fake Exercise rows for user and friend leaderboards."
    )
    parser.add_argument(
        "--target-user-id",
        type=int,
        default=5,
        help="User ID whose friend network should receive exercise rows (default: 5).",
    )
    parser.add_argument(
        "--total-exercises",
        type=int,
        default=250,
        help="Total number of fake Exercise rows to create (default: 250).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Spread fake exercise timestamps in the last N days (default: 30).",
    )
    return parser.parse_args()


def random_datetime_in_last_days(days):
    now = datetime.now()
    start = now - timedelta(days=days)
    delta_seconds = int((now - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, max(delta_seconds, 1)))


def get_target_users(target_user_id):
    target_user = User.query.filter_by(id=target_user_id).first()
    if not target_user:
        print(f"Warning: target user {target_user_id} not found. Falling back to recent users.")
        fallback_users = User.query.order_by(User.id.desc()).limit(5).all()
        return fallback_users

    users = [target_user]
    users.extend(Friend.get_friends(target_user_id))

    unique_users = {}
    for user in users:
        unique_users[user.id] = user

    return list(unique_users.values())


def ensure_meanings_exist():
    existing_count = db.session.query(Meaning.id).count()
    if existing_count > 0:
        return

    bootstrap_pairs = [
        ("book", "en", "Buch", "de"),
        ("house", "en", "Haus", "de"),
        ("water", "en", "Wasser", "de"),
        ("friend", "en", "Freund", "de"),
        ("school", "en", "Schule", "de"),
        ("city", "en", "Stadt", "de"),
        ("sun", "en", "Sonne", "de"),
        ("food", "en", "Essen", "de"),
        ("music", "en", "Musik", "de"),
        ("train", "en", "Zug", "de"),
        ("dog", "en", "Hund", "de"),
        ("cat", "en", "Katze", "de"),
    ]

    def get_or_create_phrase(content, lang_code):
        language = Language.find_or_create(lang_code)
        phrase = (
            Phrase.query.filter(Phrase.content == content)
            .filter(Phrase.language_id == language.id)
            .first()
        )
        if phrase:
            return phrase

        db.session.execute(
            text(
                """
                INSERT INTO phrase (language_id, content)
                VALUES (:language_id, :content)
                """
            ),
            {"language_id": language.id, "content": content},
        )
        db.session.commit()

        return (
            Phrase.query.filter(Phrase.content == content)
            .filter(Phrase.language_id == language.id)
            .first()
        )

    for origin, origin_lang, translation, translation_lang in bootstrap_pairs:
        origin_phrase = get_or_create_phrase(origin, origin_lang)
        translation_phrase = get_or_create_phrase(translation, translation_lang)

        exists = (
            Meaning.query.filter(Meaning.origin_id == origin_phrase.id)
            .filter(Meaning.translation_id == translation_phrase.id)
            .first()
        )
        if exists:
            continue

        meaning = Meaning(origin=origin_phrase, translation=translation_phrase)
        db.session.add(meaning)

    db.session.commit()


def ensure_user_words(users):
    """
    Ensure every target user has at least a few UserWord rows so Exercise rows
    can be linked through Exercise.user_word_id.
    """
    ensure_meanings_exist()

    all_meaning_ids = [m.id for m in db.session.query(Meaning.id).all()]
    if not all_meaning_ids:
        raise RuntimeError("No Meaning rows found. Cannot create UserWord/Exercise data.")

    created_user_words = 0
    user_to_words = {}

    for user in users:
        words = UserWord.query.filter_by(user_id=user.id).all()
        if not words:
            sample_size = min(8, len(all_meaning_ids))
            sampled_meaning_ids = random.sample(all_meaning_ids, sample_size)
            for meaning_id in sampled_meaning_ids:
                meaning = Meaning.query.filter_by(id=meaning_id).first()
                if not meaning:
                    continue
                uw = UserWord(user=user, meaning=meaning)
                db.session.add(uw)
                created_user_words += 1
            db.session.commit()
            words = UserWord.query.filter_by(user_id=user.id).all()

        user_to_words[user.id] = words

    return user_to_words, created_user_words


def ensure_exercise_metadata():
    outcome_pool = [
        ExerciseOutcome.CORRECT,
        "W",
        "HC",
        "TC",
        ExerciseOutcome.TOO_EASY,
    ]

    outcomes = {}
    for outcome_name in outcome_pool:
        outcomes[outcome_name] = ExerciseOutcome.find_or_create(db.session, outcome_name)

    source = ExerciseSource.find_or_create(
        db.session, ExerciseSource.TOP_BOOKMARKS_MINI_EXERCISE
    )
    return outcomes, source


def generate_exercises(users, user_to_words, outcomes, source, total_exercises, days):
    created = 0

    weighted_outcomes = [
        ExerciseOutcome.CORRECT,
        ExerciseOutcome.CORRECT,
        ExerciseOutcome.CORRECT,
        "W",
        "HC",
        "TC",
        ExerciseOutcome.TOO_EASY,
    ]

    for _ in range(total_exercises):
        user = random.choice(users)
        words = user_to_words.get(user.id, [])
        if not words:
            continue

        word = random.choice(words)
        outcome_name = random.choice(weighted_outcomes)
        outcome = outcomes[outcome_name]

        exercise = Exercise(
            outcome=outcome,
            source=source,
            solving_speed=random.randint(1500, 22000),
            time=random_datetime_in_last_days(days),
            session_id=None,
            user_word=word,
            feedback="",
        )
        db.session.add(exercise)
        created += 1

    db.session.commit()
    return created


def main():
    args = parse_args()

    users = get_target_users(args.target_user_id)
    if not users:
        raise RuntimeError("No users available to seed exercise data.")

    user_to_words, created_user_words = ensure_user_words(users)
    outcomes, source = ensure_exercise_metadata()
    created_exercises = generate_exercises(
        users,
        user_to_words,
        outcomes,
        source,
        args.total_exercises,
        args.days,
    )

    print(f"Target users: {[u.id for u in users]}")
    print(f"Created UserWord rows: {created_user_words}")
    print(f"Created Exercise rows: {created_exercises}")


if __name__ == "__main__":
    main()
