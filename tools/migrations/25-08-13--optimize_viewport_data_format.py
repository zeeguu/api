#!/usr/bin/env python3

"""
Migration: Convert old viewport settings format to optimized format

Old format: {"scrollHeight":5479,"clientHeight":762,"textHeight":4691,"bottomRowHeight":482}
New format: {"viewportRatio":0.1554,"scrollHeight":5479,"clientHeight":762}

This reduces storage size by ~22% per event while maintaining all functionality.
"""

import zeeguu.core
import json
from zeeguu.core.model.user_activitiy_data import UserActivityData, EVENT_USER_SCROLL
from zeeguu.core.model import db
from datetime import datetime

def convert_viewport_format(old_viewport):
    """Convert old viewport format to new optimized format"""
    try:
        if isinstance(old_viewport, str):
            viewport_data = json.loads(old_viewport)
        else:
            viewport_data = old_viewport
            
        # Check if it's already in new format
        if 'viewportRatio' in viewport_data:
            return old_viewport  # Already converted
            
        # Check if we have the required fields for conversion
        if not all(key in viewport_data for key in ['scrollHeight', 'clientHeight']):
            return old_viewport  # Can't convert, keep as is
            
        # Calculate viewport ratio
        scroll_height = viewport_data['scrollHeight']
        client_height = viewport_data['clientHeight']
        bottom_row_height = viewport_data.get('bottomRowHeight', 0)  # Default to 0 if missing
        
        # Avoid division by zero
        if scroll_height - bottom_row_height > 0:
            viewport_ratio = client_height / (scroll_height - bottom_row_height)
        else:
            viewport_ratio = 0
            
        # Create new optimized format
        new_format = {
            'viewportRatio': round(viewport_ratio, 4),  # Round to 4 decimal places
            'scrollHeight': scroll_height,
            'clientHeight': client_height
        }
        
        return json.dumps(new_format)
        
    except (json.JSONDecodeError, KeyError, TypeError):
        # If conversion fails, keep original
        return old_viewport

def main():
    from zeeguu.api.app import create_app
    app = create_app()
    app.app_context().push()

    print("=== Viewport Data Format Optimization ===")
    
    # Count current state
    total_scroll = UserActivityData.query.filter(
        UserActivityData.event == EVENT_USER_SCROLL
    ).count()
    print(f"Total scroll events: {total_scroll}")
    
    # Find events with old format (have bottomRowHeight or textHeight)
    events_to_convert = UserActivityData.query.filter(
        UserActivityData.event == EVENT_USER_SCROLL,
        UserActivityData.value.like('%bottomRowHeight%')
    ).all()
    
    additional_events = UserActivityData.query.filter(
        UserActivityData.event == EVENT_USER_SCROLL,
        UserActivityData.value.like('%textHeight%')
    ).all()
    
    # Combine and deduplicate
    all_events = list(set(events_to_convert + additional_events))
    
    print(f"Found {len(all_events)} events with old viewport format to convert")
    
    if len(all_events) == 0:
        print("No events need conversion - migration complete")
        return
    
    # Convert in batches
    converted_count = 0
    failed_count = 0
    
    for i, event in enumerate(all_events):
        if i % 100 == 0:
            print(f"Processing event {i}/{len(all_events)}...")
            
        old_value = event.value
        new_value = convert_viewport_format(old_value)
        
        if new_value != old_value:
            event.value = new_value
            converted_count += 1
        else:
            failed_count += 1
            
        if (i + 1) % 500 == 0:
            # Commit in batches
            db.session.commit()
            print(f"Committed batch, converted {converted_count} so far")
    
    # Final commit
    db.session.commit()
    
    print(f"\n=== Migration Complete ===")
    print(f"Successfully converted: {converted_count} events")
    print(f"Kept unchanged: {failed_count} events")
    
    # Calculate storage savings
    if converted_count > 0:
        # Estimate based on average sizes
        old_size = 87  # Average bytes for old format
        new_size = 68  # Average bytes for new format
        total_savings = (old_size - new_size) * converted_count
        print(f"Estimated storage saved: {total_savings:,} bytes ({total_savings/1024:.1f} KB)")

if __name__ == "__main__":
    main()