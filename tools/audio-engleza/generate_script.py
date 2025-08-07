#!/usr/bin/env python3
"""
Audio-Engleza: Script generator for English lessons

This tool generates lesson scripts and saves them to files for manual editing.
After editing, use generate_audio.py to create the audio files.

Usage:
    python generate_script.py --english "to have" --romanian "a avea" --output scripts/to_have.txt
"""

import sys
import os
import argparse
from datetime import datetime
from zeeguu.api.app import create_app
from zeeguu.core.audio_lessons.script_generator import generate_lesson_script

# Configuration
SCRIPTS_DIR = "/Users/gh/zeeguu/audio-engleza.github.io/scripts"

def create_semantic_filename(english_phrase):
    """Create a semantic filename from the English phrase"""
    import re
    semantic_name = re.sub(r'[^a-zA-Z0-9\s]', '', english_phrase.lower())
    semantic_name = re.sub(r'\s+', '_', semantic_name.strip())
    return f"{semantic_name}.txt"

def generate_script_file(english_phrase, romanian_translation, output_file=None):
    """Generate lesson script and save to file"""
    
    # Create scripts directory if it doesn't exist
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    
    # Generate output filename if not provided
    if not output_file:
        output_file = os.path.join(SCRIPTS_DIR, create_semantic_filename(english_phrase))
    
    app = create_app()
    with app.app_context():
        try:
            print(f"Generating script for '{english_phrase}' -> '{romanian_translation}'...")
            
            # Use local prompt file
            local_prompt_path = os.path.join(os.path.dirname(__file__), "basic_english_for_elderly_romanian.txt")
            
            script = generate_lesson_script(
                origin_word=english_phrase,
                translation_word=romanian_translation,
                origin_language="en",
                translation_language="ro",
                cefr_level="A1",
                generator_prompt_file=local_prompt_path,
            )
            
            # Add metadata header to script file
            header = f"""# Audio-Engleza Lesson Script
# Generated: {datetime.now().isoformat()}
# English: {english_phrase}
# Romanian: {romanian_translation}
# 
# You can edit this script as needed, then use generate_audio.py to create the audio file
#
# Format: Each line should be "Speaker: Text [pause_seconds seconds]"
# Valid speakers: Teacher, Man, Woman
#
# ========================================

"""
            
            # Write script to file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(header + script)
            
            print(f"\n✅ Script generated successfully!")
            print(f"   File: {output_file}")
            print(f"   You can now edit this script and then use generate_audio.py to create the audio")
            print(f"\nGenerated Script Preview:")
            print("=" * 50)
            print(script)
            print("=" * 50)
            
            return output_file
            
        except Exception as e:
            print(f"Error generating script: {e}")
            return None

def main():
    parser = argparse.ArgumentParser(description='Generate English lesson scripts for elderly Romanian speakers')
    parser.add_argument('--english', '-e', required=True, help='English phrase to teach')
    parser.add_argument('--romanian', '-r', required=True, help='Romanian translation')
    parser.add_argument('--output', '-o', help='Output script file path (optional)')
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("AUDIO-ENGLEZA: Script Generator")
    print("For elderly Romanian speakers")
    print("="*60)
    
    result = generate_script_file(args.english, args.romanian, args.output)
    
    if result:
        print(f"\n🎯 Next steps:")
        print(f"   1. Edit the script file: {result}")
        print(f"   2. Generate audio: python generate_audio.py --script {result}")
        sys.exit(0)
    else:
        print("\n❌ Script generation failed")
        sys.exit(1)

if __name__ == "__main__":
    main()