#!/usr/bin/env python
"""
Daily integrity check script for UserWord data.

This should be run via cron daily to detect and report integrity issues.
Use --fix flag to automatically repair issues found.

Cron setup example:
    # Run daily at 3 AM
    0 3 * * * cd /path/to/zeeguu/api && /path/to/venv/bin/python -m tools._daily_integrity_check --fix >> /var/log/zeeguu_integrity.log 2>&1
"""
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# REQUIRED: Initialize Flask app context for database access
from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

from zeeguu.core.model import UserWord, Bookmark
from sqlalchemy import func
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Daily data integrity check for UserWords"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix issues found (default is report-only)"
    )
    parser.add_argument(
        "--skip-orphaned",
        action="store_true",
        help="Skip checking for orphaned UserWords (can be slow)"
    )

    args = parser.parse_args()

    print(f"\n{'='*80}")
    print(f"Zeeguu Daily Integrity Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}")

    if args.fix:
        print("MODE: Fix issues automatically")
    else:
        print("MODE: Report only (use --fix to repair issues)")

    print(f"\n{'='*80}")
    print("Running integrity checks...")
    print(f"{'='*80}\n")

    # Import and run the main integrity check
    from tools._check_and_fix_data_integrity import (
        check_preferred_bookmark_integrity,
        check_null_preferred_bookmarks,
        check_orphaned_user_words,
        fix_preferred_bookmark_issues,
        fix_null_preferred_bookmarks,
        fix_orphaned_user_words,
    )

    total_issues = 0
    dry_run = not args.fix

    # Check 1: Wrong preferred_bookmark_id
    wrong_preferred = check_preferred_bookmark_integrity()
    total_issues += fix_preferred_bookmark_issues(wrong_preferred, dry_run)

    # Check 2: NULL preferred_bookmark with bookmarks
    null_preferred = check_null_preferred_bookmarks()
    total_issues += fix_null_preferred_bookmarks(null_preferred, dry_run)

    # Check 3: Orphaned UserWords (optional, can be slow)
    if not args.skip_orphaned:
        orphaned = check_orphaned_user_words()
        total_issues += fix_orphaned_user_words(orphaned, dry_run)

    # Summary
    print(f"\n{'='*80}")
    print("DAILY CHECK SUMMARY")
    print(f"{'='*80}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total issues found: {total_issues}")

    if total_issues == 0:
        print("\n✓ Database integrity is good!")
        sys.exit(0)
    elif args.fix:
        print(f"\n✓ Fixed {total_issues} issues!")
        sys.exit(0)
    else:
        print(f"\n⚠ Found {total_issues} issues - run with --fix to repair them")
        print("   Example: python -m tools._daily_integrity_check --fix")
        sys.exit(1)  # Non-zero exit code for monitoring


if __name__ == "__main__":
    main()
