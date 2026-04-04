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


# Outro phrases: congratulations + reminder about word list management.
OUTRO_PHRASES = {
    "en": [
        "Great job today! Remember, these words come from your study list. If you already know a word, you can mark it as learned during exercises, or remove it from your word list.",
        "Well done! The words in this lesson are from your saved words. If a word is too easy or you don't want to practice a particular meaning, mark it as learned or remove it from your list.",
        "Congratulations on completing this lesson! These are words from your study list. You can always mark a word as learned or remove it if you don't need to practice it anymore.",
    ],
    "da": [
        "Godt klaret i dag! Husk, at disse ord kommer fra din ordliste. Hvis du allerede kender et ord, kan du markere det som lært under øvelserne, eller fjerne det fra din ordliste.",
        "Flot arbejde! Ordene i denne lektion er fra dine gemte ord. Hvis et ord er for nemt, eller du ikke vil øve en bestemt betydning, kan du markere det som lært eller fjerne det fra din liste.",
        "Tillykke med at have gennemført denne lektion! Disse ord er fra din ordliste. Du kan altid markere et ord som lært eller fjerne det, hvis du ikke behøver at øve det mere.",
    ],
    "de": [
        "Gut gemacht heute! Denk daran, diese Wörter stammen aus deiner Lernliste. Wenn du ein Wort schon kennst, kannst du es bei den Übungen als gelernt markieren oder aus deiner Wortliste entfernen.",
        "Sehr gut! Die Wörter in dieser Lektion stammen aus deinen gespeicherten Wörtern. Wenn ein Wort zu einfach ist oder du eine bestimmte Bedeutung nicht üben möchtest, markiere es als gelernt oder entferne es aus deiner Liste.",
        "Herzlichen Glückwunsch zu dieser Lektion! Diese Wörter stammen aus deiner Lernliste. Du kannst ein Wort jederzeit als gelernt markieren oder entfernen, wenn du es nicht mehr üben musst.",
    ],
    "es": [
        "¡Buen trabajo hoy! Recuerda, estas palabras vienen de tu lista de estudio. Si ya conoces una palabra, puedes marcarla como aprendida durante los ejercicios, o eliminarla de tu lista.",
        "¡Muy bien! Las palabras de esta lección son de tus palabras guardadas. Si una palabra es demasiado fácil o no quieres practicar un significado en particular, márcala como aprendida o elimínala de tu lista.",
        "¡Felicidades por completar esta lección! Estas palabras son de tu lista de estudio. Siempre puedes marcar una palabra como aprendida o eliminarla si ya no necesitas practicarla.",
    ],
    "fr": [
        "Bon travail aujourd'hui ! N'oublie pas, ces mots viennent de ta liste d'étude. Si tu connais déjà un mot, tu peux le marquer comme appris pendant les exercices, ou le retirer de ta liste.",
        "Très bien ! Les mots de cette leçon viennent de tes mots sauvegardés. Si un mot est trop facile ou si tu ne veux pas pratiquer un sens en particulier, marque-le comme appris ou retire-le de ta liste.",
        "Félicitations pour cette leçon ! Ces mots viennent de ta liste d'étude. Tu peux toujours marquer un mot comme appris ou le retirer si tu n'as plus besoin de le pratiquer.",
    ],
    "it": [
        "Ottimo lavoro oggi! Ricorda, queste parole vengono dalla tua lista di studio. Se conosci già una parola, puoi segnarla come imparata durante gli esercizi, o rimuoverla dalla tua lista.",
        "Molto bene! Le parole di questa lezione vengono dalle tue parole salvate. Se una parola è troppo facile o non vuoi esercitarti su un significato specifico, segnala come imparata o rimuovila dalla tua lista.",
        "Complimenti per aver completato questa lezione! Queste parole vengono dalla tua lista di studio. Puoi sempre segnare una parola come imparata o rimuoverla se non hai più bisogno di esercitarla.",
    ],
    "nl": [
        "Goed gedaan vandaag! Onthoud dat deze woorden uit je woordenlijst komen. Als je een woord al kent, kun je het als geleerd markeren tijdens de oefeningen, of het uit je lijst verwijderen.",
        "Heel goed! De woorden in deze les komen uit je opgeslagen woorden. Als een woord te makkelijk is of je een bepaalde betekenis niet wilt oefenen, markeer het dan als geleerd of verwijder het uit je lijst.",
        "Gefeliciteerd met het afronden van deze les! Deze woorden komen uit je woordenlijst. Je kunt een woord altijd als geleerd markeren of verwijderen als je het niet meer hoeft te oefenen.",
    ],
    "pt": [
        "Bom trabalho hoje! Lembra-te, estas palavras vêm da tua lista de estudo. Se já conheces uma palavra, podes marcá-la como aprendida durante os exercícios, ou removê-la da tua lista.",
        "Muito bem! As palavras desta lição vêm das tuas palavras guardadas. Se uma palavra é demasiado fácil ou não queres praticar um significado em particular, marca-a como aprendida ou remove-a da tua lista.",
        "Parabéns por completares esta lição! Estas palavras vêm da tua lista de estudo. Podes sempre marcar uma palavra como aprendida ou removê-la se já não precisas de a praticar.",
    ],
    "sv": [
        "Bra jobbat idag! Kom ihåg att dessa ord kommer från din ordlista. Om du redan kan ett ord kan du markera det som lärt under övningarna, eller ta bort det från din lista.",
        "Mycket bra! Orden i den här lektionen kommer från dina sparade ord. Om ett ord är för lätt eller om du inte vill öva en viss betydelse, markera det som lärt eller ta bort det från din lista.",
        "Grattis till den här lektionen! Dessa ord kommer från din ordlista. Du kan alltid markera ett ord som lärt eller ta bort det om du inte behöver öva det längre.",
    ],
    "pl": [
        "Dobra robota! Pamiętaj, te słowa pochodzą z twojej listy do nauki. Jeśli znasz już jakieś słowo, możesz oznaczyć je jako nauczone podczas ćwiczeń, lub usunąć je ze swojej listy.",
        "Bardzo dobrze! Słowa w tej lekcji pochodzą z twoich zapisanych słów. Jeśli słowo jest zbyt łatwe lub nie chcesz ćwiczyć danego znaczenia, oznacz je jako nauczone lub usuń ze swojej listy.",
        "Gratulacje za ukończenie tej lekcji! Te słowa pochodzą z twojej listy do nauki. Zawsze możesz oznaczyć słowo jako nauczone lub usunąć je, jeśli nie musisz go już ćwiczyć.",
    ],
    "ro": [
        "Bravo azi! Ține minte, aceste cuvinte vin din lista ta de studiu. Dacă știi deja un cuvânt, îl poți marca ca învățat în timpul exercițiilor, sau îl poți elimina din lista ta.",
        "Foarte bine! Cuvintele din această lecție sunt din cuvintele tale salvate. Dacă un cuvânt este prea ușor sau nu vrei să exersezi un anumit sens, marchează-l ca învățat sau elimină-l din lista ta.",
        "Felicitări pentru completarea acestei lecții! Aceste cuvinte sunt din lista ta de studiu. Poți oricând marca un cuvânt ca învățat sau îl poți elimina dacă nu mai ai nevoie să-l exersezi.",
    ],
    "el": [
        "Μπράβο σήμερα! Θυμήσου, αυτές οι λέξεις προέρχονται από τη λίστα μελέτης σου. Αν ήδη ξέρεις μια λέξη, μπορείς να τη σημειώσεις ως μαθημένη κατά τη διάρκεια των ασκήσεων, ή να την αφαιρέσεις από τη λίστα σου.",
        "Πολύ καλά! Οι λέξεις σε αυτό το μάθημα προέρχονται από τις αποθηκευμένες λέξεις σου. Αν μια λέξη είναι πολύ εύκολη ή δεν θέλεις να εξασκήσεις μια συγκεκριμένη σημασία, σημείωσέ την ως μαθημένη ή αφαίρεσέ την από τη λίστα σου.",
        "Συγχαρητήρια για την ολοκλήρωση αυτού του μαθήματος! Αυτές οι λέξεις προέρχονται από τη λίστα μελέτης σου. Μπορείς πάντα να σημειώσεις μια λέξη ως μαθημένη ή να την αφαιρέσεις αν δεν χρειάζεται πλέον να την εξασκείς.",
    ],
    "uk": [
        "Чудова робота сьогодні! Пам'ятай, ці слова з твого списку для вивчення. Якщо ти вже знаєш слово, можеш позначити його як вивчене під час вправ, або видалити зі свого списку.",
        "Дуже добре! Слова в цьому уроці з твоїх збережених слів. Якщо слово занадто легке або ти не хочеш вивчати певне значення, познач його як вивчене або видали зі свого списку.",
        "Вітаю з завершенням цього уроку! Ці слова з твого списку для вивчення. Ти завжди можеш позначити слово як вивчене або видалити його, якщо більше не потрібно його вивчати.",
    ],
}


# Short positive closing after the outro reminder.
CLOSING_PHRASES = {
    "en": ["Keep it up! See you next time.", "Keep practicing, and see you soon!", "You're doing great. See you next time!"],
    "da": ["Bliv ved! Vi ses næste gang.", "Fortsæt med at øve, og vi ses snart!", "Du klarer det godt. Vi ses næste gang!"],
    "de": ["Weiter so! Bis zum nächsten Mal.", "Üb weiter, und bis bald!", "Du machst das toll. Bis zum nächsten Mal!"],
    "es": ["¡Sigue así! Nos vemos la próxima vez.", "¡Sigue practicando y nos vemos pronto!", "¡Lo estás haciendo genial! ¡Hasta la próxima!"],
    "fr": ["Continue comme ça ! À la prochaine.", "Continue à pratiquer, et à bientôt !", "Tu fais du super travail. À la prochaine !"],
    "it": ["Continua così! Ci vediamo la prossima volta.", "Continua a esercitarti, e a presto!", "Stai andando alla grande. Alla prossima!"],
    "nl": ["Ga zo door! Tot de volgende keer.", "Blijf oefenen, en tot snel!", "Je doet het geweldig. Tot de volgende keer!"],
    "pt": ["Continua assim! Até à próxima.", "Continua a praticar, e até breve!", "Estás a ir muito bem. Até à próxima!"],
    "sv": ["Fortsätt så! Vi ses nästa gång.", "Fortsätt öva, så ses vi snart!", "Du gör det jättebra. Vi ses nästa gång!"],
    "pl": ["Tak trzymaj! Do następnego razu.", "Ćwicz dalej, i do zobaczenia wkrótce!", "Świetnie ci idzie. Do następnego razu!"],
    "ro": ["Continuă tot așa! Ne vedem data viitoare.", "Continuă să exersezi, și pe curând!", "Te descurci foarte bine. Pe data viitoare!"],
    "el": ["Συνέχισε έτσι! Τα λέμε την επόμενη φορά.", "Συνέχισε να εξασκείσαι, και τα λέμε σύντομα!", "Τα πας υπέροχα. Τα λέμε την επόμενη φορά!"],
    "uk": ["Так тримати! До наступного разу.", "Продовжуй практикувати, і до зустрічі!", "Ти чудово справляєшся. До наступного разу!"],
}


class LessonBuilder:
    """Handles building complete daily lessons from individual segments."""

    def __init__(self):
        self.audio_dir = ZEEGUU_DATA_FOLDER + "/audio"
        self.daily_lessons_dir = os.path.join(self.audio_dir, "daily_lessons")

        # Create directory if it doesn't exist
        os.makedirs(self.daily_lessons_dir, exist_ok=True)

    def _synthesize_teacher_phrase(self, voice_synthesizer, teacher_language: str, text: str) -> AudioSegment:
        """Synthesize a short teacher phrase."""
        audio_path = voice_synthesizer.synthesize_segment(
            text=text,
            voice_type="teacher",
            language_code=teacher_language,
            speaking_rate=1.0,
            teacher_language=teacher_language,
        )
        return AudioSegment.from_mp3(audio_path)

    def _get_outro_segments(self, voice_synthesizer, teacher_language: str) -> list:
        """Generate outro: word list reminder + positive closing. Returns list of AudioSegments."""
        segments = []

        # Word list reminder
        phrases = OUTRO_PHRASES.get(teacher_language, OUTRO_PHRASES["en"])
        segments.append(self._synthesize_teacher_phrase(voice_synthesizer, teacher_language, random.choice(phrases)))

        # Short pause then positive closing
        segments.append(AudioSegment.silent(duration=1500))
        closings = CLOSING_PHRASES.get(teacher_language, CLOSING_PHRASES["en"])
        segments.append(self._synthesize_teacher_phrase(voice_synthesizer, teacher_language, random.choice(closings)))

        return segments

    def _get_transition_audio(self, voice_synthesizer, teacher_language: str) -> AudioSegment:
        """Generate a short teacher transition phrase between segments."""
        phrases = TRANSITION_PHRASES.get(teacher_language, TRANSITION_PHRASES["en"])
        return self._synthesize_teacher_phrase(voice_synthesizer, teacher_language, random.choice(phrases))

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
                segment.segment_type == "dialogue_lesson"
                and segment.audio_lesson_dialogue
            ):
                # Single dialogue — no transitions needed
                meaning_segment_count += 1
                relative_path = segment.audio_lesson_dialogue.audio_file_path
                if relative_path.startswith("/audio/"):
                    relative_path = relative_path[7:]
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

        # Add outro after all segments
        if voice_synthesizer and teacher_language and meaning_segment_count > 0:
            audio_segments.append(AudioSegment.silent(duration=2000))
            audio_segments.extend(self._get_outro_segments(voice_synthesizer, teacher_language))

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
