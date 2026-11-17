"""
Run slow, database-free work (LLM calls, HTTP requests) on many database rows
at the same time, while keeping every database access on the main thread.
"""
from concurrent.futures import ThreadPoolExecutor
from itertools import batched


def process_in_parallel(model, ids, prepare, work, workers=6):
    """Run `work` on the rows of `model` with these ids, several at a time.

    You give two functions:

      prepare(row)  runs on the main thread, one row at a time. It copies what
                    `work` needs out of the row into plain data (e.g. a dict).
                    Return None to skip the row.

      work(data)    runs in a worker thread, several at the same time. It gets
                    the plain data from `prepare` and must NOT touch the
                    database: SQLAlchemy sessions are not safe to share
                    between threads.

    You get back, one by one and in the order of `ids`:

        (data, result, error)

    If `work` raised, `error` is the exception and `result` is None; otherwise
    `error` is None. A failing row (in `prepare` or `work`) gives you its error
    instead of stopping the whole run; if `prepare` failed, `data` is
    {"id": <the row's id>}. You handle (e.g. save) each result in your own loop,
    which is back on the main thread.

    Example:
        for data, result, error in process_in_parallel(Article, ids, prepare, work):
            if error:
                print("failed:", data["id"], error)
            else:
                save(data["id"], result)

    Memory: rows are loaded `workers * 4` at a time, and each chunk's rows are
    removed from the session before the next chunk loads. Commit what you
    save before moving on: changes to those rows that were not yet flushed
    are lost when they are removed.
    """
    # Imported here so this module can be imported before the app exists.
    from zeeguu.core.model import db

    # Give every worker a few rows to do, so none of them sits idle.
    chunk_size = workers * 4

    def work_without_raising(data):
        # An exception in a worker thread would otherwise stop the whole loop
        # below. Returning it as a value lets the caller decide what to do.
        try:
            return data, work(data), None
        except Exception as error:
            return data, None, error

    # A ThreadPoolExecutor is a group of `workers` threads that wait for jobs.
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        for chunk_ids in batched(ids, chunk_size):
            # The database returns rows in its own order; put them back in
            # the order of `ids`.
            rows = model.query.filter(model.id.in_(chunk_ids)).all()
            position = {row_id: i for i, row_id in enumerate(chunk_ids)}
            rows.sort(key=lambda row: position[row.id])

            jobs = []
            for row in rows:
                try:
                    data = prepare(row)
                except Exception as error:
                    yield {"id": row.id}, None, error
                    continue
                if data is not None:
                    jobs.append(data)

            # pool.map hands the jobs out to the threads, which run them at the
            # same time. It gives the results back in the same order as `jobs`,
            # each one as soon as it (and the ones before it) are done.
            results = pool.map(work_without_raising, jobs)

            # Pass each result on to the caller's `for` loop. This function
            # pauses here until the caller asks for the next result, so the
            # caller saves each one before we go on.
            for result in results:
                yield result

            # The caller has handled the whole chunk: forget its rows so that
            # memory does not grow with every chunk. Only these rows: the
            # caller's other objects stay in the session.
            for row in rows:
                if row in db.session:
                    db.session.expunge(row)
    finally:
        # Normally all jobs are done here. If the caller stopped early (an
        # exception, Ctrl-C), drop the jobs that have not started, so we do
        # not keep paying for LLM calls nobody will read.
        pool.shutdown(wait=True, cancel_futures=True)
