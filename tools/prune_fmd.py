#!/usr/bin/env python
"""
Prune the Flask Monitoring Dashboard database: delete requests older than
--weeks (default 4) together with their outliers, stack lines and exceptions.

Runs nightly from the ops crontab, in the run_task container, instead of via
FMD's own add_database_pruning_schedule(): that one runs inside every gunicorn
worker, so all of them would prune at once. The batched delete it relies on
needs Flask-MonitoringDashboard >= 5.0.4.

Usage:
  python tools/prune_fmd.py            # keep the last 4 weeks
  python tools/prune_fmd.py --weeks 8
"""

import argparse
import time

import flask_monitoringdashboard as dashboard

dashboard.config.init_from(envvar="FLASK_MONITORING_DASHBOARD_CONFIG")

from flask_monitoringdashboard.core.database_pruning import (  # noqa: E402
    prune_database_older_than_weeks,
)
from flask_monitoringdashboard.database import Request, session_scope  # noqa: E402


def count_requests():
    with session_scope() as session:
        return session.query(Request).count()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--weeks", type=int, default=4, help="weeks of data to keep")
    args = parser.parse_args()

    before = count_requests()
    start = time.time()
    prune_database_older_than_weeks(args.weeks, delete_custom_graph_data=True)
    after = count_requests()
    print(
        f"FMD prune (keep {args.weeks} weeks): {before} -> {after} requests, "
        f"{before - after} deleted in {time.time() - start:.1f}s"
    )


if __name__ == "__main__":
    main()
