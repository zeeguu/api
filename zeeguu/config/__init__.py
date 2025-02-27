from os import getenv, path

# Resources are immutable data (e.g. stanza models, etc.)
ZEEGUU_RESOURCES_FOLDER = getenv("ZEEGUU_RESOURCES_FOLDER") or path.expanduser("~")

# Data folder is for zeeguu-created data (e.g. speech files, etc.)
ZEEGUU_DATA_FOLDER = getenv("ZEEGUU_DATA_FOLDER")
