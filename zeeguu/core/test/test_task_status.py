import os
import subprocess
import sys

from zeeguu.operations import task_status


def _use(tmp_path, monkeypatch):
    monkeypatch.setattr(task_status, "TASK_STATUS_DIR", str(tmp_path))
    monkeypatch.setattr(task_status, "_summary", None)


def test_a_run_is_recorded_with_its_summary(tmp_path, monkeypatch):
    _use(tmp_path, monkeypatch)

    task_status.set_summary("422 users, 33 audio generated")
    task_status.record("precompute_audio", 1000, 1090, 0)

    [run] = task_status.read_all(now=1100)
    assert run["task"] == "precompute_audio"
    assert run["ok"] and not run["late"]
    assert run["duration_s"] == 90
    assert run["summary"] == "422 users, 33 audio generated"


def test_a_failed_run_is_not_ok(tmp_path, monkeypatch):
    _use(tmp_path, monkeypatch)

    task_status.record("feed_health", 1000, 1010, 1)
    task_status.record("prefetch", 1000, 1010, None, error="KeyError: 'x'")

    assert [r["ok"] for r in task_status.read_all(now=1100)] == [False, False]


def test_a_daily_task_is_late_once_well_past_its_usual_interval(tmp_path, monkeypatch):
    _use(tmp_path, monkeypatch)
    day = 86400
    for start in (0, day, 2 * day):
        task_status.record("daily_report", start, start + 60, 0)

    assert not task_status.read_all(now=2 * day + day)[0]["late"]
    assert task_status.read_all(now=2 * day + 2 * day)[0]["late"]


def test_one_run_is_too_little_history_to_be_late(tmp_path, monkeypatch):
    _use(tmp_path, monkeypatch)
    task_status.record("weekly_report", 0, 60, 0)

    assert not task_status.read_all(now=10**9)[0]["late"]


def test_traced_task_records_the_script_and_its_summary(tmp_path, monkeypatch):
    script = tmp_path / "job.py"
    script.write_text(
        "from zeeguu.operations.task_status import set_summary\n"
        "set_summary('did 3 things')\n"
    )
    status_dir = tmp_path / "tasks"

    subprocess.run(
        [sys.executable, "-m", "zeeguu.operations.traced_task", "demo", str(script)],
        env={**os.environ, "TASK_STATUS_DIR": str(status_dir)},
        check=True,
    )

    monkeypatch.setattr(task_status, "TASK_STATUS_DIR", str(status_dir))
    [run] = task_status.read_all()
    assert run["ok"] and run["summary"] == "did 3 things"


def test_traced_task_records_a_crash(tmp_path, monkeypatch):
    script = tmp_path / "job.py"
    script.write_text("raise ValueError('boom')\n")
    status_dir = tmp_path / "tasks"

    result = subprocess.run(
        [sys.executable, "-m", "zeeguu.operations.traced_task", "demo", str(script)],
        env={**os.environ, "TASK_STATUS_DIR": str(status_dir)},
    )

    assert result.returncode != 0
    monkeypatch.setattr(task_status, "TASK_STATUS_DIR", str(status_dir))
    [run] = task_status.read_all()
    assert not run["ok"] and run["error"] == "ValueError: boom"
