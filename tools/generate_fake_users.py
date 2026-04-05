#!/usr/bin/env python
import sys
import os
import random
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# REQUIRED: Initialize Flask app context for database access
from zeeguu.api.app import create_app
from zeeguu.core.model import db
app = create_app()
app.app_context().push()

from zeeguu.core.model.user import User
from zeeguu.core.model.language import Language

def random_email():
    domains = ["example.com", "test.org", "mail.com", "demo.net"]
    name = f"user{random.randint(1000, 9999)}"
    return f"{name}@{random.choice(domains)}"

def random_name():
    first_names = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Jamie", "Robin", "Drew", "Avery"]
    last_names = ["Smith", "Johnson", "Lee", "Brown", "Garcia", "Martinez", "Davis", "Clark", "Lewis", "Walker"]
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def random_username():
    adjectives = User.ADJECTIVES
    nouns = User.NOUNS
    return f"{random.choice(adjectives)}_{random.choice(nouns)}_{random.randint(1,9999)}"

def random_language():
    codes = list(Language.LANGUAGE_NAMES.keys())
    return Language.find_or_create(random.choice(codes))

def main():
    num_users = 100
    created = 0
    for _ in range(num_users):
        email = random_email()
        name = random_name()
        username = random_username()
        password = "testpassword"
        learned_language = random_language()
        native_language = random_language()
        user = User(
            email=email,
            name=name,
            password=password,
            username=username,
            learned_language=learned_language,
            native_language=native_language
        )
        db.session.add(user)
        created += 1
    db.session.commit()
    print(f"Created {created} fake users.")

if __name__ == "__main__":
    main()
