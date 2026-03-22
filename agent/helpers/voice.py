"""
Voice Interface — Whisper STT (speech-to-text) + ElevenLabs TTS (text-to-speech).
Talk to Mira, she talks back in a consistent voice.

Phase 11 feature — skeleton built now.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mira.helpers.voice")


class VoiceInterface:
    """Handles speech-to-text and text-to-speech for Mira."""

    def __init__(self):
        self.whisper_model = None
        self.elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "")
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self._ingest_pipeline = None

    def set_mira(self, mira):
        """Store a reference to the Mira instance so we can access the ingestion pipeline.

        Args:
            mira: The Mira agent instance, expected to have an `ingest_pipeline` attribute.
        """
        if hasattr(mira, "ingest_pipeline"):
            self._ingest_pipeline = mira.ingest_pipeline
            logger.info("VoiceInterface linked to Mira's ingestion pipeline")
        else:
            logger.warning("Mira instance has no ingest_pipeline attribute")

    def initialise_stt(self, model_size: str = "base"):
        """Load Whisper model for speech-to-text."""
        try:
            import whisper
            self.whisper_model = whisper.load_model(model_size)
            logger.info(f"Whisper {model_size} model loaded for STT")
        except ImportError:
            logger.warning("Whisper not installed. STT disabled.")
        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")

    async def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file to text using Whisper."""
        if not self.whisper_model:
            return "STT not initialised"

        try:
            result = self.whisper_model.transcribe(audio_path)
            text = result["text"].strip()
            logger.info(f"Transcribed: {text[:100]}...")
            return text
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return f"Transcription error: {e}"

    async def speak(self, text: str, output_path: str = None) -> Optional[str]:
        """Convert text to speech using ElevenLabs. Returns path to audio file."""
        if not self.elevenlabs_api_key:
            logger.warning("ElevenLabs API key not set. TTS disabled.")
            return None

        try:
            import httpx

            response = httpx.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{self.elevenlabs_voice_id}",
                headers={
                    "xi-api-key": self.elevenlabs_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                },
            )

            if response.status_code == 200:
                out = output_path or "mira_speech.mp3"
                with open(out, "wb") as f:
                    f.write(response.content)
                logger.info(f"TTS generated: {out}")
                return out
            else:
                logger.error(f"ElevenLabs error: {response.status_code}")
                return None

        except ImportError:
            logger.warning("httpx not installed. Install with: pip install httpx")
            return None
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            return None

    async def transcribe_and_ingest(self, audio_path: str, source: str = "voice") -> dict:
        """Transcribe audio via Whisper and pass through the ingestion pipeline.

        Requires set_mira() to have been called first, or falls back to
        returning the transcription without ingesting.

        Args:
            audio_path: Path to audio file (mp3, wav, ogg, etc.)
            source: Source tag for the ingestion pipeline (default "voice")

        Returns:
            dict with transcription text and ingestion result, or error info.
        """
        # Step 1: Transcribe
        transcription = await self.transcribe(audio_path)
        if not transcription or transcription.startswith("STT not initialised") or transcription.startswith("Transcription error"):
            logger.error(f"Transcription failed for {audio_path}: {transcription}")
            return {"status": "error", "message": transcription, "audio_path": audio_path}

        logger.info(f"Transcribed audio ({audio_path}): {transcription[:100]}...")

        # Step 2: Pass through ingestion pipeline with voice source tag
        if not self._ingest_pipeline:
            logger.warning("No ingestion pipeline available — returning transcription only")
            return {
                "status": "partial",
                "transcription": transcription,
                "message": "No ingestion pipeline linked. Call set_mira() first.",
                "audio_path": audio_path,
            }

        try:
            ingestion_result = await self._ingest_pipeline.ingest_text(
                text=transcription,
                source=source,
                metadata={
                    "audio_path": audio_path,
                    "input_type": "voice_transcription",
                },
            )

            logger.info(f"Voice ingestion complete: memory #{ingestion_result.get('memory_id')}")
            return {
                "status": "success",
                "transcription": transcription,
                "ingestion": ingestion_result,
                "audio_path": audio_path,
            }
        except Exception as e:
            logger.error(f"Voice ingestion pipeline failed: {e}")
            return {
                "status": "error",
                "message": f"Ingestion failed: {e}",
                "transcription": transcription,
                "audio_path": audio_path,
            }
