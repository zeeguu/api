import os

current_folder = os.path.join(os.path.dirname(__file__), "")


def load_query(filename):
    query = ""
    with open(current_folder + filename + ".sql") as f:
        for line in f:
            query += line
    return query
