"""
Lesson builder for combining individual audio lessons into daily lessons.
"""

import os
import random
from pydub import AudioSegment

from zeeguu.config import ZEEGUU_DATA_FOLDER
from zeeguu.core.model import DailyAudioLesson
from zeeguu.logging import log

# Transition phrases the teacher says between meaning segments, per language.
TRANSITION_PHRASES = {
    "en": [
        "Now, let's listen to another dialogue.",
        "Let's move on to the next word.",
        "Time for another conversation.",
        "Let's continue with another word.",
        "Here's another dialogue for you.",
        "Let's practice another word now.",
    ],
    "da": [
        "Lad os nu lytte til en anden dialog.",
        "Lad os gå videre til det næste ord.",
        "Tid til en ny samtale.",
        "Lad os fortsætte med et nyt ord.",
        "Her er en ny dialog til dig.",
        "Lad os øve et nyt ord nu.",
    ],
    "de": [
        "Hören wir uns nun einen anderen Dialog an.",
        "Gehen wir zum nächsten Wort über.",
        "Zeit für ein neues Gespräch.",
        "Machen wir mit einem neuen Wort weiter.",
        "Hier ist ein weiterer Dialog für dich.",
        "Üben wir jetzt ein neues Wort.",
    ],
    "es": [
        "Ahora, escuchemos otro diálogo.",
        "Pasemos a la siguiente palabra.",
        "Es hora de otra conversación.",
        "Continuemos con otra palabra.",
        "Aquí tienes otro diálogo.",
        "Practiquemos otra palabra ahora.",
    ],
    "fr": [
        "Maintenant, écoutons un autre dialogue.",
        "Passons au mot suivant.",
        "Place à une autre conversation.",
        "Continuons avec un autre mot.",
        "Voici un autre dialogue pour toi.",
        "Pratiquons un autre mot maintenant.",
    ],
    "it": [
        "Ora, ascoltiamo un altro dialogo.",
        "Passiamo alla prossima parola.",
        "È il momento di un'altra conversazione.",
        "Continuiamo con un'altra parola.",
        "Ecco un altro dialogo per te.",
        "Esercitiamoci con un'altra parola.",
    ],
    "nl": [
        "Laten we nu naar een andere dialoog luisteren.",
        "Laten we verdergaan met het volgende woord.",
        "Tijd voor een nieuw gesprek.",
        "Laten we doorgaan met een ander woord.",
        "Hier is nog een dialoog voor je.",
        "Laten we nu een ander woord oefenen.",
    ],
    "pt": [
        "Agora, vamos ouvir outro diálogo.",
        "Vamos passar para a próxima palavra.",
        "Hora de outra conversa.",
        "Vamos continuar com outra palavra.",
        "Aqui está outro diálogo para ti.",
        "Vamos praticar outra palavra agora.",
    ],
    "sv": [
        "Nu ska vi lyssna på en annan dialog.",
        "Låt oss gå vidare till nästa ord.",
        "Dags för ett nytt samtal.",
        "Låt oss fortsätta med ett nytt ord.",
        "Här är en till dialog åt dig.",
        "Låt oss öva på ett nytt ord nu.",
    ],
    "pl": [
        "Teraz posłuchajmy kolejnego dialogu.",
        "Przejdźmy do następnego słowa.",
        "Czas na kolejną rozmowę.",
        "Kontynuujmy z kolejnym słowem.",
        "Oto kolejny dialog dla ciebie.",
        "Poćwiczmy teraz kolejne słowo.",
    ],
    "ro": [
        "Acum, să ascultăm un alt dialog.",
        "Să trecem la următorul cuvânt.",
        "E timpul pentru o altă conversație.",
        "Să continuăm cu un alt cuvânt.",
        "Iată un alt dialog pentru tine.",
        "Să exersăm acum un alt cuvânt.",
    ],
    "el": [
        "Τώρα, ας ακούσουμε έναν ακόμα διάλογο.",
        "Ας προχωρήσουμε στην επόμενη λέξη.",
        "Ώρα για μια ακόμα συνομιλία.",
        "Ας συνεχίσουμε με μια ακόμα λέξη.",
        "Ορίστε ένας ακόμα διάλογος για σένα.",
        "Ας εξασκήσουμε τώρα μια ακόμα λέξη.",
    ],
    "uk": [
        "А тепер послухаємо ще один діалог.",
        "Перейдемо до наступного слова.",
        "Час для ще однієї розмови.",
        "Продовжимо з іншим словом.",
        "Ось ще один діалог для тебе.",
        "Потренуймо ще одне слово.",
    ],
}


class LessonBuilder:
    """Handles building complete daily lessons from individual segments."""

    def __init__(self):
        self.audio_dir = ZEEGUU_DATA_FOLDER + "/audio"
        self.daily_lessons_dir = os.path.join(self.audio_dir, "daily_lessons")

        # Create directory if it doesn't exist
        os.makedirs(self.daily_lessons_dir, exist_ok=True)

    def _get_transition_audio(self, voice_synthesizer, teacher_language: str) -> AudioSegment:
        """Generate a short teacher transition phrase between segments."""
        phrases = TRANSITION_PHRASES.get(teacher_language, TRANSITION_PHRASES["en"])
        phrase = random.choice(phrases)
        audio_path = voice_synthesizer.synthesize_segment(
            text=phrase,
            voice_type="teacher",
            language_code=teacher_language,
            speaking_rate=1.0,
            teacher_language=teacher_language,
        )
        return AudioSegment.from_mp3(audio_path)

    def build_daily_lesson(self, daily_lesson: DailyAudioLesson, voice_synthesizer=None) -> str:
        """
        Build a complete daily lesson by concatenating all segment audio files.

        Args:
            daily_lesson: The DailyAudioLesson instance with segments

        Returns:
            Path to the generated daily lesson MP3 file
        """
        audio_segments = []
        meaning_segment_count = 0

        # Determine teacher language for transitions
        teacher_language = None
        if daily_lesson.user and daily_lesson.user.native_language:
            teacher_language = daily_lesson.user.native_language.code

        # Process segments in order
        segments_list = list(daily_lesson.segments)

        for idx, segment in enumerate(segments_list):

            audio_path = None

            if (
                segment.segment_type == "meaning_lesson"
                and segment.audio_lesson_meaning
            ):
                # Add transition before 2nd+ meaning segments
                meaning_segment_count += 1
                if meaning_segment_count > 1 and voice_synthesizer and teacher_language:
                    # Add silence then transition phrase
                    audio_segments.append(AudioSegment.silent(duration=2000))
                    transition = self._get_transition_audio(voice_synthesizer, teacher_language)
                    audio_segments.append(transition)
                    audio_segments.append(AudioSegment.silent(duration=1500))

                # Use the individual meaning lesson audio
                relative_path = segment.audio_lesson_meaning.audio_file_path
                # Remove leading /audio/ since we're already in /$ZEEGUU_DATA_FOLDER/audio
                if relative_path.startswith("/audio/"):
                    relative_path = relative_path[7:]  # Remove '/audio/'
                audio_path = os.path.join(self.audio_dir, relative_path)

            elif (
                segment.segment_type in ["intro", "outro"]
                and segment.daily_audio_lesson_wrapper
            ):
                # Use the wrapper audio
                relative_path = segment.daily_audio_lesson_wrapper.audio_file_path
                audio_path = os.path.join(self.audio_dir, relative_path.lstrip("/"))

            else:
                audio_path = None

            if audio_path and os.path.exists(audio_path):
                log(f"Adding segment audio: {audio_path}")
                audio_segment = AudioSegment.from_mp3(audio_path)
                audio_segments.append(audio_segment)
            else:
                log(
                    f"Warning: Audio file not found for segment {segment.id}: {audio_path}"
                )

        # Combine all audio segments
        if audio_segments:
            combined_audio = audio_segments[0]
            for segment in audio_segments[1:]:
                combined_audio += segment
        else:
            # Create a short silence if no audio segments
            log("Warning: No audio segments found, creating empty lesson")
            combined_audio = AudioSegment.silent(duration=1000)  # 1 second silence

        # Save the final daily lesson audio
        output_path = os.path.join(self.daily_lessons_dir, f"{daily_lesson.id}.mp3")
        combined_audio.export(output_path, format="mp3")

        log(f"Generated daily lesson audio: {output_path}")
        return output_path
