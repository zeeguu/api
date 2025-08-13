#!/usr/bin/env python3

"""
Migration: Clean up malformed scroll data from July 14, 2025 onwards

Issue: Frontend sent scroll count instead of viewport settings in 'value' field
This broke the reading sessions feature which expects viewport settings as JSON.

Impact: Removes ~1878 malformed events (~4.5% of total), keeps 95.5% good data
"""

import zeeguu.core
from zeeguu.core.model.user_activitiy_data import UserActivityData, EVENT_USER_SCROLL
from zeeguu.core.model import db
from datetime import datetime

def main():
    from zeeguu.api.app import create_app
    app = create_app()
    app.app_context().push()

    print("=== Scroll Data Cleanup Migration ===")
    
    # Count current state
    total_before = UserActivityData.query.filter(UserActivityData.event == EVENT_USER_SCROLL).count()
    print(f"Total scroll events before cleanup: {total_before}")

    # Find malformed events in entire dataset (no date filter)
    # Original date filter was too restrictive - check all data
    all_events = UserActivityData.query.filter(
        UserActivityData.event == EVENT_USER_SCROLL
    ).all()

    malformed_ids = []
    for event in all_events:
        if event.value and isinstance(event.value, str):
            # Check if value is numeric (like "22") or doesn't start with JSON
            if event.value.isdigit() or (event.value != '' and not event.value.startswith('{')):
                malformed_ids.append(event.id)

    print(f"Found {len(malformed_ids)} malformed scroll events to delete")
    
    if len(malformed_ids) == 0:
        print("No malformed events found - migration complete")
        return

    # Delete malformed events in batches
    batch_size = 1000
    deleted_total = 0
    
    for i in range(0, len(malformed_ids), batch_size):
        batch_ids = malformed_ids[i:i + batch_size]
        
        # Delete batch
        deleted_count = UserActivityData.query.filter(
            UserActivityData.id.in_(batch_ids)
        ).delete(synchronize_session=False)
        
        deleted_total += deleted_count
        print(f"Deleted batch {i//batch_size + 1}: {deleted_count} events")
    
    # Commit the changes
    db.session.commit()
    
    # Verify final state
    total_after = UserActivityData.query.filter(UserActivityData.event == EVENT_USER_SCROLL).count()
    print(f"Total scroll events after cleanup: {total_after}")
    print(f"Successfully deleted {deleted_total} malformed scroll events")
    print(f"Kept {total_after} events with proper viewport settings")

if __name__ == "__main__":
    main()