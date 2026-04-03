"""
Mira Telegram Userbot — Telethon bridge for managing real Telegram conversations.

Sends and reads messages from Daly's personal Telegram account (not the bot).
This is what gives Mira her "voice" — she can message contacts as Daly.
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from config import Config

logger = logging.getLogger("mira.userbot")

# Telethon is optional — graceful fallback if not installed
try:
    from telethon import TelegramClient
    from telethon.errors import FloodWaitError, SessionPasswordNeededError
    from telethon.tl.types import User, Chat, Channel
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    logger.warning("Telethon not installed — userbot features disabled. Run: pip install telethon")


class TelegramUserbot:
    """Thin async wrapper around Telethon for Mira's conversation management."""

    def __init__(self, mira=None):
        self.mira = mira
        self.client = None
        self._started = False

    @property
    def available(self) -> bool:
        """Whether userbot is configured and ready."""
        return self._started and self.client is not None

    async def start(self):
        """Initialize Telethon client and connect."""
        if not TELETHON_AVAILABLE:
            logger.warning("Telethon not available — skipping userbot start.")
            return False

        if not Config.TG_API_ID or not Config.TG_API_HASH:
            logger.info("TG_API_ID/TG_API_HASH not configured — userbot disabled.")
            return False

        try:
            session_path = str(Config.TG_SESSION_PATH)
            self.client = TelegramClient(
                session_path,
                int(Config.TG_API_ID),
                Config.TG_API_HASH,
            )

            await self.client.connect()

            if not await self.client.is_user_authorized():
                if not Config.TG_PHONE:
                    logger.error("TG_PHONE not set — cannot authenticate userbot. Set it in .env.")
                    return False

                logger.info("Userbot not authorized — sending code request...")
                await self.client.send_code_request(Config.TG_PHONE)
                logger.info(
                    "AUTH REQUIRED: Check your Telegram app for the login code. "
                    "Use /userbot_auth <code> via the Mira bot to complete setup."
                )
                # Don't mark as started — needs auth code first
                return False

            self._started = True
            me = await self.client.get_me()
            logger.info(f"Userbot connected as {me.first_name} (@{me.username or 'no username'})")
            return True

        except Exception as e:
            logger.error(f"Userbot start failed: {e}")
            return False

    async def complete_auth(self, code: str, password: str = None) -> bool:
        """Complete 2FA auth with the code sent to Telegram."""
        if not self.client:
            return False

        try:
            await self.client.sign_in(Config.TG_PHONE, code)
            self._started = True
            me = await self.client.get_me()
            logger.info(f"Userbot authenticated as {me.first_name}")
            return True
        except SessionPasswordNeededError:
            if password:
                await self.client.sign_in(password=password)
                self._started = True
                return True
            logger.error("2FA password required. Use /userbot_auth <code> <password>")
            return False
        except Exception as e:
            logger.error(f"Auth failed: {e}")
            return False

    async def stop(self):
        """Disconnect Telethon client."""
        if self.client:
            await self.client.disconnect()
            self._started = False
            logger.info("Userbot disconnected.")

    # ── Sending Messages ────────────────────────────────────────────

    async def send_message(self, contact_name: str, text: str) -> dict | None:
        """Send a message to a contact via Daly's real Telegram account.

        Args:
            contact_name: Contact name or @username to resolve
            text: Message text to send

        Returns:
            dict with message_id and timestamp, or None on failure
        """
        if not self.available:
            logger.warning("Userbot not available — cannot send message.")
            return None

        try:
            entity = await self._resolve_entity(contact_name)
            if not entity:
                logger.error(f"Could not resolve contact: {contact_name}")
                return None

            msg = await self.client.send_message(entity, text)
            logger.info(f"Sent message to {contact_name}: {text[:80]}...")

            return {
                "message_id": msg.id,
                "timestamp": msg.date.isoformat(),
                "text": text,
            }

        except FloodWaitError as e:
            logger.warning(f"Flood wait: {e.seconds}s — retrying after wait.")
            await asyncio.sleep(e.seconds)
            return await self.send_message(contact_name, text)
        except Exception as e:
            logger.error(f"Failed to send to {contact_name}: {e}")
            return None

    # ── Reading Messages ────────────────────────────────────────────

    async def get_recent_messages(self, contact_name: str, limit: int = 20) -> list[dict]:
        """Get recent messages from a conversation.

        Returns list of dicts: {id, role, content, timestamp}
        role is 'user' (them) or 'assistant' (Daly/Mira)
        """
        if not self.available:
            return []

        try:
            entity = await self._resolve_entity(contact_name)
            if not entity:
                return []

            me = await self.client.get_me()
            messages = []

            async for msg in self.client.iter_messages(entity, limit=limit):
                if not msg.text:
                    continue  # skip media-only messages for now
                role = "assistant" if msg.sender_id == me.id else "user"
                messages.append({
                    "id": msg.id,
                    "role": role,
                    "content": msg.text,
                    "timestamp": msg.date.isoformat(),
                })

            # Telethon returns newest first — reverse for chronological order
            messages.reverse()
            return messages

        except FloodWaitError as e:
            logger.warning(f"Flood wait on read: {e.seconds}s")
            await asyncio.sleep(e.seconds)
            return await self.get_recent_messages(contact_name, limit)
        except Exception as e:
            logger.error(f"Failed to read messages from {contact_name}: {e}")
            return []

    async def get_unread_dialogs(self) -> list[dict]:
        """Get all dialogs with unread messages.

        Returns list of dicts: {name, username, unread_count, last_message}
        """
        if not self.available:
            return []

        try:
            dialogs = []
            async for dialog in self.client.iter_dialogs():
                if dialog.unread_count > 0 and isinstance(dialog.entity, User):
                    name = dialog.name or "Unknown"
                    username = getattr(dialog.entity, "username", None) or ""
                    last_msg = dialog.message.text if dialog.message and dialog.message.text else ""
                    dialogs.append({
                        "name": name,
                        "username": username,
                        "unread_count": dialog.unread_count,
                        "last_message": last_msg[:200],
                    })

            return dialogs

        except Exception as e:
            logger.error(f"Failed to get unread dialogs: {e}")
            return []

    async def mark_read(self, contact_name: str) -> bool:
        """Mark all messages in a conversation as read."""
        if not self.available:
            return False

        try:
            entity = await self._resolve_entity(contact_name)
            if not entity:
                return False

            await self.client.send_read_acknowledge(entity)
            return True
        except Exception as e:
            logger.error(f"Failed to mark read for {contact_name}: {e}")
            return False

    # ── Entity Resolution ───────────────────────────────────────────

    async def _resolve_entity(self, name_or_username: str):
        """Resolve a contact name or @username to a Telethon entity.

        Tries in order:
        1. @username (if starts with @)
        2. Exact match in contacts by first name + last name
        3. Partial match in recent dialogs
        """
        try:
            # Direct @username lookup
            if name_or_username.startswith("@"):
                return await self.client.get_entity(name_or_username)

            # Try direct resolution (works for saved contacts)
            try:
                return await self.client.get_entity(name_or_username)
            except (ValueError, TypeError):
                pass

            # Search through recent dialogs for name match
            name_lower = name_or_username.lower()
            async for dialog in self.client.iter_dialogs(limit=200):
                if not isinstance(dialog.entity, User):
                    continue
                dialog_name = dialog.name or ""
                if dialog_name.lower() == name_lower:
                    return dialog.entity
                # Partial match: first name
                first = getattr(dialog.entity, "first_name", "") or ""
                if first.lower() == name_lower:
                    return dialog.entity

            logger.warning(f"Could not resolve entity: {name_or_username}")
            return None

        except Exception as e:
            logger.error(f"Entity resolution failed for {name_or_username}: {e}")
            return None

    async def get_contact_info(self, name_or_username: str) -> dict | None:
        """Get info about a contact (name, username, phone, etc.)."""
        if not self.available:
            return None

        try:
            entity = await self._resolve_entity(name_or_username)
            if not entity or not isinstance(entity, User):
                return None

            return {
                "id": entity.id,
                "first_name": entity.first_name or "",
                "last_name": entity.last_name or "",
                "username": entity.username or "",
                "phone": entity.phone or "",
            }
        except Exception as e:
            logger.error(f"Failed to get contact info for {name_or_username}: {e}")
            return None
