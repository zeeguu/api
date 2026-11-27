import re

from zeeguu.core.model.user import User
from zeeguu.core.model.user_avatar import UserAvatar
from zeeguu.core.test.model_test_mixin import ModelTestMixIn


# All non-classic illustrated / Zeeguu avatar IDs supported in web/src/profile/avatarOptions.js.
WEB_NEW_AVATAR_IDS = {
    "colibri",
    "dragonfly",
    "butterfly",
    "swan",
    "cat",
    "giraffe",
    "hippo",
    "elephant-book",
    "elephant-headphones",
    "elephant-glasses",
    "elephant-kimono",
    "elephant-beret",
    "zeeguu",
    "zeeguu-blossom",
    "zeeguu-kimono",
    "zeeguu-headphones",
    "zeeguu-bowtie",
    "zeeguu-dapper",
    "zeeguu-newspaper",
    "zeeguu-reader",
    "zeeguu-mug",
    "zeeguu-scarf",
    "watercolor-colibri",
    "watercolor-dragonfly",
    "watercolor-butterfly",
    "watercolor-cat",
    "watercolor-giraffe",
    "watercolor-hippo",
    "watercolor-owl",
    "watercolor-fox",
    "watercolor-elephant-headphones",
    "watercolor-elephant-reading",
}


class UserAvatarTest(ModelTestMixIn):
    def test_curated_palettes_are_paired_and_valid_hex(self):
        assert len(UserAvatar.AVATAR_CHARACTER_COLORS) == len(UserAvatar.AVATAR_BACKGROUND_COLORS) == 8
        hex_re = re.compile(r"^#[0-9A-Fa-f]{6}$")
        for fg, bg in zip(UserAvatar.AVATAR_CHARACTER_COLORS, UserAvatar.AVATAR_BACKGROUND_COLORS):
            assert hex_re.match(fg)
            assert hex_re.match(bg)

        fg, bg = UserAvatar.random_colors()
        idx = UserAvatar.AVATAR_CHARACTER_COLORS.index(fg)
        assert UserAvatar.AVATAR_BACKGROUND_COLORS[idx] == bg

    def test_every_default_and_language_handle_maps_to_valid_web_avatar_and_regex(self):
        assert len(User.ANIMALS) == len(set(User.ANIMALS))
        all_nouns = set(User.ANIMALS)
        for lang_code, nouns in User.LANGUAGE_HANDLES.items():
            assert len(nouns) == len(set(nouns)), f"Duplicate noun in {lang_code}"
            all_nouns.update(nouns)

        for noun in all_nouns:
            assert noun in UserAvatar.HANDLE_AVATAR_MAP, f"Missing avatar mapping for handle '{noun}'"
            candidates = UserAvatar.HANDLE_AVATAR_MAP[noun]
            assert len(candidates) > 0
            for avatar_id in candidates:
                assert avatar_id in WEB_NEW_AVATAR_IDS
                assert len(avatar_id) <= 100

            sample_username = f"{User.ADJECTIVES[0]}_{noun}"
            assert len(sample_username) <= User.MAX_USERNAME_LENGTH
            assert re.fullmatch(User.USERNAME_VALIDATION_REGEX, sample_username)

    def test_image_name_for_handle_falls_back_for_legacy_animals(self):
        assert UserAvatar.image_name_for_handle("otter") == "otter"
        assert UserAvatar.image_name_for_handle("guldsmed") in ("dragonfly", "watercolor-dragonfly")

    def test_generate_unique_username_matches_learned_language(self):
        username, adjective, noun = User.generate_unique_username(language_code="da")
        assert adjective in User.ADJECTIVES
        assert noun in User.LANGUAGE_HANDLES["da"]
        assert re.fullmatch(User.USERNAME_VALIDATION_REGEX, username)
        assert UserAvatar.image_name_for_handle(noun) in WEB_NEW_AVATAR_IDS

        _, _, pt_noun = User.generate_unique_username(language_code="pt")
        assert pt_noun in User.LANGUAGE_HANDLES["pt"]

        # English or unsupported codes draw from the default English/universal pool
        _, _, en_noun = User.generate_unique_username(language_code="en")
        assert en_noun in User.ANIMALS
        assert en_noun != "beijaflor"
        assert en_noun != "guldsmed"
