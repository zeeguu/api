# -*- coding: utf8 -*-
from hashlib import sha1


def text_hash(text: str) -> str:
    """
    :param text: str:
    :return: str
    """
    if isinstance(text, str):
        text = text.encode("utf8")
    return sha1(text).hexdigest()


def password_hash(password: str, salt: bytes) -> str:
    """
    
    :return: bytes

    """
    hash_ = password.encode("utf8")
    for i in range(1000):
        hash_ = sha1(hash_ + salt).digest()
    return hash_.hex()
