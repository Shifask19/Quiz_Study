"""
Voice service for SnapStudy (optional feature).

Provides:
  - Speech-to-Text (STT): microphone → text
  - Text-to-Speech (TTS): text → audio

This module is intentionally modular and gracefully disabled
if voice libraries are not available.

The core application does NOT depend on this service.
Voice is an enhancement only.

Local voice options:
  STT: openai-whisper (runs locally), vosk, speech_recognition
  TTS: pyttsx3 (system TTS), edge-tts, kokoro

Do NOT set VOICE_ENABLED=true unless you have tested the voice pipeline.
"""
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class VoiceServiceUnavailableError(Exception):
    pass


class VoiceService:
    """
    Voice processing service.
    All methods gracefully return (None, error_message) if unavailable.
    """

    def __init__(self):
        self._stt_available = False
        self._tts_available = False
        self._init_error = None
        self._try_init()

    def _try_init(self):
        from backend.config.settings import settings
        if not settings.VOICE_ENABLED:
            self._init_error = "Voice disabled. Set VOICE_ENABLED=true in .env to enable."
            return

        # Try STT
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._stt_available = True
        except ImportError:
            logger.info("speech_recognition not installed. STT unavailable.")

        # Try TTS
        try:
            import pyttsx3
            self._tts_engine = pyttsx3.init()
            self._tts_available = True
        except ImportError:
            logger.info("pyttsx3 not installed. TTS unavailable.")
        except Exception as e:
            logger.info(f"TTS init failed: {e}")

    def transcribe_audio(self, audio_bytes: bytes, format: str = "wav") -> Tuple[Optional[str], Optional[str]]:
        """
        Convert audio bytes to text.
        Returns (transcript, error_message).
        """
        if not self._stt_available:
            return None, (self._init_error or "STT not available. Install speech_recognition.")

        try:
            import speech_recognition as sr
            import io
            audio_file = io.BytesIO(audio_bytes)
            with sr.AudioFile(audio_file) as source:
                audio = self._recognizer.record(source)
            text = self._recognizer.recognize_google(audio)  # local: use recognize_sphinx
            return text, None
        except Exception as e:
            return None, f"Transcription failed: {e}"

    def synthesize_speech(self, text: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Convert text to speech audio bytes.
        Returns (audio_bytes, error_message).
        """
        if not self._tts_available:
            return None, (self._init_error or "TTS not available. Install pyttsx3.")

        try:
            import pyttsx3
            import io
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name

            self._tts_engine.save_to_file(text, tmp_path)
            self._tts_engine.runAndWait()

            with open(tmp_path, "rb") as f:
                audio_bytes = f.read()

            os.unlink(tmp_path)
            return audio_bytes, None
        except Exception as e:
            return None, f"Speech synthesis failed: {e}"

    def get_status(self) -> dict:
        return {
            "stt_available": self._stt_available,
            "tts_available": self._tts_available,
            "enabled": self._stt_available or self._tts_available,
            "error": self._init_error,
        }


# Module-level singleton
_voice_instance: Optional[VoiceService] = None


def get_voice_service() -> VoiceService:
    global _voice_instance
    if _voice_instance is None:
        _voice_instance = VoiceService()
    return _voice_instance
