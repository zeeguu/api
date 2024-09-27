from pathlib import Path
import os

MODULE_PATH = Path(__file__).parent.absolute()
PATH_TO_NAME_FILE = os.path.join(MODULE_PATH, "data", "name-list.txt")
PATH_TO_CITY_FILE = os.path.join(MODULE_PATH, "data", "city-names.txt")


def load_proper_name_list():
    proper_name_list = set()
    for file in [PATH_TO_NAME_FILE, PATH_TO_CITY_FILE]:
        with open(file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                proper_name_list.add(line.strip().lower())
    return proper_name_list
