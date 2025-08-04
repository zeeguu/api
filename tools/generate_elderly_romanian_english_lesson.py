#!/usr/bin/env python3
"""
Tool to generate basic English audio lessons for elderly Romanian speakers.
Specifically designed for a 78-year-old preparing to talk to nephew Armin and son-in-law Aldo.

This tool has a staged approach:
1. Generate the lesson script (including translation)
2. Show script to user for confirmation
3. Generate audio only after confirmation
"""

import sys
import os
from zeeguu.api.app import create_app
from zeeguu.core.audio_lessons.script_generator import generate_lesson_script
from zeeguu.core.audio_lessons.voice_synthesizer import VoiceSynthesizer

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

def main():
    print("\n" + "="*60)
    print("BASIC ENGLISH LESSONS FOR ELDERLY ROMANIAN SPEAKER")
    print("For conversations with Armin (nephew) and Aldo (son-in-law)")
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
            print("  - Include references to Armin or Aldo")
            print("  - Have lots of pauses for practice")
            print("  - Break down words clearly")
            
            confirm = input("\nDo you want to generate audio for this script? (yes/no): ").strip().lower()
            
            if confirm != 'yes':
                print("\nScript generation cancelled. You can modify the prompt and try again.")
                sys.exit(0)
            
            # Stage 3: Generate audio
            print("\n" + "-"*40)
            print("STAGE 3: GENERATING AUDIO")
            print("-"*40)
            
            # Get lesson ID (for file naming)
            lesson_id_str = input("\nEnter a lesson ID number (e.g., 1001): ").strip()
            try:
                lesson_id = int(lesson_id_str)
            except ValueError:
                print("Error: Please provide a valid number for lesson ID")
                sys.exit(1)
            
            print(f"\nGenerating audio for lesson {lesson_id}...")
            mp3_path = generate_audio(script, lesson_id, english_phrase)
            
            print("\n" + "="*60)
            print("SUCCESS!")
            print("="*60)
            print(f"Audio lesson generated successfully!")
            print(f"File saved at: {mp3_path}")
            print(f"\nLesson details:")
            print(f"  - English phrase: {english_phrase}")
            print(f"  - Romanian translation: {romanian_translation}")
            print(f"  - Lesson ID: {lesson_id}")
            print("\nThe elderly learner can now practice with this audio lesson!")
            
        except Exception as e:
            print(f"\nError generating lesson: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()