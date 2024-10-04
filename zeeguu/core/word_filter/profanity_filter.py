from pathlib import Path
import os

SKIP_FILES = set(["README.md", "USERS.md", "LICENSE"])
MODULE_PATH = Path(__file__).parent.absolute()
BAD_WORDS_FOLDER = os.path.join(MODULE_PATH, "data", "bad-words")


def load_bad_words():
    bad_word_list = set()
    for f in os.listdir(BAD_WORDS_FOLDER):
        path_to_file = os.path.join(BAD_WORDS_FOLDER, f)
        if os.path.isfile(path_to_file) and f not in SKIP_FILES:
            with open(path_to_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    bad_word_list.add(line.strip().lower())
    return bad_word_list
