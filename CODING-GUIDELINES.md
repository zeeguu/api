# Coding Conventions for the Zeeguu API

## SQLAlchemy Related
- [Adding altered objects to sessions without committing](https://github.com/zeeguu/api/discussions/210)

## Records: query results and value objects

When a function puts data together from several rows for one use (a query
result: `words_heard.HeardLesson`, built by `heard_lessons()`), or a piece of
code passes a small value around (`lesson_script.challenges.Challenge`), give it a type:

- **A frozen dataclass**, not a `namedtuple` and not a dict: one line per
  field, with its type, its default and a short comment saying what it holds
  and which table it comes from. `@dataclass(frozen=True)`: it is read, never
  changed.
- **Defined next to the function that builds it**, at the top of its module,
  and named after what it is (`HeardLesson`, `ReviewItem`), not after where
  it comes from. Not in a package of records: a record means something only
  with the code that builds and reads it.
- **Not a table.** If every field comes from stored rows, the record is a view
  for one use; storing it would copy those facts and let the copy go stale.
  Facts that need to last get their own table (`audio_challenge`).
- **Why not just pass the ORM objects**: the logic that uses the record can
  then be tested as plain functions, built by hand in the test, with no
  database (`test_lesson_script.py`).

Older `namedtuple`s (`GeneratedScript`) are converted when they next change.
