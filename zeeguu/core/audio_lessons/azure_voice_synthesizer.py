"""
Azure Text-to-Speech synthesizer for languages not well-supported by Google.
Currently used for Greek (el-GR) which only has female voices on Google.

Requires environment variables:
- AZURE_SPEECH_KEY: Azure Speech Services subscription key
- AZURE_SPEECH_REGION: Azure region (e.g., 'westeurope', 'eastus')
"""

import os
import azure.cognitiveservices.speech as speechsdk
from io import BytesIO
from pydub import AudioSegment


class AzureVoiceSynthesizer:
    """Handles text-to-speech synthesis using Azure Speech Services."""

    def __init__(self):
        """Initialize Azure Speech SDK with credentials from environment."""
        speech_key = os.environ.get("AZURE_SPEECH_KEY")
        service_region = os.environ.get("AZURE_SPEECH_REGION", "westeurope")

        if not speech_key:
            raise ValueError(
                "AZURE_SPEECH_KEY environment variable not set. "
                "Please set it to your Azure Speech Services subscription key."
            )

        self.speech_config = speechsdk.SpeechConfig(
            subscription=speech_key, region=service_region
        )

        # Set output format to MP3 (matches Google TTS output)
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        )

    def text_to_speech(
        self,
        text: str,
        voice_id: str,
        speaking_rate: float = 1.0,
        language_code: str = "el-GR",
    ) -> bytes:
        """
        Convert text to speech using Azure Neural voices.

        Args:
            text: The text to synthesize
            voice_id: Azure voice name (e.g., 'el-GR-NestorasNeural')
            speaking_rate: Speech rate (0.5 to 2.0, default 1.0)
            language_code: Language code (e.g., 'el-GR')

        Returns:
            MP3 audio bytes

        Raises:
            Exception: If synthesis fails
        """
        # Escape XML special characters in text
        text = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

        # Create SSML with speaking rate control
        ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{language_code}">
    <voice name="{voice_id}">
        <prosody rate="{speaking_rate:.2f}">
            {text}
        </prosody>
    </voice>
</speak>"""

        # Create synthesizer with no audio output config (will use result.audio_data)
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config, audio_config=None
        )

        # Synthesize speech
        result = synthesizer.speak_ssml_async(ssml).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            # Get audio data from the result
            return result.audio_data
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            error_msg = f"Azure TTS synthesis canceled: {cancellation.reason}"
            if cancellation.error_details:
                error_msg += f" - {cancellation.error_details}"
            raise Exception(error_msg)
        else:
            raise Exception(f"Azure TTS synthesis failed with reason: {result.reason}")

    def get_audio_duration(self, audio_bytes: bytes) -> float:
        """
        Calculate duration of audio in seconds.
        Uses pydub like the Google version for consistency.

        Args:
            audio_bytes: MP3 audio data

        Returns:
            Duration in seconds
        """
        audio = AudioSegment.from_mp3(BytesIO(audio_bytes))
        return len(audio) / 1000.0  # Convert milliseconds to seconds
