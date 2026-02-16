# -*- coding: utf8 -*-
from hashlib import sha1, sha256
import bcrypt

# Prefix to identify bcrypt hashes vs legacy SHA1 hashes
BCRYPT_PREFIX = "$2b$"


def text_hash(text: str) -> str:
    """
    :param text: str:
    :return: str
    """
    if isinstance(text, str):
        text = text.encode("utf8")
    return sha1(text).hexdigest()


def long_hash(text: str) -> str:
    """
    :param text: str:
    :return: str
    """
    if isinstance(text, str):
        text = text.encode("utf8")
    return sha256(text).hexdigest()


def password_hash_bcrypt(password: str) -> str:
    """
    Hash a password using bcrypt (secure, modern algorithm).
    Returns the full bcrypt hash string including salt.
    """
    password_bytes = password.encode("utf-8")
    # Use 12 rounds (2^12 = 4096 iterations) - good balance of security and speed
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password_bcrypt(password: str, hashed: str) -> bool:
    """
    Verify a password against a bcrypt hash.
    """
    try:
        password_bytes = password.encode("utf-8")
        hashed_bytes = hashed.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def is_bcrypt_hash(hashed: str) -> bool:
    """
    Check if a hash is a bcrypt hash (vs legacy SHA1).
    """
    return hashed.startswith(BCRYPT_PREFIX)


def password_hash(password: str, salt: bytes) -> str:
    """
    DEPRECATED: Legacy SHA1 password hashing.
    Only used for verifying existing passwords during migration.
    New passwords should use password_hash_bcrypt().
    """
    hash_ = password.encode("utf8")
    for i in range(1000):
        hash_ = sha1(hash_ + salt).digest()
    return hash_.hex()
