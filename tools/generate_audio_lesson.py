from zeeguu.api.app import create_app
from zeeguu.core.audio_lessons.script_generator import generate_lesson_script
from zeeguu.core.audio_lessons.voice_synthesizer import VoiceSynthesizer

# app = create_app()
# app.app_context().push()

target_language = "es"
cefr_level="A1"

script = generate_lesson_script(
    origin_word="mientras",
    translation_word="while",
    origin_language=target_language,
    translation_language="en",
    cefr_level=cefr_level,
    generator_prompt_file="meaning_lesson--teacher_challenges_both_dialogue_and_beyond-v2.txt",
)

print(script)

voice_synthesizer = VoiceSynthesizer()

mp3_path = voice_synthesizer.generate_lesson_audio(
    audio_lesson_meaning_id=51,
    script=script,
    language_code=target_language,
    cefr_level=cefr_level,
)

print(mp3_path)
