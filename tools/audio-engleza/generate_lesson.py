#!/usr/bin/env python3
"""
Audio-Engleza: English lessons generator for elderly Romanian speakers.

This tool generates English audio lessons with Romanian explanations and manages
the lesson index for the audio-engleza.github.io website.

This tool has a staged approach:
1. Generate the lesson script (including translation)
2. Show script to user for confirmation
3. Generate audio only after confirmation
4. Update lesson index and deploy to website
"""

import sys
import os
import json
import shutil
from datetime import datetime
from zeeguu.api.app import create_app
from zeeguu.core.audio_lessons.script_generator import generate_lesson_script
from zeeguu.core.audio_lessons.voice_synthesizer import VoiceSynthesizer

# Configuration
WEBSITE_DIR = "/Users/gh/zeeguu/audio-engleza.github.io"
AUDIO_DIR = os.path.join(WEBSITE_DIR, "audio")
LESSON_INDEX_FILE = os.path.join(WEBSITE_DIR, "lessons.json")

def generate_script(english_phrase, romanian_translation):
    """Generate the lesson script for review"""
    
    script = generate_lesson_script(
        origin_word=english_phrase,
        translation_word=romanian_translation,
        origin_language="en",
        translation_language="ro",
        cefr_level="A1",
        generator_prompt_file="basic_english_for_elderly_romanian.txt",
    )
    
    return script

def generate_audio(script, lesson_id, english_phrase):
    """Generate the audio file from the approved script"""
    
    voice_synthesizer = VoiceSynthesizer()
    
    mp3_path = voice_synthesizer.generate_lesson_audio(
        audio_lesson_meaning_id=lesson_id,
        script=script,
        language_code="en",  # Target language is English
        cefr_level="A1",
        teacher_language="ro",  # Teacher speaks Romanian
    )
    
    return mp3_path

def load_lesson_index():
    """Load the existing lesson index or create a new one"""
    if os.path.exists(LESSON_INDEX_FILE):
        with open(LESSON_INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return {"lessons": [], "last_updated": None}

def save_lesson_index(index):
    """Save the lesson index"""
    index["last_updated"] = datetime.now().isoformat()
    with open(LESSON_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

def get_next_lesson_id():
    """Get the next available lesson ID"""
    index = load_lesson_index()
    if not index["lessons"]:
        return 1
    return max(lesson["id"] for lesson in index["lessons"]) + 1

def add_lesson_to_index(lesson_id, english_phrase, romanian_translation, filename):
    """Add a new lesson to the index"""
    index = load_lesson_index()
    
    new_lesson = {
        "id": lesson_id,
        "english": english_phrase,
        "romanian": romanian_translation,
        "filename": filename,
        "created_at": datetime.now().isoformat()
    }
    
    index["lessons"].append(new_lesson)
    save_lesson_index(index)
    return new_lesson

def create_semantic_filename(english_phrase, lesson_id):
    """Create a semantic filename from the English phrase"""
    # Convert to lowercase and replace spaces and special chars with underscores
    import re
    semantic_name = re.sub(r'[^a-zA-Z0-9\s]', '', english_phrase.lower())
    semantic_name = re.sub(r'\s+', '_', semantic_name.strip())
    
    # Add lesson ID as suffix for uniqueness
    return f"{semantic_name}_{lesson_id}.mp3"

def deploy_lesson(lesson_id, source_mp3_path, english_phrase):
    """Deploy the lesson to the website directory"""
    # Create audio directory if it doesn't exist
    os.makedirs(AUDIO_DIR, exist_ok=True)
    
    # Create semantic filename
    filename = create_semantic_filename(english_phrase, lesson_id)
    dest_path = os.path.join(AUDIO_DIR, filename)
    shutil.copy2(source_mp3_path, dest_path)
    
    return f"audio/{filename}"  # Return relative path for the index

def main():
    print("\n" + "="*60)
    print("AUDIO-ENGLEZA: English Lessons Generator")
    print("For elderly Romanian speakers")
    print("="*60 + "\n")
    
    # Get phrase to teach
    print("Enter the English phrase to teach:")
    print("Examples: 'Hello', 'Thank you', 'How are you?', 'Nice to see you'")
    english_phrase = input("English phrase: ").strip()
    
    if not english_phrase:
        print("Error: Please provide an English phrase")
        sys.exit(1)
    
    print("\nEnter the Romanian translation:")
    print("Examples: 'Bună ziua', 'Mulțumesc', 'Ce mai faci?', 'Mă bucur să te văd'")
    romanian_translation = input("Romanian translation: ").strip()
    
    if not romanian_translation:
        print("Error: Please provide a Romanian translation")
        sys.exit(1)
    
    # Stage 1: Generate script
    print("\n" + "-"*40)
    print("STAGE 1: GENERATING LESSON SCRIPT")
    print("-"*40)
    
    app = create_app()
    with app.app_context():
        try:
            script = generate_script(english_phrase, romanian_translation)
            
            print("\nGenerated Script:")
            print("="*50)
            print(script)
            print("="*50)
            
            # Stage 2: Confirm script
            print("\n" + "-"*40)
            print("STAGE 2: SCRIPT REVIEW")
            print("-"*40)
            print("\nPlease review the script above.")
            print("The script should:")
            print("  - Be very simple and repetitive")
            print("  - Include practical conversation examples")
            print("  - Have lots of pauses for practice")
            print("  - Break down words clearly")
            
            confirm = input("\nDo you want to generate audio for this script? (yes/no): ").strip().lower()
            
            if confirm != 'yes':
                print("\nScript generation cancelled. You can modify the prompt and try again.")
                sys.exit(0)
            
            # Stage 3: Generate audio
            print("\n" + "-"*40)
            print("STAGE 3: GENERATING AUDIO & DEPLOYING")
            print("-"*40)
            
            # Get next lesson ID automatically
            lesson_id = get_next_lesson_id()
            print(f"\nAssigning lesson ID: {lesson_id}")
            
            print(f"Generating audio for lesson {lesson_id}...")
            mp3_path = generate_audio(script, lesson_id, english_phrase)
            
            # Stage 4: Deploy to website
            print(f"\nDeploying lesson to website...")
            filename = deploy_lesson(lesson_id, mp3_path, english_phrase)
            
            # Stage 5: Update index
            print(f"Updating lesson index...")
            lesson_entry = add_lesson_to_index(lesson_id, english_phrase, romanian_translation, filename)
            
            print("\n" + "="*60)
            print("SUCCESS!")
            print("="*60)
            print(f"Audio lesson generated and deployed successfully!")
            print(f"\nLesson details:")
            print(f"  - Lesson ID: {lesson_id}")
            print(f"  - English phrase: {english_phrase}")
            print(f"  - Romanian translation: {romanian_translation}")
            print(f"  - Audio file: {filename}")
            print(f"  - Website location: {WEBSITE_DIR}/{filename}")
            print(f"  - Index updated: {LESSON_INDEX_FILE}")
            print("\nThe lesson is now available on the audio-engleza website!")
            
        except Exception as e:
            print(f"\nError generating lesson: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()