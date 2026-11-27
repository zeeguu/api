import random
from typing import Optional

from zeeguu.core.model.db import db



class UserAvatar(db.Model):
    __tablename__ = "user_avatar"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    image_name = db.Column(db.String(100))
    character_color = db.Column(db.String(7))
    background_color = db.Column(db.String(7))
    # Curated paired palettes (synced with web/src/profile/avatarOptions.js).
    # Each index pairs a foreground/accent hex with a soft pastel background.
    AVATAR_CHARACTER_COLORS = [
        "#D97706",  # Amber
        "#C2410C",  # Terracotta
        "#E11D48",  # Rose
        "#7C3AED",  # Plum
        "#2563EB",  # Cobalt
        "#0D9488",  # Teal
        "#15803D",  # Forest
        "#334155",  # Slate
    ]
    AVATAR_BACKGROUND_COLORS = [
        "#FEF3C7",  # Amber
        "#FFEDD5",  # Terracotta
        "#FFE4E6",  # Rose
        "#EDE9FE",  # Plum
        "#DBEAFE",  # Cobalt
        "#CCFBF1",  # Teal
        "#DCFCE7",  # Forest
        "#E2E8F0",  # Slate
    ]

    # Maps auto-generated username nouns (including multilingual creature and
    # learner-persona words) to matching illustrated avatar IDs in web.
    HANDLE_AVATAR_MAP = {
        # Colibri / hummingbird (FR/ES/RO, DE/DA, PT)
        "colibri": ("colibri", "watercolor-colibri"),
        "kolibri": ("colibri", "watercolor-colibri"),
        "beijaflor": ("colibri", "watercolor-colibri"),
        # Dragonfly (EN, DE/FR/NL, IT, JP, DA)
        "dragonfly": ("dragonfly", "watercolor-dragonfly"),
        "libelle": ("dragonfly", "watercolor-dragonfly"),
        "libellula": ("dragonfly", "watercolor-dragonfly"),
        "tonbo": ("dragonfly", "watercolor-dragonfly"),
        "guldsmed": ("dragonfly", "watercolor-dragonfly"),
        # Butterfly (EN, FR, ES, IT)
        "butterfly": ("butterfly", "watercolor-butterfly"),
        "papillon": ("butterfly", "watercolor-butterfly"),
        "mariposa": ("butterfly", "watercolor-butterfly"),
        "farfalla": ("butterfly", "watercolor-butterfly"),
        # Swan (EN, DA, FR, IT)
        "swan": ("swan",),
        "svane": ("swan",),
        "cygne": ("swan",),
        "cigno": ("swan",),
        # Cat (EN, JP, FR, IT)
        "cat": ("cat", "watercolor-cat"),
        "neko": ("cat", "watercolor-cat"),
        "chaton": ("cat", "watercolor-cat"),
        "gatto": ("cat", "watercolor-cat"),
        # Giraffe (EN, IT, ES)
        "giraffe": ("giraffe", "watercolor-giraffe"),
        "giraffa": ("giraffe", "watercolor-giraffe"),
        "jirafa": ("giraffe", "watercolor-giraffe"),
        # Hippo (EN, DE)
        "hippo": ("hippo", "watercolor-hippo"),
        "nilpferd": ("hippo", "watercolor-hippo"),
        # Owl & Fox (EN + FR/DE/JP/IT -> watercolor portraits)
        "owl": ("watercolor-owl",),
        "hibou": ("watercolor-owl",),
        "eule": ("watercolor-owl",),
        "fox": ("watercolor-fox",),
        "renard": ("watercolor-fox",),
        "kitsune": ("watercolor-fox",),
        "volpe": ("watercolor-fox",),
        # Elephants & Zeeguu learner personas
        "elephant": (
            "elephant-book",
            "elephant-headphones",
            "elephant-glasses",
            "elephant-kimono",
            "elephant-beret",
        ),
        "elefant": (
            "elephant-book",
            "elephant-headphones",
            "watercolor-elephant-headphones",
            "watercolor-elephant-reading",
        ),
        "reader": ("elephant-book", "zeeguu-reader", "zeeguu-newspaper", "watercolor-elephant-reading"),
        "lecteur": ("elephant-book", "zeeguu-reader", "zeeguu-newspaper"),
        "leser": ("elephant-book", "zeeguu-newspaper", "watercolor-elephant-reading"),
        "listener": ("elephant-headphones", "zeeguu-headphones", "watercolor-elephant-headphones"),
        "flaneur": ("elephant-beret", "zeeguu-scarf"),
        "scholar": ("elephant-glasses", "zeeguu-mug"),
        "polyglot": ("zeeguu-dapper", "zeeguu-bowtie", "zeeguu"),
        "traveler": ("elephant-kimono", "zeeguu-kimono", "zeeguu-blossom"),
    }

    user = db.relationship("User")

    def __init__(
            self,
            user_id,
            image_name=None,
            character_color=None,
            background_color=None
    ):
        self.user_id = user_id
        self.image_name = image_name
        self.character_color = character_color
        self.background_color = background_color

    def __repr__(self):
        return f"<UserAvatar User:{self.user_id}>"

    @classmethod
    def random_colors(cls):
        """Return a randomly paired (character_color, background_color) tuple."""
        idx = random.randrange(len(cls.AVATAR_CHARACTER_COLORS))
        return cls.AVATAR_CHARACTER_COLORS[idx], cls.AVATAR_BACKGROUND_COLORS[idx]

    @classmethod
    def image_name_for_handle(cls, handle: str) -> str:
        """Pick an avatar image_name matching an auto-generated username noun."""
        candidates = cls.HANDLE_AVATAR_MAP.get(handle)
        if candidates:
            return random.choice(candidates)
        return handle

    @classmethod
    def find(cls, user_id: int) -> Optional["UserAvatar"]:
        """
        Return the corresponding avatar for the given user.
        """
        return cls.query.filter_by(user_id=user_id).one_or_none()

    @classmethod
    def update_or_create(cls, user_id, image_name, character_color, background_color):
        """
        Update an existing avatar or create a new one for the specified user.
        Does not commit.
        """
        user_avatar = cls.find(user_id)
        if not user_avatar: 
            # Return new user avatar
            return UserAvatar(user_id, image_name, character_color, background_color)
        
        # Update the current user avatar
        if image_name:
            user_avatar.image_name = image_name
        if character_color:
            user_avatar.character_color = character_color
        if background_color:
            user_avatar.background_color = background_color

        return user_avatar
