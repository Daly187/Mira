"""
Memory ingestion pipeline — the four-stage process that turns raw input into structured memory.

1. Ingest — raw capture arrives (audio, text, image, structured data)
2. Transcribe/Parse — convert to text (Whisper for audio, OCR for images)
3. Enrich — Claude extracts entities, tags importance, identifies action items
4. Store — writes to all three memory layers simultaneously
"""

import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mira.capture.ingest")

# Supported image formats and their MIME types
IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".heic": "image/heic",
}


class IngestionPipeline:
    """Processes raw input through all four stages into Mira's memory."""

    def __init__(self, brain, sqlite_store, vector_store, knowledge_graph):
        self.brain = brain
        self.sqlite = sqlite_store
        self.vector = vector_store
        self.graph = knowledge_graph

    async def ingest_text(
        self,
        text: str,
        source: str = "telegram",
        metadata: dict = None,
    ) -> dict:
        """Process a text input through the full pipeline."""
        logger.info(f"Ingesting text from {source}: {text[:80]}...")

        # Stage 1: Already text, no transcription needed

        # Stage 2: Not needed for text

        # Stage 3: Enrich — extract entities and meaning
        entities = await self.brain.extract_entities(text)

        # Stage 4: Store in all three layers
        # 4a: Structured memory (SQLite)
        memory_id = self.sqlite.store_memory(
            content=text,
            category=entities.get("category", "general"),
            importance=entities.get("importance", 3),
            source=source,
            tags=entities.get("topics", []),
            metadata={
                "entities": entities,
                **(metadata or {}),
            },
        )

        # 4b: Semantic memory (ChromaDB)
        self.vector.add(
            text=text,
            memory_id=f"mem_{memory_id}",
            category=entities.get("category", "general"),
            source=source,
            importance=entities.get("importance", 3),
        )

        # 4c: Knowledge graph — add nodes and edges for extracted entities
        self._update_graph(text, entities, memory_id)

        # Handle action items — create tasks
        for action in entities.get("action_items", []):
            self.sqlite.add_task(
                title=action,
                description=f"From {source}: {text[:100]}",
                priority=entities.get("importance", 3),
            )

        # Handle people — update CRM
        for person_name in entities.get("people", []):
            self.sqlite.upsert_person(name=person_name)

        # Handle decisions
        for decision in entities.get("decisions", []):
            self.sqlite.log_decision(
                decision=decision,
                context=text[:500],
                domain=entities.get("category", "general"),
            )

        # Log the action
        self.sqlite.log_action(
            module="memory",
            action="ingest",
            outcome="stored",
            details={
                "source": source,
                "memory_id": memory_id,
                "entities_found": {
                    k: len(v) if isinstance(v, list) else v
                    for k, v in entities.items()
                },
            },
        )

        result = {
            "memory_id": memory_id,
            "category": entities.get("category", "general"),
            "importance": entities.get("importance", 3),
            "entities": entities,
            "action_items_created": len(entities.get("action_items", [])),
            "people_found": entities.get("people", []),
        }

        logger.info(f"Ingestion complete: memory #{memory_id}, "
                     f"importance={entities.get('importance', 3)}, "
                     f"category={entities.get('category', 'general')}")

        return result

    async def ingest_audio(self, audio_path: str, source: str = "voice") -> dict:
        """Process audio through Whisper transcription then the text pipeline.

        Requires a VoiceInterface with Whisper initialised. If unavailable,
        returns an error.

        Args:
            audio_path: Path to audio file (mp3, wav, ogg, etc.)
            source: Source tag for the memory (default "voice")

        Returns:
            dict with transcription and ingestion result
        """
        try:
            from helpers.voice import VoiceInterface

            voice = VoiceInterface()
            voice.initialise_stt()
            if not voice.whisper_model:
                return {"status": "error", "message": "Whisper STT not available"}

            transcription = await voice.transcribe(audio_path)
            if not transcription or transcription.startswith("STT not") or transcription.startswith("Transcription error"):
                return {"status": "error", "message": transcription, "audio_path": audio_path}

            ingestion_result = await self.ingest_text(
                text=transcription,
                source=source,
                metadata={
                    "audio_path": audio_path,
                    "input_type": "audio_transcription",
                },
            )

            return {
                "status": "success",
                "transcription": transcription,
                "ingestion": ingestion_result,
                "audio_path": audio_path,
            }
        except Exception as e:
            logger.error(f"Audio ingestion failed: {e}")
            return {"status": "error", "message": str(e), "audio_path": audio_path}

    async def ingest_image(self, image_path: str, source: str = "photo") -> dict:
        """Process image through Claude Vision OCR then the text pipeline.

        Reads the image file, sends it to Claude vision API to extract
        text (OCR) and describe the visual content, then passes the
        extracted text through the normal ingestion pipeline.

        Args:
            image_path: Path to image file (PNG, JPG, JPEG, HEIC, WebP, GIF)
            source: Source tag for the memory (default "photo")

        Returns:
            dict with extracted_text, description, and ingestion result
        """
        path = Path(image_path)
        if not path.exists():
            logger.error(f"Image file not found: {image_path}")
            return {"status": "error", "message": f"File not found: {image_path}"}

        suffix = path.suffix.lower()
        media_type = IMAGE_MIME_TYPES.get(suffix)
        if not media_type:
            logger.error(f"Unsupported image format: {suffix}")
            return {
                "status": "error",
                "message": f"Unsupported format {suffix}. Supported: {list(IMAGE_MIME_TYPES.keys())}",
            }

        # Read and base64-encode the image
        try:
            image_bytes = path.read_bytes()
            image_b64 = base64.b64encode(image_bytes).decode("ascii")
        except Exception as e:
            logger.error(f"Failed to read image {image_path}: {e}")
            return {"status": "error", "message": f"Failed to read image: {e}"}

        # Send to Claude Vision for OCR + description
        vision_prompt = (
            "Analyse this image. Provide:\n"
            "1. **OCR Text**: Extract ALL visible text exactly as written (preserve formatting).\n"
            "2. **Description**: Describe what the image shows (objects, people, context).\n"
            "3. **Summary**: A one-sentence summary suitable for a memory note.\n\n"
            "Format your response as:\n"
            "OCR_TEXT:\n<extracted text here, or NONE if no text visible>\n\n"
            "DESCRIPTION:\n<visual description>\n\n"
            "SUMMARY:\n<one-sentence summary>"
        )

        try:
            # Use the Anthropic client directly for vision (multimodal message)
            from config import Config

            model = Config.get_model_for_tier("standard")
            response = self.brain.client.messages.create(
                model=model,
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": vision_prompt,
                            },
                        ],
                    }
                ],
            )

            vision_text = response.content[0].text

            # Log the API usage
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = Config.estimate_cost(model, input_tokens, output_tokens)
            logger.info(f"[standard] image_ocr: {model} | {input_tokens}in/{output_tokens}out | ${cost:.4f}")
            if self.sqlite:
                self.sqlite.log_api_usage(
                    model=model,
                    tier="standard",
                    task_type="image_ocr",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=cost,
                )

        except Exception as e:
            logger.error(f"Claude Vision API call failed: {e}")
            return {"status": "error", "message": f"Vision API error: {e}"}

        # Parse the structured response
        extracted_text = ""
        description = ""
        summary = ""

        if "OCR_TEXT:" in vision_text:
            parts = vision_text.split("OCR_TEXT:", 1)[1]
            if "DESCRIPTION:" in parts:
                extracted_text = parts.split("DESCRIPTION:", 1)[0].strip()
                remaining = parts.split("DESCRIPTION:", 1)[1]
                if "SUMMARY:" in remaining:
                    description = remaining.split("SUMMARY:", 1)[0].strip()
                    summary = remaining.split("SUMMARY:", 1)[1].strip()
                else:
                    description = remaining.strip()
            else:
                extracted_text = parts.strip()
        else:
            # Fallback: treat the whole response as the extracted content
            extracted_text = vision_text

        # Build the text to ingest (combine OCR + description for full context)
        ingest_content = ""
        if extracted_text and extracted_text.upper() != "NONE":
            ingest_content += f"[Image OCR Text]: {extracted_text}\n"
        if description:
            ingest_content += f"[Image Description]: {description}\n"
        if summary:
            ingest_content += f"[Summary]: {summary}"

        if not ingest_content.strip():
            ingest_content = f"[Image]: {vision_text}"

        # Pass through the normal text ingestion pipeline
        try:
            ingestion_result = await self.ingest_text(
                text=ingest_content.strip(),
                source=source,
                metadata={
                    "image_path": str(image_path),
                    "input_type": "image_ocr",
                    "media_type": media_type,
                    "extracted_text": extracted_text if extracted_text.upper() != "NONE" else "",
                    "description": description,
                    "summary": summary,
                },
            )

            logger.info(f"Image ingestion complete: memory #{ingestion_result.get('memory_id')}")
            return {
                "status": "success",
                "extracted_text": extracted_text if extracted_text.upper() != "NONE" else "",
                "description": description,
                "summary": summary,
                "ingestion": ingestion_result,
                "image_path": str(image_path),
            }
        except Exception as e:
            logger.error(f"Image ingestion pipeline failed: {e}")
            return {
                "status": "error",
                "message": f"Ingestion pipeline failed: {e}",
                "extracted_text": extracted_text,
                "image_path": str(image_path),
            }

    def _update_graph(self, text: str, entities: dict, memory_id: int):
        """Update the knowledge graph with extracted entities."""
        # Add memory node
        mem_node_id = f"memory_{memory_id}"
        self.graph.add_node(
            mem_node_id,
            node_type="memory",
            label=text[:100],
            properties={
                "category": entities.get("category", "general"),
                "importance": entities.get("importance", 3),
                "full_text": text[:500],
            },
        )

        # Add person nodes and link to memory
        for person in entities.get("people", []):
            person_id = f"person_{person.lower().replace(' ', '_')}"
            self.graph.add_node(person_id, node_type="person", label=person)
            self.graph.add_edge(mem_node_id, person_id, relationship="mentions")

        # Add topic nodes and link
        for topic in entities.get("topics", []):
            topic_id = f"topic_{topic.lower().replace(' ', '_')}"
            self.graph.add_node(topic_id, node_type="topic", label=topic)
            self.graph.add_edge(mem_node_id, topic_id, relationship="about")

        # Add place nodes and link
        for place in entities.get("places", []):
            place_id = f"place_{place.lower().replace(' ', '_')}"
            self.graph.add_node(place_id, node_type="place", label=place)
            self.graph.add_edge(mem_node_id, place_id, relationship="location")

        # Add decision nodes and link
        for decision in entities.get("decisions", []):
            dec_id = f"decision_{memory_id}_{hash(decision) % 10000}"
            self.graph.add_node(dec_id, node_type="decision", label=decision[:100])
            self.graph.add_edge(mem_node_id, dec_id, relationship="decided")
