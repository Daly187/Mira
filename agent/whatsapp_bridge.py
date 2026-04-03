"""
Mira WhatsApp Bridge — Python HTTP client for the Node.js WhatsApp sidecar.

Mirrors telegram_userbot.py but communicates via HTTP to localhost:3001
instead of using a native library (WhatsApp requires Node.js + Puppeteer).
"""

import asyncio
import logging
from typing import Optional

from config import Config

logger = logging.getLogger("mira.whatsapp")

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.warning("aiohttp not installed — WhatsApp bridge disabled. Run: pip install aiohttp")


class WhatsAppBridge:
    """Async HTTP wrapper around the Node.js WhatsApp sidecar."""

    def __init__(self, mira=None):
        self.mira = mira
        self.base_url = Config.WA_SERVER_URL
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def available(self) -> bool:
        """Whether the Node.js sidecar is reachable and connected."""
        return AIOHTTP_AVAILABLE and self._is_connected

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    async def start(self) -> bool:
        """Check if Node.js sidecar is running and WhatsApp is connected."""
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available — skipping WhatsApp bridge start.")
            return False

        try:
            self._session = aiohttp.ClientSession()
            status = await self._get("/status")
            if status and status.get("ready"):
                self._is_connected = True
                logger.info("WhatsApp bridge connected — sidecar is ready.")
                return True
            elif status and status.get("status") == "qr_pending":
                self._is_connected = False
                logger.info("WhatsApp bridge: QR code pending — scan via /waqr or dashboard.")
                return False
            else:
                self._is_connected = False
                logger.info("WhatsApp bridge: sidecar not ready.")
                return False
        except Exception as e:
            self._is_connected = False
            logger.info(f"WhatsApp bridge: sidecar not reachable ({e}). Start it with: cd agent/whatsapp && npm start")
            return False

    async def stop(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._is_connected = False
        logger.info("WhatsApp bridge stopped.")

    # ── Sending Messages ────────────────────────────────────────

    async def send_message(self, contact_name: str, text: str) -> dict | None:
        """Send a message to a contact via WhatsApp.

        Args:
            contact_name: Contact name (resolved to phone via whatsapp_contacts table)
            text: Message text to send

        Returns:
            dict with message_id and timestamp, or None on failure
        """
        if not self.available:
            logger.warning("WhatsApp bridge not available — cannot send message.")
            return None

        # Resolve contact name to phone number
        phone = await self._resolve_phone(contact_name)
        if not phone:
            logger.error(f"Could not resolve WhatsApp contact: {contact_name}")
            return None

        result = await self._post("/send", {"phone": phone, "text": text})
        if result and result.get("success"):
            logger.info(f"Sent WhatsApp to {contact_name}: {text[:80]}...")
            return {
                "message_id": result.get("message_id"),
                "timestamp": result.get("timestamp"),
                "text": text,
            }

        logger.error(f"Failed to send WhatsApp to {contact_name}: {result}")
        return None

    # ── Reading Messages ────────────────────────────────────────

    async def get_recent_messages(self, contact_name: str, limit: int = 20) -> list[dict]:
        """Get recent messages from a WhatsApp conversation.

        Returns list of dicts: {id, role, content, timestamp}
        """
        if not self.available:
            return []

        phone = await self._resolve_phone(contact_name)
        if not phone:
            return []

        result = await self._get(f"/messages/{phone}?limit={limit}")
        if result and isinstance(result, list):
            return result

        return []

    async def get_unread_dialogs(self) -> list[dict]:
        """Get all WhatsApp chats with unread messages.

        Returns list of dicts: {name, phone, unread_count, last_message}
        """
        if not self.available:
            return []

        result = await self._get("/unread")
        if result and isinstance(result, list):
            return result

        return []

    async def mark_read(self, contact_name: str) -> bool:
        """Mark all messages in a WhatsApp conversation as read."""
        if not self.available:
            return False

        phone = await self._resolve_phone(contact_name)
        if not phone:
            return False

        result = await self._post(f"/read/{phone}", {})
        return bool(result and result.get("success"))

    async def get_contact_info(self, name_or_phone: str) -> dict | None:
        """Get WhatsApp contact info by name or phone."""
        if not self.available:
            return None

        # Try looking up in the DB first
        if self.mira and self.mira.sqlite:
            contact = self.mira.sqlite.get_whatsapp_contact(name=name_or_phone)
            if contact:
                return contact
            contact = self.mira.sqlite.get_whatsapp_contact(phone=name_or_phone)
            if contact:
                return contact

        return None

    async def get_status(self) -> dict:
        """Get bridge connection status including QR code."""
        status = await self._get("/status") or {}
        qr = await self._get("/qr") or {}
        return {**status, "qr": qr.get("qr")}

    # ── Contact Resolution ──────────────────────────────────────

    async def _resolve_phone(self, name_or_phone: str) -> str | None:
        """Resolve a contact name to a phone number.

        Tries in order:
        1. If it looks like a phone number, use directly
        2. Look up in whatsapp_contacts table by name
        """
        # If it starts with + or is all digits, treat as phone
        stripped = name_or_phone.replace("+", "").replace("-", "").replace(" ", "")
        if stripped.isdigit() and len(stripped) >= 7:
            return name_or_phone

        # Look up in DB
        if self.mira and self.mira.sqlite:
            contact = self.mira.sqlite.get_whatsapp_contact(name=name_or_phone)
            if contact and contact.get("phone"):
                return contact["phone"]

        logger.warning(f"Could not resolve WhatsApp phone for: {name_or_phone}")
        return None

    # ── HTTP Helpers ────────────────────────────────────────────

    async def _get(self, path: str) -> dict | list | None:
        """GET request to the Node.js sidecar."""
        try:
            async with self._session.get(f"{self.base_url}{path}", timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(f"WhatsApp GET {path} returned {resp.status}")
                return None
        except Exception as e:
            logger.debug(f"WhatsApp GET {path} failed: {e}")
            return None

    async def _post(self, path: str, data: dict) -> dict | None:
        """POST request to the Node.js sidecar."""
        try:
            async with self._session.post(f"{self.base_url}{path}", json=data, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(f"WhatsApp POST {path} returned {resp.status}")
                return None
        except Exception as e:
            logger.debug(f"WhatsApp POST {path} failed: {e}")
            return None
