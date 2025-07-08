#!/usr/bin/env python
"""
Command-line tool to update meaning frequencies for a range of IDs.

Usage:
    python -m tools.update_meaning_frequencies --start 1 --end 100
    python -m tools.update_meaning_frequencies --ids 5,10,15,20
    python -m tools.update_meaning_frequencies --start 1 --end 10 --dry-run
"""

import argparse
import sys
import time

from zeeguu.api.app import create_app
from zeeguu.core.model import db, Meaning
from zeeguu.core.model.meaning_frequency_classifier import MeaningFrequencyClassifier
from zeeguu.logging import log


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Update meaning frequencies using AI classification"
    )

    # ID range options
    parser.add_argument("--start", type=int, help="Starting meaning ID (inclusive)")
    parser.add_argument("--end", type=int, help="Ending meaning ID (inclusive)")
    parser.add_argument(
        "--ids", type=str, help="Comma-separated list of specific IDs to update"
    )

    # Options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument(
        "--force", action="store_true", help="Update even if frequency already exists"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between API calls in seconds (default: 0.5)",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.ids:
        if args.start or args.end:
            parser.error("Cannot use --ids with --start/--end")
    elif not (args.start and args.end):
        parser.error("Must provide either --ids or both --start and --end")

    if args.start and args.end and args.start > args.end:
        parser.error("Start ID must be less than or equal to end ID")

    return args


def get_meanings_to_update(args):
    """Get the list of meanings to update based on arguments."""
    if args.ids:
        # Parse comma-separated IDs
        id_list = [int(id_str.strip()) for id_str in args.ids.split(",")]
        meanings = Meaning.query.filter(Meaning.id.in_(id_list)).all()

        # Report any missing IDs
        found_ids = {m.id for m in meanings}
        missing_ids = set(id_list) - found_ids
        if missing_ids:
            log(f"Warning: IDs not found in database: {sorted(missing_ids)}")
    else:
        # Get range of IDs
        query = Meaning.query.filter(Meaning.id >= args.start, Meaning.id <= args.end)

        if not args.force:
            # Skip meanings that already have frequency
            query = query.filter(Meaning.frequency.is_(None))

        meanings = query.order_by(Meaning.id).all()

    return meanings


def format_meaning_info(meaning):
    """Format meaning information for display."""
    return (
        f"ID {meaning.id}: "
        f"{meaning.origin.content} ({meaning.origin.language.code}) → "
        f"{meaning.translation.content} ({meaning.translation.language.code})"
    )


def main():
    """Main function."""
    args = parse_arguments()

    # Initialize app context
    app = create_app()
    app.app_context().push()

    # Initialize classifier
    try:
        classifier = MeaningFrequencyClassifier()
    except ValueError as e:
        print(f"Error: {e}")
        print("Make sure ANTHROPIC_API_KEY environment variable is set")
        sys.exit(1)

    # Get meanings to update
    meanings = get_meanings_to_update(args)

    if not meanings:
        print("No meanings found to update")
        return

    print(f"Found {len(meanings)} meanings to process")

    if args.dry_run:
        print("\n=== DRY RUN MODE - No changes will be made ===")

    # Process each meaning
    success_count = 0
    error_count = 0
    skipped_count = 0

    for i, meaning in enumerate(meanings, 1):
        print(f"\n[{i}/{len(meanings)}] {format_meaning_info(meaning)}")

        # Check if already has frequency
        if meaning.frequency and not args.force:
            print(f"  → Skipping: already has frequency '{meaning.frequency.value}'")
            skipped_count += 1
            continue

        if meaning.frequency:
            print(f"  → Current frequency: '{meaning.frequency.value}' (will update)")

        if args.dry_run:
            print("  → Would classify and update")
            success_count += 1
        else:
            try:
                # Classify and update
                print("  → Classifying...", end="", flush=True)

                import time
                start_time = time.time()
                success = classifier.classify_and_update_meaning(meaning, db.session)
                end_time = time.time()
                execution_time = end_time - start_time
                print(f"Execution time: {execution_time:.4f} seconds")

                if success:
                    print(
                        f" ✓ Updated to: '{meaning.frequency.value}, {meaning.phrase_type.value}'"
                    )
                    success_count += 1
                else:
                    print(" ✗ Classification failed")
                    error_count += 1

            except Exception as e:
                print(f" ✗ Error: {e}")
                error_count += 1
                db.session.rollback()

        # Rate limiting
        if i < len(meanings) and not args.dry_run:
            time.sleep(args.delay)

    # Summary
    print("\n=== Summary ===")
    print(f"Total processed: {len(meanings)}")
    print(f"Successfully updated: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Skipped: {skipped_count}")

    if args.dry_run:
        print("\nThis was a dry run. Use without --dry-run to make actual changes.")


if __name__ == "__main__":
    main()
