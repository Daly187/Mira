"""
Audio Processor — processes audio files (voice notes, call recordings, microphone input)
through Whisper transcription, entity extraction, and the memory ingestion pipeline.

Supports:
- General audio file processing (microphone, uploads)
- Phone call recordings with basic speaker diarization
- Quick voice notes from watch/phone (thought capture)
- Batch processing of audio directories
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mira.capture.audio_processor")

AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".webm", ".aac", ".wma"}


class AudioProcessor:
    """Processes audio files through transcription, enrichment, and memory storage."""

    def __init__(self, mira):
        """
        Args:
            mira: The Mira agent instance. Expected attributes:
                - voice (VoiceInterface with Whisper)
                - brain (MiraBrain for Claude API calls)
                - ingest_pipeline (IngestionPipeline)
                - sqlite (SQLiteStore for logging)
        """
        self.mira = mira
        self.voice = getattr(mira, "voice", None)
        self.brain = getattr(mira, "brain", None)
        self.pipeline = getattr(mira, "ingest_pipeline", None)
        self.sqlite = getattr(mira, "sqlite", None)

    # ── Public API ────────────────────────────────────────────────────

    async def process_audio_file(
        self, file_path: str, source: str = "microphone"
    ) -> dict:
        """Process a general audio file: transcribe, extract entities, store in memory.

        Args:
            file_path: Path to the audio file.
            source: Source label for the memory (e.g. "microphone", "telegram", "upload").

        Returns:
            dict with status, transcription, entities, and ingestion result.
        """
        path = Path(file_path)
        if not path.exists():
            return self._error(f"File not found: {file_path}")

        if path.suffix.lower() not in AUDIO_EXTENSIONS:
            return self._error(
                f"Unsupported format {path.suffix}. Supported: {sorted(AUDIO_EXTENSIONS)}"
            )

        logger.info(f"Processing audio file: {file_path} (source={source})")

        # Step 1: Transcribe via Whisper
        transcription = await self._transcribe(file_path)
        if transcription is None:
            return self._error("Transcription failed or returned empty")

        # Step 2: Feed through the ingestion pipeline (extracts entities, stores in all 3 layers)
        ingestion_result = await self._ingest(
            text=transcription,
            source=source,
            metadata={
                "audio_path": str(file_path),
                "input_type": "audio_transcription",
                "file_size_bytes": path.stat().st_size,
                "file_format": path.suffix.lower(),
            },
        )

        self._log_action("process_audio", "completed", {
            "source": source,
            "file": str(file_path),
            "transcription_length": len(transcription),
        })

        return {
            "status": "success",
            "transcription": transcription,
            "entities": ingestion_result.get("entities", {}),
            "ingestion": ingestion_result,
            "audio_path": str(file_path),
        }

    async def process_call_recording(
        self, file_path: str, caller_info: Optional[dict] = None
    ) -> dict:
        """Process a phone call recording with basic speaker segmentation.

        Splits audio by silence gaps to approximate speaker turns, transcribes
        each segment, then uses Claude to extract key decisions, action items,
        and a call summary.

        Args:
            file_path: Path to the call recording.
            caller_info: Optional dict with keys like 'name', 'phone', 'relationship'.

        Returns:
            dict with transcription, speaker segments, decisions, action items, summary.
        """
        path = Path(file_path)
        if not path.exists():
            return self._error(f"File not found: {file_path}")

        logger.info(f"Processing call recording: {file_path}")

        # Step 1: Try speaker-segmented transcription, fall back to full transcription
        segments = await self._segment_and_transcribe(file_path)
        if segments is None:
            # Fallback: transcribe the entire file as one block
            full_text = await self._transcribe(file_path)
            if full_text is None:
                return self._error("Call transcription failed")
            segments = [{"speaker": "Unknown", "text": full_text}]

        # Build combined transcript text
        transcript_lines = []
        for seg in segments:
            speaker = seg.get("speaker", "Unknown")
            text = seg.get("text", "")
            transcript_lines.append(f"[{speaker}]: {text}")
        full_transcript = "\n".join(transcript_lines)

        # Step 2: Use Claude to extract call insights
        caller_label = "Unknown caller"
        if caller_info:
            caller_label = caller_info.get("name", caller_info.get("phone", "Unknown"))

        analysis = await self._analyse_call(full_transcript, caller_label)

        # Step 3: Ingest the full transcript into memory
        ingest_metadata = {
            "audio_path": str(file_path),
            "input_type": "call_recording",
            "caller_info": caller_info or {},
            "num_segments": len(segments),
        }

        ingestion_result = await self._ingest(
            text=f"Call with {caller_label}:\n{full_transcript}",
            source="phone_call",
            metadata=ingest_metadata,
        )

        # Step 4: Store action items as tasks
        if self.sqlite and analysis.get("action_items"):
            for item in analysis["action_items"]:
                self.sqlite.add_task(
                    title=item,
                    description=f"From call with {caller_label}: {file_path}",
                    priority=analysis.get("importance", 3),
                )

        # Step 5: Store decisions
        if self.sqlite and analysis.get("decisions"):
            for decision in analysis["decisions"]:
                self.sqlite.log_decision(
                    decision=decision,
                    context=f"Call with {caller_label}",
                    domain="phone_call",
                )

        self._log_action("process_call", "completed", {
            "caller": caller_label,
            "segments": len(segments),
            "action_items": len(analysis.get("action_items", [])),
        })

        return {
            "status": "success",
            "transcription": full_transcript,
            "segments": segments,
            "summary": analysis.get("summary", ""),
            "decisions": analysis.get("decisions", []),
            "action_items": analysis.get("action_items", []),
            "sentiment": analysis.get("sentiment", "neutral"),
            "importance": analysis.get("importance", 3),
            "ingestion": ingestion_result,
            "caller_info": caller_info,
            "audio_path": str(file_path),
        }

    async def process_voice_note(
        self, file_path: str, source: str = "watch"
    ) -> dict:
        """Process a quick voice note (thought capture / brain dump).

        Optimised for short, informal voice memos. Uses fast-tier extraction
        and tags as thought/note for later retrieval.

        Args:
            file_path: Path to the voice note audio.
            source: Origin device/app (e.g. "watch", "phone", "telegram").

        Returns:
            dict with transcription and ingestion result.
        """
        path = Path(file_path)
        if not path.exists():
            return self._error(f"File not found: {file_path}")

        logger.info(f"Processing voice note: {file_path} (source={source})")

        # Transcribe
        transcription = await self._transcribe(file_path)
        if transcription is None:
            return self._error("Voice note transcription failed")

        # For voice notes, prepend a tag so the ingestion pipeline knows this is
        # a quick thought capture (helps with importance/category classification)
        tagged_text = f"[Voice Note — {source}]: {transcription}"

        ingestion_result = await self._ingest(
            text=tagged_text,
            source=f"voice_note_{source}",
            metadata={
                "audio_path": str(file_path),
                "input_type": "voice_note",
                "capture_device": source,
                "timestamp": datetime.now().isoformat(),
            },
        )

        self._log_action("process_voice_note", "completed", {
            "source": source,
            "length": len(transcription),
        })

        return {
            "status": "success",
            "transcription": transcription,
            "ingestion": ingestion_result,
            "source": source,
            "audio_path": str(file_path),
        }

    async def batch_process(self, directory_path: str) -> dict:
        """Process all audio files in a directory.

        Scans for supported audio formats, processes each sequentially,
        and returns a summary of results.

        Args:
            directory_path: Path to the directory containing audio files.

        Returns:
            dict with counts of processed, failed, and skipped files plus per-file results.
        """
        dir_path = Path(directory_path)
        if not dir_path.is_dir():
            return self._error(f"Directory not found: {directory_path}")

        audio_files = sorted(
            f for f in dir_path.iterdir()
            if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
        )

        if not audio_files:
            return {
                "status": "empty",
                "message": f"No audio files found in {directory_path}",
                "supported_formats": sorted(AUDIO_EXTENSIONS),
            }

        logger.info(f"Batch processing {len(audio_files)} audio files from {directory_path}")

        results = []
        processed = 0
        failed = 0

        for audio_file in audio_files:
            try:
                result = await self.process_audio_file(
                    str(audio_file), source="batch_import"
                )
                results.append({
                    "file": audio_file.name,
                    "status": result.get("status", "unknown"),
                    "memory_id": result.get("ingestion", {}).get("memory_id"),
                })
                if result.get("status") == "success":
                    processed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Batch item failed ({audio_file.name}): {e}")
                results.append({
                    "file": audio_file.name,
                    "status": "error",
                    "message": str(e),
                })
                failed += 1

        self._log_action("batch_process", "completed", {
            "directory": str(directory_path),
            "total": len(audio_files),
            "processed": processed,
            "failed": failed,
        })

        return {
            "status": "success",
            "directory": str(directory_path),
            "total_files": len(audio_files),
            "processed": processed,
            "failed": failed,
            "results": results,
        }

    # ── Internal Helpers ──────────────────────────────────────────────

    async def _transcribe(self, file_path: str) -> Optional[str]:
        """Transcribe an audio file via VoiceInterface (Whisper).

        Returns the transcription text, or None on failure.
        """
        if not self.voice:
            logger.error("VoiceInterface not available on Mira instance")
            return None

        # Ensure Whisper is loaded
        if not self.voice.whisper_model:
            self.voice.initialise_stt()
            if not self.voice.whisper_model:
                logger.error("Whisper model could not be loaded")
                return None

        text = await self.voice.transcribe(file_path)
        if not text or text.startswith("STT not") or text.startswith("Transcription error"):
            logger.error(f"Transcription returned error: {text}")
            return None

        return text.strip()

    async def _segment_and_transcribe(self, file_path: str) -> Optional[list]:
        """Basic speaker diarization by splitting audio on silence gaps.

        Uses pydub to detect silence and split the audio. Each chunk is saved
        as a temp file, transcribed, and labelled as alternating speakers
        (Speaker A / Speaker B).

        Returns a list of dicts: [{"speaker": str, "text": str}, ...] or None on failure.
        """
        try:
            from pydub import AudioSegment
            from pydub.silence import split_on_silence
        except ImportError:
            logger.warning("pydub not installed — falling back to full-file transcription")
            return None

        try:
            audio = AudioSegment.from_file(file_path)
        except Exception as e:
            logger.error(f"Failed to load audio for segmentation: {e}")
            return None

        # Split on silence: min_silence_len=700ms, silence_thresh relative to dBFS
        chunks = split_on_silence(
            audio,
            min_silence_len=700,
            silence_thresh=audio.dBFS - 16,
            keep_silence=200,  # keep 200ms padding
        )

        if not chunks:
            logger.warning("No segments found after silence split")
            return None

        # Transcribe each chunk and alternate speaker labels
        segments = []
        temp_dir = Path(file_path).parent / "_temp_segments"
        temp_dir.mkdir(exist_ok=True)

        speakers = ["Speaker A", "Speaker B"]
        try:
            for i, chunk in enumerate(chunks):
                # Skip very short chunks (< 0.5s) — likely noise
                if len(chunk) < 500:
                    continue

                temp_path = temp_dir / f"segment_{i:04d}.wav"
                chunk.export(str(temp_path), format="wav")

                text = await self._transcribe(str(temp_path))
                if text:
                    segments.append({
                        "speaker": speakers[i % 2],
                        "text": text,
                        "duration_ms": len(chunk),
                    })

                # Clean up temp file
                try:
                    temp_path.unlink()
                except OSError:
                    pass
        finally:
            # Clean up temp directory
            try:
                temp_dir.rmdir()
            except OSError:
                pass

        return segments if segments else None

    async def _analyse_call(self, transcript: str, caller_label: str) -> dict:
        """Use Claude to extract structured insights from a call transcript."""
        if not self.brain:
            logger.warning("Brain not available — skipping call analysis")
            return {}

        import json

        prompt = f"""Analyse this phone call transcript. Return ONLY valid JSON with these fields:
- summary: 2-3 sentence summary of the call
- decisions: list of decisions made during the call
- action_items: list of action items or commitments (who needs to do what)
- sentiment: overall sentiment of the call (positive, neutral, negative, mixed)
- importance: 1-5 rating of how important this call was
- topics: list of key topics discussed

Caller: {caller_label}

Transcript:
{transcript[:4000]}"""

        response = await self.brain.think(
            message=prompt,
            include_history=False,
            system_override="You are a precise call analysis system. Return ONLY valid JSON.",
            max_tokens=1024,
            tier="fast",
            task_type="call_analysis",
        )

        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]
            return json.loads(cleaned)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse call analysis: {e}")
            return {
                "summary": "",
                "decisions": [],
                "action_items": [],
                "sentiment": "neutral",
                "importance": 3,
                "topics": [],
            }

    async def _ingest(self, text: str, source: str, metadata: dict) -> dict:
        """Feed text through the ingestion pipeline. Returns ingestion result or empty dict."""
        if not self.pipeline:
            logger.warning("Ingestion pipeline not available — text will not be stored")
            return {}

        try:
            return await self.pipeline.ingest_text(
                text=text,
                source=source,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Ingestion pipeline error: {e}")
            return {"status": "error", "message": str(e)}

    def _log_action(self, action: str, outcome: str, details: dict):
        """Log to the action_log table if SQLite is available."""
        if self.sqlite:
            try:
                self.sqlite.log_action(
                    module="audio_processor",
                    action=action,
                    outcome=outcome,
                    details=details,
                )
            except Exception as e:
                logger.error(f"Failed to log action: {e}")

    @staticmethod
    def _error(message: str) -> dict:
        """Return a standard error dict."""
        logger.error(message)
        return {"status": "error", "message": message}
