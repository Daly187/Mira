"""
WhatsApp Integration — reads messages, classifies by urgency, stores in memory.

Connects via WhatsApp Business API or Baileys library (unofficial but functional).
Groups monitored but never replied to autonomously — summary sent to you.
Voice messages transcribed and processed same as text.

Autonomy levels:
- General contacts: DRAFT + APPROVE (draft reply, you approve before sending)
- Close contacts: ASK FIRST (asks your intent before even drafting)
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("mira.modules.whatsapp")


class WhatsAppModule:
    """Manages WhatsApp message monitoring, classification, and response drafting."""

    def __init__(self, mira):
        self.mira = mira
        self.close_contacts = []  # Loaded from preferences

    async def initialise(self):
        """Set up WhatsApp connection."""
        # Load close contacts list from preferences
        contacts = self.mira.sqlite.get_preference("whatsapp_close_contacts")
        if contacts:
            self.close_contacts = contacts.split(",")
        logger.info("WhatsApp module initialised (connection pending Phase 6)")

    async def process_message(self, message: dict) -> dict:
        """Process an incoming WhatsApp message."""
        sender = message.get("sender", "unknown")
        text = message.get("text", "")
        is_group = message.get("is_group", False)
        is_voice = message.get("is_voice", False)

        # Transcribe voice messages via Whisper
        if is_voice and message.get("audio_path"):
            voice = getattr(self.mira, "voice", None)
            if voice:
                try:
                    transcription = await voice.transcribe(message["audio_path"])
                    if transcription:
                        text = transcription
                        self.mira.sqlite.log_action(
                            "whatsapp", "voice_transcribed",
                            f"from {sender}: {transcription[:100]}",
                        )
                    else:
                        text = "(Voice message — transcription failed)"
                except Exception as e:
                    logger.error(f"WhatsApp voice transcription failed: {e}")
                    text = "(Voice message — transcription error)"
            else:
                text = "(Voice message — Whisper not available)"

        # Classify urgency and relationship
        is_close = sender in self.close_contacts
        classification = await self._classify_message(text, sender, is_group, is_close)

        # Store in memory
        await self.mira.ingest.ingest_text(
            f"WhatsApp from {sender}: {text}",
            source="whatsapp",
            metadata={
                "sender": sender,
                "is_group": is_group,
                "urgency": classification.get("urgency", 3),
            },
        )

        # Update person record
        self.mira.sqlite.upsert_person(name=sender)

        # Determine action based on autonomy rules
        if is_group:
            # Groups: never reply autonomously, just summarise
            return {"action": "monitor", "classification": classification}

        if is_close:
            # Close contacts: ASK FIRST
            if classification.get("urgency", 3) >= 4:
                await self.mira.telegram.send(
                    f"WhatsApp from {sender} (close contact, urgent):\n"
                    f"{text[:300]}\n\n"
                    f"How would you like me to respond?"
                )
            return {"action": "ask_first", "classification": classification}

        # General contacts: DRAFT + APPROVE
        if classification.get("needs_reply", False):
            draft = await self.mira.brain.draft_reply(
                original_message=text,
                sender=sender,
                tone="casual",
            )
            await self.mira.telegram.send(
                f"WhatsApp from {sender}:\n{text[:300]}\n\n"
                f"Draft reply:\n{draft}\n\n"
                f"Approve / Edit / Reject?"
            )
            return {"action": "draft_approve", "draft": draft, "classification": classification}

        return {"action": "stored", "classification": classification}

    async def _classify_message(
        self, text: str, sender: str, is_group: bool, is_close: bool
    ) -> dict:
        """Classify a message by urgency and determine if reply needed."""
        prompt = f"""Classify this WhatsApp message. Return ONLY valid JSON.

From: {sender} ({'close contact' if is_close else 'general contact'})
Group: {is_group}
Message: {text}

Return:
- urgency: 1-5
- needs_reply: true/false
- category: one of [question, update, request, social, spam]
- summary: one-sentence summary"""

        response = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            tier="fast",
            task_type="whatsapp_classify",
            system_override="Classify this message. Return ONLY valid JSON.",
            max_tokens=256,
        )

        try:
            import json
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(cleaned)
        except Exception:
            return {"urgency": 3, "needs_reply": False, "category": "update", "summary": text[:50]}

    async def get_group_summary(self, group_name: str) -> str:
        """Generate summary of recent group activity."""
        messages = self.mira.sqlite.search_memories(
            query=f"WhatsApp {group_name}", limit=20
        )
        if not messages:
            return f"No recent messages from {group_name}"

        return await self.mira.brain.think(
            message=f"Summarise these WhatsApp group messages from {group_name}:\n"
            + "\n".join(m["content"][:200] for m in messages),
            include_history=False,
            tier="fast",
            task_type="whatsapp_summary",
        )
