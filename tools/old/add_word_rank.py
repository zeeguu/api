from datetime import datetime
import zeeguu.core.model
from zeeguu.core.model.user_word import UserWord
from wordstats import Word

import zeeguu

db_session = zeeguu.core.model.db.session

words = UserWord.query.all()

print("starting...")
print(datetime.now())
i = 0
unsupported_languages = set()
for word in words:

    try:

        if word.rank:
            continue

        rank = Word.stats(word.word, word.language.code).rank
        if rank == 100000:
            continue

        # print(f"{word.id} {word.word} -> {rank}")
        word.rank = rank
        db_session.add(word)
        i += 1

        if i % 1000 == 0:
            print(f"current userword id: {word.id}")
            print(datetime.now())
            print("comitting... 1k")
            db_session.commit()
    except FileNotFoundError as e:
        # "[Errno 2] No such file or directory: '/Users/mlun/.venvs/z_env/lib/python3.9/site-packages/wordstats/language_data/hermitdave/2016/sq/sq_50k.txt'"
        import re

        res = re.match(".*2016/(.*)_50k", str(e))
        if res[1] not in unsupported_languages:
            unsupported_languages.add(res[1])
            print(res[1])

db_session.commit()
print(f"updated {i} words")

print("found unsupported languages: ")
print(unsupported_languages)
