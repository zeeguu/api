import os.path
import re

from flask import request

from zeeguu_api.api import api
from zeeguu_api.api.utils.route_wrappers import cross_domain, with_session

from zeeguu_api.app import app

DATA_FOLDER = app.config.get("ZEEGUU_DATA_FOLDER")


@api.route("/text_to_speech", methods=("POST",))
@cross_domain
@with_session
def tts():
    import zeeguu_core
    from zeeguu_core.model import UserWord, Language

    db_session = zeeguu_core.db.session

    text_to_pronounce = request.form.get("text", "")
    language_id = request.form.get("language_id", "")

    if not text_to_pronounce:
        return ""

    user_word = UserWord.find_or_create(
        db_session, text_to_pronounce, Language.find_or_create(language_id)
    )

    audio_file_path = _file_name_for_user_word(user_word, language_id)

    if not os.path.isfile(DATA_FOLDER + audio_file_path):
        _save_speech_to_file(user_word, language_id, audio_file_path)

    return audio_file_path


def _save_speech_to_file(user_word, language_id, audio_file_path):
    from google.cloud import texttospeech

    # Instantiates a client
    client = texttospeech.TextToSpeechClient()

    # Set the text input to be synthesized
    synthesis_input = texttospeech.SynthesisInput(text=user_word.word)

    # Build the voice request
    voice = texttospeech.VoiceSelectionParams(
        language_code=_code_from_id(language_id), name=_voice_for_id(language_id)
    )

    # Select the type of audio file you want returned
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    # Perform the text-to-speech request on the text input with the selected
    # voice parameters and audio file type
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    # The response's audio_content is binary.
    with open(DATA_FOLDER + audio_file_path, "wb") as out:
        # Write the response to the output file.
        out.write(response.audio_content)


def _file_name_for_user_word(user_word, language_id):

    word_without_special_chars = re.sub("[^A-Za-z0-9]+", "_", user_word.word)
    return f"/speech/{language_id}_{user_word.id}_{word_without_special_chars}.mp3"


def _code_from_id(language_id):
    if language_id == "da":
        return "da-DK"
    return "en-US"


def _voice_for_id(language_id):
    if language_id == "da":
        return "da-DK-Wavenet-D"
    return "en-US"
