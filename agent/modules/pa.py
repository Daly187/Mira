"""
Personal Assistant Module — Gmail, Calendar, daily briefing, email triage, meeting intelligence.

Autonomy levels vary by domain:
- Work email (Boldr): DRAFT + APPROVE
- Personal email: DRAFT + APPROVE (never sends without confirmation)
- Calendar (Boldr colleagues): FULL AUTO accept during work hours
- Calendar (outside hours): Auto-decline unless marked urgent
"""

import base64
import json
import logging
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger("mira.modules.pa")

MANILA_TZ = ZoneInfo("Asia/Manila")
BOLDR_DOMAIN = "boldr.com"
WORK_HOURS = (9, 18)  # 9am-6pm
WORK_DAYS = range(0, 5)  # Mon-Fri

# Priority senders whose invites get special treatment outside work hours
PRIORITY_SENDERS = [
    s.strip().lower()
    for s in os.getenv("PRIORITY_SENDERS", "").split(",")
    if s.strip()
]


class PAModule:
    """Personal Assistant — email, calendar, briefings, meeting intelligence."""

    def __init__(self, mira):
        self.mira = mira
        self.gmail_service = None
        self.calendar_service = None

    async def initialise(self):
        """Set up Gmail and Calendar API connections via GoogleAuthManager."""
        try:
            from helpers.google_auth import GoogleAuthManager

            auth = GoogleAuthManager()
            self.gmail_service = auth.get_gmail_service()
            self.calendar_service = auth.get_calendar_service()

            if self.gmail_service:
                logger.info("Gmail service connected")
            else:
                logger.warning("Gmail service not available — run google_auth setup")

            if self.calendar_service:
                logger.info("Calendar service connected")
            else:
                logger.warning("Calendar service not available — run google_auth setup")

        except Exception as e:
            logger.warning(f"Google API init skipped: {e}")
            logger.info("PA module initialised (Gmail/Calendar not connected)")

    # ── Email Triage ─────────────────────────────────────────────────

    async def check_email(self) -> list[dict]:
        """Poll Gmail for unread emails, extract fields, triage each one,
        apply labels, store metadata in memory, and alert as needed.

        Triage actions by score:
        - Urgency 5: immediate Telegram alert
        - Importance 4+: flagged for daily briefing
        - Urgency 1-2 AND Importance 1-2: auto-label as "Mira/Low Priority"

        Returns:
            List of triaged email dicts with evaluation data attached.
        """
        if not self.gmail_service:
            logger.debug("Gmail service not connected — skipping email check")
            return []

        # Ensure our custom label exists (cached after first call)
        low_priority_label_id = await self._ensure_label("Mira/Low Priority")

        try:
            results = (
                self.gmail_service.users()
                .messages()
                .list(userId="me", q="is:unread is:inbox", maxResults=20)
                .execute()
            )
            messages = results.get("messages", [])
        except Exception as e:
            logger.error(f"Failed to fetch unread emails: {e}")
            return []

        if not messages:
            logger.debug("No unread emails found")
            return []

        triaged = []
        for msg_stub in messages:
            try:
                msg = (
                    self.gmail_service.users()
                    .messages()
                    .get(userId="me", id=msg_stub["id"], format="full")
                    .execute()
                )

                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                body = self._extract_body(msg.get("payload", {}))

                email_data = {
                    "id": msg["id"],
                    "thread_id": msg.get("threadId"),
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                    "body": body[:2000],  # cap body for triage prompt
                    "snippet": msg.get("snippet", ""),
                    "label_ids": msg.get("labelIds", []),
                }

                # Run through AI triage
                evaluation = await self.triage_email(email_data)
                email_data["evaluation"] = evaluation

                urgency = evaluation.get("urgency", 3)
                importance = evaluation.get("importance", 3)

                # ── Score 5 urgency: immediate Telegram alert ──
                if urgency >= 5:
                    if hasattr(self.mira, "telegram"):
                        await self.mira.telegram.notify(
                            "email",
                            f"URGENT from {email_data.get('from', 'unknown')}",
                            f"{email_data.get('subject', '')}\n{evaluation.get('summary', '')}",
                        )

                # ── Score 4+ importance: flag for daily briefing ──
                if importance >= 4:
                    evaluation["flagged_for_briefing"] = True

                # ── Score 1-2 both: auto-label as low priority ──
                if urgency <= 2 and importance <= 2 and low_priority_label_id:
                    try:
                        self.gmail_service.users().messages().modify(
                            userId="me",
                            id=msg["id"],
                            body={"addLabelIds": [low_priority_label_id]},
                        ).execute()
                        evaluation["auto_labeled"] = "Mira/Low Priority"
                        logger.debug(f"Auto-labeled low priority: {email_data['subject'][:60]}")
                    except Exception as e:
                        logger.warning(f"Failed to apply low-priority label: {e}")

                # ── Store email metadata in memory ──
                await self._store_email_metadata(email_data, evaluation)

                # ── Draft reply if needed ──
                if evaluation.get("draft_needed"):
                    thread_messages = await self.get_thread(email_data["thread_id"])
                    thread_context = "\n---\n".join(
                        f"From: {m['from']}\n{m['body'][:500]}" for m in thread_messages
                    )
                    draft = await self.draft_reply(email_data, context=thread_context)
                    email_data["draft"] = draft

                    # Send draft for approval via Telegram
                    if hasattr(self.mira, "telegram"):
                        await self.mira.telegram.send_draft_for_approval(
                            draft_text=draft,
                            draft_type="email_reply",
                            metadata={
                                "thread_id": email_data["thread_id"],
                                "to": email_data["from"],
                                "subject": f"Re: {email_data['subject']}",
                            },
                        )

                triaged.append(email_data)

            except Exception as e:
                logger.error(f"Error processing email {msg_stub.get('id')}: {e}")

        logger.info(f"Email check complete: {len(triaged)} emails triaged")
        return triaged

    async def _ensure_label(self, label_name: str) -> Optional[str]:
        """Get or create a Gmail label by name. Returns the label ID or None."""
        if not self.gmail_service:
            return None

        try:
            results = self.gmail_service.users().labels().list(userId="me").execute()
            for label in results.get("labels", []):
                if label["name"] == label_name:
                    return label["id"]

            # Label does not exist yet — create it
            created = (
                self.gmail_service.users()
                .labels()
                .create(
                    userId="me",
                    body={
                        "name": label_name,
                        "labelListVisibility": "labelShow",
                        "messageListVisibility": "show",
                    },
                )
                .execute()
            )
            logger.info(f"Created Gmail label: {label_name} (id={created['id']})")
            return created["id"]

        except Exception as e:
            logger.warning(f"Could not ensure Gmail label '{label_name}': {e}")
            return None

    async def _store_email_metadata(self, email_data: dict, evaluation: dict):
        """Persist email metadata into Mira's memory layers."""
        try:
            memory_text = (
                f"Email from {email_data.get('from', 'unknown')}: "
                f"{email_data.get('subject', '(no subject)')}\n"
                f"Urgency: {evaluation.get('urgency')}, "
                f"Importance: {evaluation.get('importance')}\n"
                f"Summary: {evaluation.get('summary', '')}"
            )

            # Store in SQLite as a memory entry
            if hasattr(self.mira, "sqlite") and hasattr(self.mira.sqlite, "add_memory"):
                self.mira.sqlite.add_memory(
                    content=memory_text,
                    source="gmail",
                    category=evaluation.get("category", "general"),
                    metadata={
                        "email_id": email_data.get("id"),
                        "thread_id": email_data.get("thread_id"),
                        "from": email_data.get("from"),
                        "subject": email_data.get("subject"),
                        "urgency": evaluation.get("urgency"),
                        "importance": evaluation.get("importance"),
                        "suggested_action": evaluation.get("suggested_action"),
                    },
                )

            # Store in vector store for semantic retrieval
            if hasattr(self.mira, "vector") and hasattr(self.mira.vector, "add"):
                self.mira.vector.add(
                    text=memory_text,
                    metadata={
                        "source": "gmail",
                        "email_id": email_data.get("id"),
                        "from": email_data.get("from"),
                        "subject": email_data.get("subject"),
                    },
                )

        except Exception as e:
            logger.warning(f"Failed to store email metadata in memory: {e}")

    def _extract_body(self, payload: dict) -> str:
        """Recursively extract plain-text body from a Gmail message payload."""
        if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

        for part in payload.get("parts", []):
            text = self._extract_body(part)
            if text:
                return text

        return ""

    async def get_thread(self, thread_id: str) -> list[dict]:
        """Fetch all messages in a Gmail thread for full context before replying.

        Returns:
            List of dicts with from, subject, date, body for each message in the thread.
        """
        if not self.gmail_service or not thread_id:
            return []

        try:
            thread = (
                self.gmail_service.users()
                .threads()
                .get(userId="me", id=thread_id, format="full")
                .execute()
            )
        except Exception as e:
            logger.error(f"Failed to fetch thread {thread_id}: {e}")
            return []

        messages = []
        for msg in thread.get("messages", []):
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            body = self._extract_body(msg.get("payload", {}))
            messages.append({
                "id": msg["id"],
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "body": body,
            })

        return messages

    async def send_reply(
        self, thread_id: str, to: str, subject: str, body: str
    ) -> dict:
        """Send an approved email reply via Gmail API.

        Called by the Telegram draft-approval flow after user clicks Accept.

        Args:
            thread_id: Gmail thread ID to reply within.
            to: Recipient email address.
            subject: Email subject (typically 'Re: ...' from the original).
            body: Plain-text body content.

        Returns:
            Gmail API send response dict.

        Raises:
            RuntimeError: If Gmail service is not connected.
        """
        if not self.gmail_service:
            raise RuntimeError("Gmail service not connected")

        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        send_body = {"raw": raw}
        if thread_id:
            send_body["threadId"] = thread_id

        try:
            result = (
                self.gmail_service.users()
                .messages()
                .send(userId="me", body=send_body)
                .execute()
            )

            self.mira.sqlite.log_action(
                "pa", "email_sent", f"to={to}, subject={subject[:60]}",
            )
            logger.info(f"Email sent to {to} (thread {thread_id})")
            return result

        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            self.mira.sqlite.log_action(
                "pa", "email_send_failed", f"to={to}, error={str(e)[:100]}",
            )
            raise

    async def triage_email(self, email_data: dict) -> dict:
        """Score email 1-5 for urgency and importance, determine action."""
        evaluation = await self.mira.brain.evaluate_email(email_data)

        self.mira.sqlite.log_action(
            "pa",
            "email_triage",
            f"urgency={evaluation.get('urgency')}, importance={evaluation.get('importance')}",
            {"email_from": email_data.get("from"), "evaluation": evaluation},
        )

        # Auto-file newsletters and marketing emails
        category = evaluation.get("category", "")
        if category in ("newsletter", "marketing", "spam"):
            await self._auto_file_email(email_data, category, evaluation)

        return evaluation

    async def _auto_file_email(self, email_data: dict, category: str, evaluation: dict):
        """Auto-label and optionally archive newsletters, marketing, and spam.

        - newsletter → label "Mira/Newsletter", archive
        - marketing → label "Mira/Marketing", archive
        - spam → label "Mira/Spam", archive
        """
        if not self.gmail_service:
            return

        label_map = {
            "newsletter": "Mira/Newsletter",
            "marketing": "Mira/Marketing",
            "spam": "Mira/Spam",
        }

        label_name = label_map.get(category)
        if not label_name:
            return

        try:
            label_id = await self._ensure_label(label_name)
            if label_id:
                # Apply label and remove from inbox (archive)
                self.gmail_service.users().messages().modify(
                    userId="me",
                    id=email_data["id"],
                    body={
                        "addLabelIds": [label_id],
                        "removeLabelIds": ["INBOX"],
                    },
                ).execute()

                self.mira.sqlite.log_action(
                    "pa", "email_auto_filed",
                    f"{category}: {email_data.get('subject', '')[:60]}",
                    {"from": email_data.get("from"), "category": category},
                )
                logger.info(f"Auto-filed {category} email: {email_data.get('subject', '')[:60]}")

        except Exception as e:
            logger.warning(f"Failed to auto-file {category} email: {e}")

    async def draft_reply(self, email_data: dict, context: str = None) -> str:
        """Draft a reply in the user's voice."""
        reply = await self.mira.brain.draft_reply(
            original_message=email_data.get("body", ""),
            sender=email_data.get("from", "unknown"),
            context=context,
        )
        return reply

    # ── Calendar Management ──────────────────────────────────────────

    async def check_calendar_invites(self) -> list[dict]:
        """Fetch and evaluate pending calendar invites (responseStatus = needsAction).

        Decision rules:
        - Boldr colleagues during work hours (9am-6pm Manila, Mon-Fri):
          auto-accept unless there is a scheduling conflict.
        - Outside work hours: auto-decline UNLESS the sender is on the
          priority list (PRIORITY_SENDERS env var) or the subject/description
          contains 'urgent'.
        - Ambiguous cases (non-Boldr during work hours, priority senders
          outside hours, etc.) are evaluated via brain.think() with Haiku tier.
        - All accept/decline decisions are logged to action_log.
        - Telegram notification sent for each decision.

        Returns:
            List of invite event dicts with decision data attached.
        """
        if not self.calendar_service:
            logger.debug("Calendar service not connected — skipping invite check")
            return []

        now = datetime.now(MANILA_TZ)
        # Look 7 days ahead for pending invites
        time_min = now.isoformat()
        time_max = (now + timedelta(days=7)).isoformat()

        try:
            events_result = (
                self.calendar_service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])
        except Exception as e:
            logger.error(f"Failed to fetch calendar events for invite check: {e}")
            return []

        # Filter to only events needing a response
        pending = [
            ev for ev in events
            if self._get_my_response_status(ev) == "needsAction"
        ]

        if not pending:
            logger.debug("No pending calendar invites found")
            return []

        results = []
        for event in pending:
            event_data = {
                "id": event.get("id"),
                "summary": event.get("summary", "(No title)"),
                "start": event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
                "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"),
                "organizer": event.get("organizer", {}).get("email", ""),
                "attendees": [a.get("email", "") for a in event.get("attendees", [])],
                "description": event.get("description", ""),
                "location": event.get("location", ""),
                "html_link": event.get("htmlLink", ""),
            }

            decision = await self.evaluate_invite(event_data)
            event_data["invite_decision"] = decision

            action = decision["action"]

            if action == "accept":
                await self._respond_to_invite(event["id"], "accepted")
                event_data["my_status"] = "accepted"
            elif action == "decline":
                await self._respond_to_invite(event["id"], "declined")
                event_data["my_status"] = "declined"
            elif action == "ask_user":
                event_data["my_status"] = "needsAction"

            # Log every decision to action_log
            self.mira.sqlite.log_action(
                "pa",
                f"invite_{action}",
                f"event='{event_data['summary']}', organizer={event_data['organizer']}",
                {
                    "event_id": event_data["id"],
                    "reason": decision.get("reason", ""),
                    "start": event_data["start"],
                },
            )

            # Telegram notification for each decision
            if hasattr(self.mira, "telegram"):
                status_emoji = {"accept": "Accepted", "decline": "Declined", "ask_user": "Needs your input"}
                await self.mira.telegram.notify(
                    "calendar",
                    f"Invite {status_emoji.get(action, action)}: {event_data['summary']}",
                    f"Organizer: {event_data['organizer']}\n"
                    f"Time: {event_data['start']}\n"
                    f"Reason: {decision.get('reason', '')}",
                )

            results.append(event_data)

        logger.info(f"Calendar invite check: {len(results)} pending invites processed")
        return results

    async def check_calendar(self) -> list[dict]:
        """Fetch upcoming events for next 24 hours, check pending invites,
        and generate meeting briefs for events starting within 30 minutes.

        Returns:
            List of event dicts with status and optional briefs.
        """
        if not self.calendar_service:
            logger.debug("Calendar service not connected — skipping calendar check")
            return []

        now = datetime.now(MANILA_TZ)
        time_min = now.isoformat()
        time_max = (now + timedelta(hours=24)).isoformat()

        try:
            events_result = (
                self.calendar_service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])
        except Exception as e:
            logger.error(f"Failed to fetch calendar events: {e}")
            return []

        processed = []
        for event in events:
            event_data = {
                "id": event.get("id"),
                "summary": event.get("summary", "(No title)"),
                "start": event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
                "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"),
                "organizer": event.get("organizer", {}).get("email", ""),
                "attendees": [
                    a.get("email", "") for a in event.get("attendees", [])
                ],
                "status": event.get("status"),
                "my_status": self._get_my_response_status(event),
                "description": event.get("description", ""),
                "location": event.get("location", ""),
                "html_link": event.get("htmlLink", ""),
            }

            # Pending invites handled by check_calendar_invites() now,
            # but still handle inline if encountered here
            if event_data["my_status"] == "needsAction":
                decision = await self.evaluate_invite(event_data)
                event_data["invite_decision"] = decision

                if decision["action"] == "accept":
                    await self._respond_to_invite(event["id"], "accepted")
                    event_data["my_status"] = "accepted"
                elif decision["action"] == "decline":
                    await self._respond_to_invite(event["id"], "declined")
                    event_data["my_status"] = "declined"
                elif decision["action"] == "ask_user" and hasattr(self.mira, "telegram"):
                    await self.mira.telegram.notify(
                        "calendar",
                        f"Invite needs your decision: {event_data['summary']}",
                        decision["reason"],
                    )

            # Generate meeting brief for events starting within 30 minutes
            start_str = event_data["start"]
            if start_str and "T" in start_str:
                try:
                    start_dt = datetime.fromisoformat(start_str)
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=MANILA_TZ)
                    mins_until = (start_dt - now).total_seconds() / 60
                    if 0 < mins_until <= 30 and event_data["my_status"] in ("accepted", "tentative"):
                        brief = await self.generate_meeting_brief(event_data)
                        event_data["meeting_brief"] = brief

                        if hasattr(self.mira, "telegram"):
                            await self.mira.telegram.send(
                                f"MEETING BRIEF — {event_data['summary']} (in {int(mins_until)} min)\n\n{brief}"
                            )
                except (ValueError, TypeError):
                    pass

            processed.append(event_data)

        logger.info(f"Calendar check: {len(processed)} events in next 24h")
        return processed

    def _get_my_response_status(self, event: dict) -> str:
        """Extract the current user's response status from event attendees."""
        for attendee in event.get("attendees", []):
            if attendee.get("self"):
                return attendee.get("responseStatus", "needsAction")
        return "accepted"  # organizer is implicitly accepted

    async def _respond_to_invite(self, event_id: str, response: str):
        """Accept or decline a calendar invite."""
        if not self.calendar_service:
            return

        try:
            event = (
                self.calendar_service.events()
                .get(calendarId="primary", eventId=event_id)
                .execute()
            )

            for attendee in event.get("attendees", []):
                if attendee.get("self"):
                    attendee["responseStatus"] = response

            self.calendar_service.events().patch(
                calendarId="primary",
                eventId=event_id,
                body={"attendees": event.get("attendees", [])},
                sendUpdates="all",
            ).execute()

            self.mira.sqlite.log_action(
                "pa", f"invite_{response}", f"event={event.get('summary', event_id)}"
            )
            logger.info(f"Calendar invite {response}: {event.get('summary')}")

        except Exception as e:
            logger.error(f"Failed to respond to invite {event_id}: {e}")

    async def evaluate_invite(self, event: dict) -> dict:
        """Evaluate a calendar invite and decide: accept, decline, or ask_user.

        Rules:
        1. Work hours (9am-6pm Manila, Mon-Fri) + Boldr sender -> auto-accept if no conflict
        2. Outside work hours + priority sender or 'urgent' keyword -> use AI to evaluate
        3. Outside work hours + normal sender -> auto-decline
        4. Work hours + non-Boldr sender -> use AI to evaluate (ambiguous)

        Returns:
            dict with keys: action ("accept"|"decline"|"ask_user"), reason (str)
        """
        organizer = event.get("organizer", "")
        summary = event.get("summary", "")
        description = event.get("description", "").lower()
        start_str = event.get("start", "")

        # Parse event start time
        is_work_hours = False
        if start_str and "T" in start_str:
            try:
                start_dt = datetime.fromisoformat(start_str)
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=MANILA_TZ)
                start_manila = start_dt.astimezone(MANILA_TZ)
                is_work_hours = (
                    start_manila.weekday() in WORK_DAYS
                    and WORK_HOURS[0] <= start_manila.hour < WORK_HOURS[1]
                )
            except (ValueError, TypeError):
                pass

        is_boldr = BOLDR_DOMAIN in organizer.lower()
        is_urgent = "urgent" in description or "urgent" in summary.lower()
        is_priority_sender = any(
            ps in organizer.lower() for ps in PRIORITY_SENDERS
        ) if PRIORITY_SENDERS else False

        # Check for conflicts
        has_conflict = await self._check_conflict(start_str, event.get("end", ""))

        # Peak cognitive window protection (9-11am Manila)
        is_peak_window = False
        if start_str and "T" in start_str:
            try:
                start_dt = datetime.fromisoformat(start_str)
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=MANILA_TZ)
                start_manila = start_dt.astimezone(MANILA_TZ)
                is_peak_window = 9 <= start_manila.hour < 11
            except (ValueError, TypeError):
                pass

        # ── Rule 0: Peak cognitive window — protect deep work time ──
        if is_peak_window and not is_urgent:
            # Check if this is a 1:1 or a large meeting
            attendee_count = len(event.get("attendees", []))
            if attendee_count > 3:
                return {
                    "action": "ask_user",
                    "reason": f"'{summary}' is during your peak cognitive window (9-11am). "
                              f"Large meeting ({attendee_count} attendees) — consider rescheduling for deep work protection.",
                }

        # ── Rule 1: Work hours + Boldr sender ──
        if is_work_hours and is_boldr:
            if has_conflict:
                return {
                    "action": "ask_user",
                    "reason": f"Boldr invite '{summary}' conflicts with an existing event.",
                }
            return {
                "action": "accept",
                "reason": f"Boldr invite during work hours — auto-accepted.",
            }

        # ── Rule 2: Outside work hours ──
        if not is_work_hours:
            if is_urgent or is_priority_sender:
                # Ambiguous — use AI to decide
                return await self._ai_evaluate_invite(event, context=(
                    f"Outside work hours but {'marked urgent' if is_urgent else 'from priority sender'}. "
                    f"Sender: {organizer}. "
                    f"Priority sender: {is_priority_sender}. Urgent: {is_urgent}."
                ))
            return {
                "action": "decline",
                "reason": f"Outside work hours (auto-declined): '{summary}'.",
            }

        # ── Rule 3: Work hours but non-Boldr sender — ambiguous, use AI ──
        return await self._ai_evaluate_invite(event, context=(
            f"During work hours but non-Boldr sender: {organizer}. "
            f"Conflict: {has_conflict}."
        ))

    async def _ai_evaluate_invite(self, event: dict, context: str = "") -> dict:
        """Use brain.think() with Haiku tier to evaluate an ambiguous calendar invite.

        Returns:
            dict with keys: action ("accept"|"decline"|"ask_user"), reason (str)
        """
        prompt = f"""Evaluate this calendar invite and decide what to do.

Event: {event.get('summary', '(No title)')}
Organizer: {event.get('organizer', 'unknown')}
Start: {event.get('start', 'unknown')}
End: {event.get('end', 'unknown')}
Description: {event.get('description', '')[:500]}
Attendees: {', '.join(event.get('attendees', [])[:10])}

Context: {context}

The user works at Boldr (BPO), based in Manila (UTC+8). Work hours are 9am-6pm Mon-Fri.

Return ONLY valid JSON with:
- action: one of "accept", "decline", "ask_user"
- reason: one-sentence explanation for the decision

Lean toward "ask_user" if genuinely uncertain. Only auto-accept/decline when the right choice is clear."""

        try:
            response = await self.mira.brain.think(
                message=prompt,
                include_history=False,
                system_override="You are a calendar management system. Return ONLY valid JSON.",
                max_tokens=256,
                tier="fast",
                task_type="invite_evaluation",
            )

            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]

            result = json.loads(cleaned)
            # Validate action field
            if result.get("action") not in ("accept", "decline", "ask_user"):
                result["action"] = "ask_user"
            return result

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"AI invite evaluation failed, defaulting to ask_user: {e}")
            return {
                "action": "ask_user",
                "reason": f"Could not evaluate automatically: '{event.get('summary', '')}'.",
            }

    async def _check_conflict(self, start: str, end: str) -> bool:
        """Check if there is an existing accepted event overlapping the given time range."""
        if not self.calendar_service or not start or not end:
            return False

        try:
            events_result = (
                self.calendar_service.events()
                .list(
                    calendarId="primary",
                    timeMin=start,
                    timeMax=end,
                    singleEvents=True,
                )
                .execute()
            )
            for ev in events_result.get("items", []):
                my_status = self._get_my_response_status(ev)
                if my_status in ("accepted", "tentative"):
                    return True
        except Exception as e:
            logger.error(f"Conflict check failed: {e}")

        return False

    async def generate_meeting_brief(self, meeting: dict) -> str:
        """Generate prep brief 30 minutes before meeting."""
        participants = meeting.get("attendees", meeting.get("participants", []))

        people_context = []
        for name in participants:
            if hasattr(self.mira, "sqlite") and hasattr(self.mira.sqlite, "get_person"):
                person = self.mira.sqlite.get_person(name)
                if person:
                    people_context.append(person)

        relevant_memories = []
        if hasattr(self.mira, "sqlite") and hasattr(self.mira.sqlite, "search_memories"):
            relevant_memories = self.mira.sqlite.search_memories(
                query=meeting.get("summary", meeting.get("title", "")), limit=5
            )

        brief_data = {
            "meeting": meeting,
            "participants": people_context,
            "relevant_memories": relevant_memories,
        }

        return await self.mira.brain.think(
            f"Generate a meeting prep brief:\n{json.dumps(brief_data, indent=2, default=str)}",
            include_history=False,
            tier="standard",
            task_type="meeting_brief",
        )

    # ── Post-Meeting Action Prompts ────────────────────────────────────

    async def check_post_meeting_actions(self):
        """Check if any meeting ended in the last hour and prompt for action items.

        Called by scheduler every 15 minutes. Finds meetings that ended
        within the last 60 minutes and sends a Telegram prompt asking for
        key decisions, action items, and follow-ups.
        """
        if not self.calendar_service:
            return

        now = datetime.now(MANILA_TZ)
        one_hour_ago = now - timedelta(hours=1)

        try:
            events_result = (
                self.calendar_service.events()
                .list(
                    calendarId="primary",
                    timeMin=one_hour_ago.isoformat(),
                    timeMax=now.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except Exception as e:
            logger.error(f"Post-meeting check failed: {e}")
            return

        for event in events_result.get("items", []):
            end_str = event.get("end", {}).get("dateTime")
            if not end_str:
                continue

            try:
                end_dt = datetime.fromisoformat(end_str)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=MANILA_TZ)
            except (ValueError, TypeError):
                continue

            # Meeting ended between 5 and 60 minutes ago
            minutes_since_end = (now - end_dt).total_seconds() / 60
            if not (5 <= minutes_since_end <= 60):
                continue

            # Only for meetings I accepted
            my_status = self._get_my_response_status(event)
            if my_status not in ("accepted", "tentative"):
                continue

            event_id = event.get("id", "")
            summary = event.get("summary", "(No title)")

            # Skip if we already prompted for this meeting
            already_prompted = self.mira.sqlite.conn.execute(
                "SELECT id FROM action_log WHERE action = 'post_meeting_prompt' AND outcome LIKE ?",
                (f"%{event_id}%",),
            ).fetchone()
            if already_prompted:
                continue

            # Send prompt
            attendees = [a.get("email", "") for a in event.get("attendees", [])]
            msg = (
                f"Meeting just ended: {summary}\n"
                f"Attendees: {', '.join(attendees[:5])}\n\n"
                f"Quick capture — reply with:\n"
                f"- Key decisions made\n"
                f"- Action items (who owes what)\n"
                f"- Follow-ups needed\n\n"
                f"Or just say 'nothing' to skip."
            )

            if hasattr(self.mira, "telegram"):
                await self.mira.telegram.send(msg)

            self.mira.sqlite.log_action(
                "pa", "post_meeting_prompt", f"event_id={event_id}: {summary[:60]}"
            )

    # ── Weekly Calendar Review ────────────────────────────────────────

    async def generate_weekly_calendar_review(self) -> str:
        """Review next week's calendar — identify conflicts, overloaded days,
        meetings that could be emails, and prep requirements.
        """
        if not self.calendar_service:
            return "Calendar service not connected."

        now = datetime.now(MANILA_TZ)
        # Next Monday through Friday
        days_until_monday = (7 - now.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = (now + timedelta(days=days_until_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        next_friday_end = (next_monday + timedelta(days=5)).replace(
            hour=23, minute=59, second=59
        )

        try:
            events_result = (
                self.calendar_service.events()
                .list(
                    calendarId="primary",
                    timeMin=next_monday.isoformat(),
                    timeMax=next_friday_end.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=50,
                )
                .execute()
            )
            events = events_result.get("items", [])
        except Exception as e:
            logger.error(f"Weekly calendar review failed: {e}")
            return "Could not fetch next week's calendar."

        if not events:
            return f"Next week ({next_monday.strftime('%b %d')} — {next_friday_end.strftime('%b %d')}): No meetings scheduled."

        # Build day-by-day summary
        by_day = {}
        for ev in events:
            start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", ""))
            try:
                day = datetime.fromisoformat(start).strftime("%A %b %d")
            except (ValueError, TypeError):
                day = "Unknown"
            by_day.setdefault(day, []).append({
                "summary": ev.get("summary", "(No title)"),
                "start": start,
                "duration_min": self._calc_duration_min(ev),
                "attendees": len(ev.get("attendees", [])),
                "organizer": ev.get("organizer", {}).get("email", ""),
            })

        prompt = f"""Review next week's calendar and provide insights.

Week: {next_monday.strftime('%b %d')} — {next_friday_end.strftime('%b %d, %Y')}

Meetings by day:
{json.dumps(by_day, indent=2, default=str)}

Total meetings: {len(events)}

Provide:
1. Day-by-day overview (busiest day, light days)
2. Any scheduling conflicts or back-to-back meetings without breaks
3. Meetings with 5+ attendees that might be able to be async
4. Prep needed (any meetings requiring research or materials)
5. Suggested time blocks for deep work

Keep it concise and actionable."""

        review = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=1500,
            tier="standard",
            task_type="calendar_review",
        )

        self.mira.sqlite.log_action(
            "pa", "weekly_calendar_review",
            f"next week: {len(events)} meetings reviewed",
        )
        return review

    def _calc_duration_min(self, event: dict) -> int:
        """Calculate event duration in minutes."""
        try:
            start = event.get("start", {}).get("dateTime")
            end = event.get("end", {}).get("dateTime")
            if start and end:
                s = datetime.fromisoformat(start)
                e = datetime.fromisoformat(end)
                return int((e - s).total_seconds() / 60)
        except (ValueError, TypeError):
            pass
        return 0

    # ── Daily Briefing ───────────────────────────────────────────────

    async def generate_daily_briefing(self) -> str:
        """Generate the morning briefing — delivered via Telegram."""
        now = datetime.now(MANILA_TZ)

        # Gather email summary for briefing
        briefing_emails = []
        try:
            triaged = await self.check_email()
            briefing_emails = [
                {
                    "from": e.get("from", ""),
                    "subject": e.get("subject", ""),
                    "urgency": e.get("evaluation", {}).get("urgency"),
                    "importance": e.get("evaluation", {}).get("importance"),
                    "summary": e.get("evaluation", {}).get("summary", ""),
                    "suggested_action": e.get("evaluation", {}).get("suggested_action", ""),
                }
                for e in triaged
                if e.get("evaluation", {}).get("importance", 0) >= 3
            ]
        except Exception as e:
            logger.warning(f"Could not fetch emails for briefing: {e}")

        # Gather calendar events for briefing
        calendar_events = []
        try:
            events = await self.check_calendar()
            calendar_events = [
                {
                    "summary": ev.get("summary"),
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                    "my_status": ev.get("my_status"),
                    "location": ev.get("location"),
                }
                for ev in events
            ]
        except Exception as e:
            logger.warning(f"Could not fetch calendar for briefing: {e}")

        # Gather habit streaks for briefing
        habit_streaks = []
        try:
            personal = getattr(self.mira, "personal", None)
            if personal:
                stats = await personal.get_habit_stats()
                habit_streaks = [
                    {"name": h["name"], "streak": h["streak"], "done_today": h["last_completed"] == now.strftime("%Y-%m-%d")}
                    for h in stats
                ]
        except Exception as e:
            logger.warning(f"Could not fetch habits for briefing: {e}")

        # Gather upcoming important dates (next 7 days)
        upcoming_dates = []
        try:
            personal = getattr(self.mira, "personal", None)
            if personal:
                upcoming_dates = await personal.get_upcoming_dates(days=7)
        except Exception as e:
            logger.warning(f"Could not fetch important dates for briefing: {e}")

        data = {
            "date": now.strftime("%A, %B %d, %Y"),
            "time": now.strftime("%H:%M"),
            "timezone": "Manila (UTC+8)",
            "pending_tasks": self.mira.sqlite.get_pending_tasks(),
            "open_trades": self.mira.sqlite.get_open_trades(),
            "recent_memories": self.mira.sqlite.get_recent_memories(10),
            "todays_actions": self.mira.sqlite.get_daily_actions(),
            "memory_stats": self.mira.sqlite.get_stats(),
            "priority_emails": briefing_emails,
            "todays_calendar": calendar_events,
            "habit_streaks": habit_streaks,
            "upcoming_dates": upcoming_dates,
        }

        briefing = await self.mira.brain.generate_briefing(data)
        return briefing

    # ── Weekly Email Digest ─────────────────────────────────────────

    async def generate_weekly_email_digest(self) -> str:
        """Generate a concise weekly digest of low-priority emails.

        Queries all emails triaged as importance <= 2 in the last 7 days from
        memory, groups them by sender/topic, and uses brain.think() with
        standard tier to produce a summary digest.

        Wired as a weekly scheduled task (Sundays at 6pm alongside calendar review).

        Returns:
            Formatted weekly email digest string.
        """
        cutoff = (datetime.now(MANILA_TZ) - timedelta(days=7)).isoformat()

        # Pull low-importance email memories from the last 7 days
        try:
            rows = self.mira.sqlite.conn.execute(
                """SELECT content, metadata, created_at FROM memories
                   WHERE source = 'gmail'
                     AND created_at >= ?
                   ORDER BY created_at DESC""",
                (cutoff,),
            ).fetchall()
        except Exception as e:
            logger.error(f"Failed to query email memories for weekly digest: {e}")
            return "Could not generate weekly email digest — memory query failed."

        # Filter to importance <= 2 using stored metadata
        low_priority_emails = []
        for row in rows:
            row_dict = dict(row)
            try:
                meta = json.loads(row_dict.get("metadata", "{}"))
            except (json.JSONDecodeError, TypeError):
                meta = {}
            importance = meta.get("importance", 3)
            if importance is not None and importance <= 2:
                low_priority_emails.append({
                    "content": row_dict["content"],
                    "from": meta.get("from", "unknown"),
                    "subject": meta.get("subject", "(no subject)"),
                    "importance": importance,
                    "urgency": meta.get("urgency", 0),
                    "suggested_action": meta.get("suggested_action", ""),
                    "date": row_dict.get("created_at", ""),
                })

        if not low_priority_emails:
            logger.info("No low-priority emails found for weekly digest")
            return "No low-priority emails in the last 7 days — inbox is clean."

        # Group by sender for the prompt
        by_sender = {}
        for email in low_priority_emails:
            sender = email["from"]
            by_sender.setdefault(sender, []).append(email)

        grouped_summary = []
        for sender, emails in by_sender.items():
            subjects = [e["subject"] for e in emails]
            grouped_summary.append({
                "sender": sender,
                "count": len(emails),
                "subjects": subjects[:10],  # cap to avoid huge prompts
            })

        prompt = f"""Generate a concise weekly email digest.

These are the low-priority emails (importance 1-2) from the past 7 days, grouped by sender.
The user hasn't looked at these — give them a quick, scannable summary so they know if anything
actually needs attention or can be safely ignored.

Email data (grouped by sender):
{json.dumps(grouped_summary, indent=2, default=str)}

Total emails: {len(low_priority_emails)}

Format:
1. One-line overall summary (e.g. "23 low-priority emails this week — mostly newsletters and notifications")
2. Group by sender/category with 1-line summaries
3. Call out anything that might actually need attention despite the low score
4. End with a recommendation (archive all, review X, etc.)

Keep it concise and scannable. This is a weekly catch-up, not a deep dive."""

        digest = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=1500,
            tier="standard",
            task_type="weekly_email_digest",
        )

        self.mira.sqlite.log_action(
            "pa", "weekly_email_digest", f"generated ({len(low_priority_emails)} emails summarised)",
        )

        return digest

    # ── EOW Summary (Boldr) ──────────────────────────────────────────

    async def generate_eow_summary(self) -> str:
        """Generate end-of-week summary — pull meetings, emails, actions, tasks.

        Synthesises data from the current week into a concise executive summary
        suitable for sending to David and Andrew at Boldr.
        """
        now = datetime.now(MANILA_TZ)
        # Monday of this week
        week_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_start_str = week_start.isoformat()

        # 1. Gather this week's actions
        actions = []
        try:
            all_actions = self.mira.sqlite.get_daily_actions()
            # Also pull actions from earlier in the week
            rows = self.mira.sqlite.conn.execute(
                "SELECT * FROM action_log WHERE created_at >= ? ORDER BY created_at",
                (week_start_str,),
            ).fetchall()
            actions = [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"EOW: could not fetch actions: {e}")

        # 2. Gather completed tasks this week
        tasks_completed = []
        try:
            rows = self.mira.sqlite.conn.execute(
                "SELECT * FROM tasks WHERE completed_at IS NOT NULL AND completed_at >= ?",
                (week_start_str,),
            ).fetchall()
            tasks_completed = [dict(r) for r in rows]
        except Exception:
            pass

        # 3. Gather this week's calendar events
        calendar_events = []
        try:
            if self.calendar_service:
                events_result = (
                    self.calendar_service.events()
                    .list(
                        calendarId="primary",
                        timeMin=week_start.isoformat() + "Z" if not week_start.tzinfo else week_start.isoformat(),
                        timeMax=now.isoformat(),
                        singleEvents=True,
                        orderBy="startTime",
                        maxResults=50,
                    )
                    .execute()
                )
                calendar_events = [
                    {
                        "summary": ev.get("summary", ""),
                        "start": ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", "")),
                        "attendees": len(ev.get("attendees", [])),
                    }
                    for ev in events_result.get("items", [])
                ]
        except Exception as e:
            logger.warning(f"EOW: could not fetch calendar: {e}")

        # 4. Gather email stats
        email_stats = {"total_triaged": 0, "urgent": 0, "replied": 0}
        try:
            rows = self.mira.sqlite.conn.execute(
                "SELECT * FROM action_log WHERE module = 'pa' AND action LIKE '%email%' AND created_at >= ?",
                (week_start_str,),
            ).fetchall()
            email_stats["total_triaged"] = len([r for r in rows if "triage" in dict(r).get("action", "")])
            email_stats["urgent"] = len([r for r in rows if "alert" in dict(r).get("action", "")])
            email_stats["replied"] = len([r for r in rows if "sent" in dict(r).get("action", "")])
        except Exception:
            pass

        data = {
            "week": f"{week_start.strftime('%b %d')} — {now.strftime('%b %d, %Y')}",
            "meetings_attended": len(calendar_events),
            "meetings": calendar_events[:20],
            "tasks_completed": len(tasks_completed),
            "task_titles": [t.get("title", "") for t in tasks_completed[:15]],
            "total_actions": len(actions),
            "email_stats": email_stats,
            "action_summary_by_module": {},
        }

        # Group actions by module
        for a in actions:
            mod = a.get("module", "other")
            data["action_summary_by_module"].setdefault(mod, 0)
            data["action_summary_by_module"][mod] += 1

        prompt = f"""Generate a concise end-of-week summary for Boldr leadership (David and Andrew).

Week data:
{json.dumps(data, indent=2, default=str)}

Format:
1. One-line executive summary
2. Key accomplishments (3-5 bullet points)
3. Meetings attended this week (count + highlights)
4. Email management (triaged, urgent, replied)
5. Items carrying over to next week
6. Any concerns or blockers

Keep it professional, concise, and action-oriented. 300-500 words max."""

        summary = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=1500,
            tier="standard",
            task_type="eow_summary",
        )

        self.mira.sqlite.log_action("pa", "eow_summary", "generated")
        return summary
