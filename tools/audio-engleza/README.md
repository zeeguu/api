# Audio-Engleza: English Lessons for Elderly Romanian Speakers

This toolkit generates English audio lessons with Romanian explanations, specifically designed for elderly learners who want to learn practical conversational English.

## 🎯 Overview

The system uses a two-step workflow:
1. **Generate editable lesson scripts** 
2. **Convert approved scripts to audio lessons**

This approach gives you full control over the lesson content before generating expensive TTS audio.

## 📋 Workflow

### Step 1: Generate Lesson Script
```bash
# Generate a script file you can edit
python generate_script.py --english "to have" --romanian "a avea"
```

This creates:
- `scripts/to_have.txt` - Editable lesson script
- Includes metadata, formatting instructions, and AI-generated content
- You can edit this file as much as you want

### Step 2: Edit Script (Optional)
```bash
# Edit the generated script file  
nano /Users/gh/zeeguu/audio-engleza.github.io/scripts/to_have.txt  # or any editor
```

The script format is:
```
Speaker: Text [pause_seconds seconds]
```

Valid speakers: `Teacher`, `Man`, `Woman`

### Step 3: Generate Audio Lesson
```bash
# Convert script to audio lesson (lesson ID auto-assigned)
python generate_audio.py --script /Users/gh/zeeguu/audio-engleza.github.io/scripts/to_have.txt

# Or specify a lesson ID manually  
python generate_audio.py --script /Users/gh/zeeguu/audio-engleza.github.io/scripts/to_have.txt --lesson-id 1
```

This:
- Auto-assigns the next available lesson ID (or uses specified ID)
- Generates TTS audio from your script
- Deploys to website directory
- Updates lesson index automatically

### Step 4: Update Website
```bash
# Generate HTML index page
python deploy_lessons.py --generate-html
```

### Step 5: Publish to GitHub Pages
```bash
# Go to the website directory
cd /Users/gh/zeeguu/audio-engleza.github.io

# Check what will be published
python publish.py --status

# Commit and push all changes
python publish.py

# Or with custom commit message
python publish.py --message "Add new hello lesson"
```

This:
- Commits all changes (audio files, HTML, JSON index)
- Pushes to GitHub Pages for live deployment
- Auto-generates commit message with timestamp
- Shows status of what's being published

## 📁 Directory Structure

```
audio-engleza/
├── generate_script.py                      # Step 1: Generate editable scripts
├── generate_audio.py                       # Step 3: Convert scripts to audio  
├── deploy_lessons.py                       # Step 4: Generate website HTML
├── basic_english_for_elderly_romanian.txt  # AI prompt template (editable)
└── README.md                              # This file

../audio-engleza.github.io/
├── publish.py                             # Step 5: Commit and push to GitHub
├── scripts/                               # Generated script files (editable)
│   ├── to_have.txt
│   ├── i_am_happy_to_see_you.txt
│   └── ...
├── index.html                             # Generated website
├── lessons.json                           # Lesson index
└── audio/                                # Generated audio files
    ├── to_have_1.mp3
    ├── i_am_happy_to_see_you_2.mp3
    └── ...
```

## 🎨 Lesson Content Features

### Pedagogical Approach
- **Motivational content**: Family-focused phrases elderly people want to say
- **Individual word explanations**: After sentences, explains key words
- **Lots of repetition**: Each phrase repeated 3+ times with pauses
- **Practical conversations**: Real-world dialogue examples

### Example Content
```
Teacher: Prima frază [2 seconds]
Man: I have three children [3 seconds]
Teacher: Care înseamnă am trei copii [2 seconds]
Teacher: Repetați [2 seconds]
Man: I have three children [4 seconds]

Teacher: Primul cuvânt important este [2 seconds]
Man: children [3 seconds]
Teacher: Care înseamnă copii [2 seconds]
Teacher: Repetați [2 seconds]
Man: children [4 seconds]
```

## 🔧 Technical Details

### Voice Mapping
- **Teacher**: Romanian female voice - explains and guides
- **Man**: English male voice - pronunciation examples
- **Woman**: English female voice - conversation partner

### File Generation
- **Semantic filenames**: `to_have_1.mp3` instead of `lesson_1.mp3`
- **Metadata tracking**: JSON index with lesson details
- **Automatic deployment**: Files copied to website directory

### TTS Caching
- Reuses cached audio segments when possible
- Faster generation for repeated phrases
- Consistent voice across lessons

## 📝 Script Editing Tips

1. **Maintain format**: Keep `Speaker: Text [X seconds]` structure
2. **Adjust pauses**: Elderly learners need longer pauses (2-5 seconds)
3. **Add repetition**: Repeat important phrases multiple times
4. **Family focus**: Use examples like "I have grandchildren", "I have family"
5. **Simple vocabulary**: Avoid complex words or idioms

## 🎛️ Customizing Content Generation

### Editing the AI Prompt
You can customize how scripts are generated by editing:
```
basic_english_for_elderly_romanian.txt
```

This file contains:
- **Content instructions**: What types of sentences to generate
- **Pedagogical rules**: How to structure lessons
- **Example phrases**: Family-focused motivational content
- **Format requirements**: Speaker labels and timing

### Key Sections to Customize:
- **Motivational examples**: Add more family/achievement phrases
- **Timing rules**: Adjust pause lengths for different learner needs  
- **Vocabulary focus**: Emphasize specific word types or themes
- **Repetition patterns**: Change how often phrases are repeated

## 🌐 Website Integration

Generated lessons are deployed to `audio-engleza.github.io` with:
- Custom audio player with pause/resume
- Duration calculation and display
- Portal back-button support
- Responsive design for elderly users

## ⚡ Quick Examples

```bash
# Generate common phrases
python generate_script.py --english "Hello" --romanian "Bună ziua"
python generate_script.py --english "Thank you" --romanian "Mulțumesc"
python generate_script.py --english "How are you?" --romanian "Ce mai faci?"

# Edit scripts as needed, then generate audio (IDs auto-assigned)
python generate_audio.py --script /Users/gh/zeeguu/audio-engleza.github.io/scripts/hello.txt
python generate_audio.py --script /Users/gh/zeeguu/audio-engleza.github.io/scripts/thank_you.txt

# Update website and publish  
python deploy_lessons.py --generate-html
cd /Users/gh/zeeguu/audio-engleza.github.io && python publish.py
```

## 🎯 Design Philosophy

**Always overwrite, never duplicate**: When improving a lesson, always replace the old version rather than keeping multiple versions. This ensures learners get the best content.

**Motivational content**: Focus on phrases elderly people are proud to say - family, achievements, positive statements about their lives.

**Edit-friendly workflow**: Separate script generation from audio generation so you can perfect the content before the expensive TTS step.