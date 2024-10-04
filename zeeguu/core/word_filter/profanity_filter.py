from pathlib import Path
import os

SKIP_FILES = set(["README.md", "USERS.md", "LICENSE"])
MODULE_PATH = Path(__file__).parent.absolute()
PATH_TO_WORD_LIST = os.path.join(MODULE_PATH, "data", "bad-words")


def load_bad_words():
    bad_word_list = set()
    for f in os.listdir(PATH_TO_WORD_LIST):
        path_to_file = os.path.join(PATH_TO_WORD_LIST, f)
        if os.path.isfile(path_to_file) and f not in SKIP_FILES:
            with open(path_to_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    bad_word_list.add(line.strip().lower())
    return bad_word_list
