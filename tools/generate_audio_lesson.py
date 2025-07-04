from zeeguu.api.app import create_app
from zeeguu.core.audio_lessons.script_generator import generate_lesson_script
from zeeguu.core.audio_lessons.voice_synthesizer import VoiceSynthesizer

app = create_app()
app.app_context().push()


script = generate_lesson_script(
    origin_word="før",
    translation_word="before",
    origin_language="da",
    translation_language="en",
    cefr_level="A1",
)

voice_synthesizer = VoiceSynthesizer()

mp3_path = voice_synthesizer.generate_lesson_audio(
    audio_lesson_meaning_id=43,
    script=script,
    language_code="da",
    cefr_level="A1",
)

print(mp3_path)
