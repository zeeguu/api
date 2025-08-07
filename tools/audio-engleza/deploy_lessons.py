#!/usr/bin/env python3
"""
Deploy script for audio-engleza lessons.
Manages lesson deployment and index generation for the website.
"""

import os
import json
import shutil
import argparse
from datetime import datetime

# Configuration
WEBSITE_DIR = "/Users/gh/zeeguu/audio-engleza.github.io"
AUDIO_DIR = os.path.join(WEBSITE_DIR, "audio")
LESSON_INDEX_FILE = os.path.join(WEBSITE_DIR, "lessons.json")
ZEEGUU_AUDIO_DIR = "/Users/mircea/zeeguu-data/audio/lessons"

def load_lesson_index():
    """Load the existing lesson index or create a new one"""
    if os.path.exists(LESSON_INDEX_FILE):
        with open(LESSON_INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return {"lessons": [], "last_updated": None, "total_count": 0}

def save_lesson_index(index):
    """Save the lesson index"""
    index["last_updated"] = datetime.now().isoformat()
    index["total_count"] = len(index["lessons"])
    with open(LESSON_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

def create_semantic_filename(english_phrase, lesson_id):
    """Create a semantic filename from the English phrase"""
    import re
    semantic_name = re.sub(r'[^a-zA-Z0-9\s]', '', english_phrase.lower())
    semantic_name = re.sub(r'\s+', '_', semantic_name.strip())
    
    # Add lesson ID as suffix for uniqueness
    return f"{semantic_name}_{lesson_id}.mp3"

def deploy_lesson_file(lesson_id, english_phrase=None, romanian_translation=None):
    """Deploy a specific lesson file from zeeguu-data to website"""
    source_file = os.path.join(ZEEGUU_AUDIO_DIR, f"{lesson_id}.mp3")
    
    if not os.path.exists(source_file):
        print(f"Error: Source file {source_file} not found")
        return False
    
    if not english_phrase:
        print("Error: English phrase is required for semantic filename")
        return False
    
    # Create audio directory if it doesn't exist
    os.makedirs(AUDIO_DIR, exist_ok=True)
    
    # Copy file with semantic naming to audio folder
    filename = create_semantic_filename(english_phrase, lesson_id)
    dest_file = os.path.join(AUDIO_DIR, filename)
    shutil.copy2(source_file, dest_file)
    
    # Add to index if phrase info provided
    if english_phrase and romanian_translation:
        index = load_lesson_index()
        
        # Check if lesson already exists
        existing_lesson = next((l for l in index["lessons"] if l["id"] == lesson_id), None)
        if existing_lesson:
            print(f"Lesson {lesson_id} already exists in index, updating...")
            existing_lesson.update({
                "english": english_phrase,
                "romanian": romanian_translation,
                "filename": f"audio/{filename}",
                "updated_at": datetime.now().isoformat()
            })
        else:
            new_lesson = {
                "id": lesson_id,
                "english": english_phrase,
                "romanian": romanian_translation,
                "filename": f"audio/{filename}",
                "created_at": datetime.now().isoformat()
            }
            index["lessons"].append(new_lesson)
        
        save_lesson_index(index)
    
    print(f"Successfully deployed: {filename}")
    return True

def list_lessons():
    """List all lessons in the index"""
    index = load_lesson_index()
    if not index["lessons"]:
        print("No lessons found in index")
        return
    
    print(f"\nTotal lessons: {len(index['lessons'])}")
    print("Last updated:", index.get("last_updated", "Never"))
    print("\nLessons:")
    print("-" * 60)
    
    for lesson in sorted(index["lessons"], key=lambda x: x["id"]):
        print(f"ID: {lesson['id']}")
        print(f"English: {lesson['english']}")
        print(f"Romanian: {lesson['romanian']}")
        print(f"File: {lesson['filename']}")
        print(f"Created: {lesson.get('created_at', 'Unknown')}")
        print("-" * 60)

def generate_html_index():
    """Generate a simple HTML index page"""
    index = load_lesson_index()
    
    html_content = f"""<!DOCTYPE html>
<html lang="ro">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lecții de engleză</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            max-width: 800px; 
            margin: 0 auto; 
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .back-button {{
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            display: block;
            width: 90%;
            max-width: 300px;
            padding: 20px;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            text-align: center;
            text-decoration: none;
            font-size: 22px;
            font-weight: bold;
            border-radius: 15px;
            border: none;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(240, 147, 251, 0.3);
        }}
        .back-button:hover {{
            transform: translateX(-50%) translateY(-2px);
            box-shadow: 0 6px 20px rgba(240, 147, 251, 0.4);
            background: linear-gradient(135deg, #e1467c 0%, #f04867 100%);
        }}
        .back-button:focus {{
            outline: 3px solid #FFD700;
            outline-offset: 2px;
        }}
        .header {{ 
            text-align: center; 
            margin-top: 100px;
            margin-bottom: 30px;
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .lesson {{ 
            background-color: white;
            margin: 15px 0; 
            padding: 20px; 
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .lesson-title {{ 
            font-size: 1.4em; 
            font-weight: bold; 
            color: #e74c3c;
            margin-bottom: 15px;
        }}
        .lesson-title .romanian {{
            color: #e74c3c;
            font-weight: bold;
        }}
        .lesson-title .english {{
            color: #2c3e50;
            font-weight: normal;
            margin-left: 8px;
            font-size: 0.85em;
        }}
        .audio-player {{
            margin-top: 20px;
            text-align: center;
        }}
        .play-button {{
            background-color: #27ae60;
            color: white;
            border: none;
            border-radius: 50px;
            padding: 20px 40px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            min-width: 200px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        .play-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.3);
        }}
        .play-button.playing {{
            background-color: #f39c12;
        }}
        .play-button.loading {{
            background-color: #95a5a6;
            cursor: wait;
        }}
        .stats {{
            text-align: center;
            margin: 20px 0;
            color: #7f8c8d;
        }}
        audio {{
            display: none;
        }}
        
        /* Hide header and stats when coming from portal */
        .from-portal .header {{
            display: none;
        }}
        
        .from-portal .stats {{
            display: none;
        }}
    </style>
</head>
<body>
    <!-- Portal back button (shown only if portal parameter exists) -->
    <a href="#" id="portalButton" class="back-button" style="display: block;">← Portal F</a>
    
    <div class="header">
        <h1>🎧 Lecții de engleză</h1>
        <p>Cu explicații în română</p>
    </div>
    
    <div class="stats">
        <p>Total lecții: {len(index['lessons'])} | Ultima actualizare: {index.get('last_updated', 'Necunoscută')}</p>
    </div>
"""

    if index["lessons"]:
        for lesson in sorted(index["lessons"], key=lambda x: x["id"]):
            html_content += f"""
    <div class="lesson">
        <div class="lesson-title">
            <span class="romanian">Lecția {lesson['id']}: {lesson['romanian']}</span>
            <span class="english">({lesson['english']})</span>
        </div>
        <div class="audio-player">
            <button class="play-button" data-audio="{lesson['filename']}" data-lesson-id="{lesson['id']}">
                ▶️ Ascultă Lecția
            </button>
            <audio preload="metadata">
                <source src="{lesson['filename']}" type="audio/mpeg">
                Browserul dumneavoastră nu suportă redarea audio.
            </audio>
        </div>
        <p style="font-size: 0.9em; color: #95a5a6;">
            <span class="duration-display" data-lesson-id="{lesson['id']}">Durată: Se încarcă...</span> | 
            Creat: {lesson.get('created_at', 'Necunoscut')[:10]}
        </p>
    </div>
"""
    else:
        html_content += "<p>Nu există lecții disponibile momentan.</p>"
    
    html_content += """
    <script>
        // Portal functionality
        const urlParams = new URLSearchParams(window.location.search);
        const portalUrl = urlParams.get('portal');
        
        if (portalUrl) {
            const portalButton = document.getElementById('portalButton');
            portalButton.style.display = 'block';
            portalButton.href = portalUrl;
            
            // Hide header and stats when coming from portal
            document.body.classList.add('from-portal');
            
            portalButton.addEventListener('click', function(e) {
                e.preventDefault();
                window.location.href = portalUrl;
            });
        }

        // Custom audio player functionality
        document.addEventListener('DOMContentLoaded', function() {
            let currentAudio = null;
            let currentButton = null;

            // Function to format duration
            function formatDuration(seconds) {
                const minutes = Math.floor(seconds / 60);
                const secs = Math.floor(seconds % 60);
                return `${minutes}:${secs.toString().padStart(2, '0')} min`;
            }

            // Get all play buttons
            const playButtons = document.querySelectorAll('.play-button');
            
            playButtons.forEach(button => {
                const audio = button.parentElement.querySelector('audio');
                const lessonId = button.getAttribute('data-lesson-id');
                const durationDisplay = document.querySelector(`.duration-display[data-lesson-id="${lessonId}"]`);
                
                // Function to update duration display
                function updateDuration() {
                    if (audio.duration && isFinite(audio.duration)) {
                        durationDisplay.textContent = `Durată: ${formatDuration(audio.duration)}`;
                        return true;
                    }
                    return false;
                }
                
                // Try to get duration immediately (if already loaded)
                if (!updateDuration()) {
                    // If not available, listen for when metadata loads
                    audio.addEventListener('loadedmetadata', updateDuration);
                    
                    // Also try after a short delay (for slow connections)
                    setTimeout(() => {
                        if (!updateDuration()) {
                            // Force load metadata if still not available
                            audio.load();
                        }
                    }, 1000);
                }
                
                button.addEventListener('click', function() {
                    // Stop any currently playing audio
                    if (currentAudio && currentAudio !== audio) {
                        currentAudio.pause();
                        currentAudio.currentTime = 0;
                        if (currentButton) {
                            currentButton.textContent = '▶️ Ascultă Lecția';
                            currentButton.className = 'play-button';
                        }
                    }

                    if (audio.paused) {
                        // Show loading state
                        button.textContent = 'Se încarcă...';
                        button.className = 'play-button loading';
                        
                        // Start playing
                        audio.play().then(() => {
                            button.textContent = '⏸️ Pauză';
                            button.className = 'play-button playing';
                            currentAudio = audio;
                            currentButton = button;
                        }).catch(error => {
                            console.error('Error playing audio:', error);
                            button.textContent = '❌ Eroare';
                            button.className = 'play-button';
                        });
                    } else {
                        // Pause
                        audio.pause();
                        button.textContent = '▶️ Continuă';
                        button.className = 'play-button';
                    }
                });

                // Handle audio ending
                audio.addEventListener('ended', function() {
                    button.textContent = '▶️ Ascultă Lecția';
                    button.className = 'play-button';
                    currentAudio = null;
                    currentButton = null;
                });

                // Handle loading errors
                audio.addEventListener('error', function() {
                    button.textContent = '❌ Eroare la încărcare';
                    button.className = 'play-button';
                });
            });
        });
    </script>
</body>
</html>"""
    
    html_file = os.path.join(WEBSITE_DIR, "index.html")
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Generated HTML index: {html_file}")

def main():
    parser = argparse.ArgumentParser(description="Deploy audio-engleza lessons")
    parser.add_argument("--deploy", type=int, help="Deploy lesson by ID")
    parser.add_argument("--english", help="English phrase (required with --deploy)")
    parser.add_argument("--romanian", help="Romanian translation (required with --deploy)")
    parser.add_argument("--list", action="store_true", help="List all lessons")
    parser.add_argument("--generate-html", action="store_true", help="Generate HTML index")
    
    args = parser.parse_args()
    
    if args.deploy:
        if not args.english or not args.romanian:
            print("Error: --english and --romanian are required with --deploy")
            return
        deploy_lesson_file(args.deploy, args.english, args.romanian)
    elif args.list:
        list_lessons()
    elif args.generate_html:
        generate_html_index()
    else:
        print("Use --help for available commands")

if __name__ == "__main__":
    main()