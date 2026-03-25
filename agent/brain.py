"""
Mira's Brain — Claude API integration with tiered model routing.

Tier system:
- local (Ollama): On-device, free — classification, entity extraction, formatting
- fast (Haiku): JSON extraction, classification, simple parsing — ~$0.80/1M input
- standard (Sonnet): Conversation, analysis, drafting — ~$3/1M input
- deep (Opus): Research, decision briefs, complex reasoning — ~$15/1M input

Simple tasks try the local model first. If unavailable or quality is poor,
they silently escalate to Haiku. The user never sees an error from local.
"""

import json
import logging
from datetime import datetime
from typing import Optional

import anthropic

try:
    import httpx
except ImportError:
    httpx = None

from config import Config
from personality import MIRA_SYSTEM_PROMPT, get_system_prompt

logger = logging.getLogger("mira.brain")

# Tasks that should NEVER use local model (need personality or complex reasoning)
LOCAL_BLOCKED_TASKS = frozenset({
    "conversation",
    "draft_reply",
    "daily_briefing",
    "deep_research",
    "decision_brief",
    "polymarket_analysis",
    "analysis",
})

# Tasks that are good candidates for local model
LOCAL_ELIGIBLE_TASKS = frozenset({
    "entity_extraction",
    "classification",
    "sentiment_analysis",
    "keyword_extraction",
    "simple_qa",
    "data_formatting",
    "text_summarization_short",
})


class LocalLLMClient:
    """Client for local LLM inference via Ollama / OpenAI-compatible API."""

    def __init__(self, base_url: str, model: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._available = False
        if httpx:
            self._http = httpx.AsyncClient(timeout=timeout)
        else:
            self._http = None

    async def check_health(self) -> bool:
        """Ping the local model server. Returns True if reachable."""
        if not self._http:
            self._available = False
            return False

        # Try Ollama endpoint
        try:
            resp = await self._http.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                self._available = True
                return True
        except Exception:
            pass

        # Try OpenAI-compatible endpoint
        try:
            resp = await self._http.get(f"{self.base_url}/v1/models", timeout=5)
            if resp.status_code == 200:
                self._available = True
                return True
        except Exception:
            pass

        self._available = False
        return False

    @property
    def is_available(self) -> bool:
        return self._available

    async def chat(self, messages: list, system: str = None, max_tokens: int = 1024) -> dict:
        """Send a chat completion request. Returns dict with text, input_tokens, output_tokens."""
        if not self._http:
            raise RuntimeError("httpx not installed")

        payload = {
            "model": self.model,
            "messages": [],
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "stream": False,
        }
        if system:
            payload["messages"].append({"role": "system", "content": system})
        payload["messages"].extend(messages)

        resp = await self._http.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})

        return {
            "text": choice["message"]["content"],
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }

    async def close(self):
        if self._http:
            await self._http.aclose()


class MiraBrain:
    """Claude API integration with tiered model routing for cost optimization."""

    def __init__(self, sqlite_store=None):
        self.client = None
        self.local_client = None
        self.sqlite = sqlite_store
        self.conversation_history = []
        self.max_history = 20

    def initialise(self):
        """Set up the Anthropic client and optional local model."""
        if not Config.ANTHROPIC_API_KEY:
            logger.error("Cannot initialise brain: ANTHROPIC_API_KEY not set")
            return False

        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

        tier_info = (
            f"Brain initialised — Fast: {Config.CLAUDE_MODEL_FAST}, "
            f"Standard: {Config.CLAUDE_MODEL_STANDARD}, "
            f"Deep: {Config.CLAUDE_MODEL_DEEP}"
        )

        # Initialize local model if enabled
        if Config.LOCAL_MODEL_ENABLED:
            self.local_client = LocalLLMClient(
                base_url=Config.LOCAL_MODEL_URL,
                model=Config.LOCAL_MODEL_NAME,
                timeout=Config.LOCAL_MODEL_TIMEOUT,
            )
            tier_info += f", Local: {Config.LOCAL_MODEL_NAME}"
            logger.info(f"Local model configured: {Config.LOCAL_MODEL_NAME} at {Config.LOCAL_MODEL_URL}")

        logger.info(tier_info)
        return True

    async def refresh_local_model_status(self):
        """Re-check if local model is available. Call periodically."""
        if self.local_client:
            was = self.local_client.is_available
            now = await self.local_client.check_health()
            if was != now:
                status = "online" if now else "offline"
                logger.info(f"Local model status changed: {status}")

    def _local_quality_check_failed(self, response: str, task_type: str) -> bool:
        """Check if local model response is too low quality. Returns True if should escalate."""
        if not response or not response.strip():
            return True

        stripped = response.strip()

        # Too short for structured tasks
        if task_type in ("entity_extraction", "email_triage") and len(stripped) < 10:
            return True

        # JSON tasks must be parseable
        if task_type in ("entity_extraction", "email_triage", "classification"):
            cleaned = stripped
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
            try:
                json.loads(cleaned)
            except json.JSONDecodeError:
                return True

        # Repetition detector (local models sometimes loop)
        if len(stripped) > 100:
            words = stripped.split()
            if len(words) > 20:
                unique_ratio = len(set(words)) / len(words)
                if unique_ratio < 0.3:
                    return True

        return False

    async def think(
        self,
        message: str,
        context: str = None,
        system_override: str = None,
        max_tokens: int = None,
        include_history: bool = True,
        tier: str = "standard",
        task_type: str = "conversation",
    ) -> str:
        """Send a message to Claude. Routes to appropriate model based on tier.

        Tiers:
        - "fast": Haiku — JSON extraction, classification, simple tasks
        - "standard": Sonnet — conversation, analysis, drafting
        - "deep": Opus — research, decision briefs, complex reasoning
        """
        if not self.client:
            return "Brain not initialised. Set ANTHROPIC_API_KEY in .env"

        model = Config.get_model_for_tier(tier)
        system = system_override or MIRA_SYSTEM_PROMPT
        if context:
            system += f"\n\nAdditional context:\n{context}"

        messages = []
        if include_history:
            messages.extend(self.conversation_history[-self.max_history:])
        messages.append({"role": "user", "content": message})

        # ── Local model path ────────────────────────────────────
        if tier == "local" and self.local_client and self.local_client.is_available:
            if task_type in LOCAL_BLOCKED_TASKS:
                logger.info(f"[local->fast] {task_type} not eligible for local, escalating")
                tier = "fast"
                model = Config.get_model_for_tier("fast")
            else:
                try:
                    result = await self.local_client.chat(
                        messages=messages,
                        system=system_override or "You are a precise assistant. Return concise, structured responses.",
                        max_tokens=max_tokens or Config.LOCAL_MODEL_MAX_TOKENS,
                    )
                    reply = result["text"]

                    if self._local_quality_check_failed(reply, task_type):
                        logger.warning(f"[local->fast] Quality gate failed for {task_type}, escalating")
                        tier = "fast"
                        model = Config.get_model_for_tier("fast")
                    else:
                        input_tokens = result["input_tokens"]
                        output_tokens = result["output_tokens"]
                        logger.info(
                            f"[local] {task_type}: {Config.LOCAL_MODEL_NAME} | "
                            f"{input_tokens}in/{output_tokens}out | $0.0000"
                        )
                        if self.sqlite:
                            self.sqlite.log_api_usage(
                                model=Config.LOCAL_MODEL_NAME,
                                tier="local",
                                task_type=task_type,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                estimated_cost=0.0,
                            )
                        return reply
                except Exception as e:
                    logger.warning(f"[local->fast] Local model error: {e}, falling back to Haiku")
                    tier = "fast"
                    model = Config.get_model_for_tier("fast")

        elif tier == "local":
            logger.debug("Local model not available, falling back to fast tier")
            tier = "fast"
            model = Config.get_model_for_tier("fast")

        # ── Anthropic API path ──────────────────────────────────
        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens or Config.CLAUDE_MAX_TOKENS,
                system=system,
                messages=messages,
            )

            reply = response.content[0].text

            # Track costs
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = Config.estimate_cost(model, input_tokens, output_tokens)

            logger.info(
                f"[{tier}] {task_type}: {model} | "
                f"{input_tokens}in/{output_tokens}out | ${cost:.4f}"
            )

            # Log to database if available
            if self.sqlite:
                self.sqlite.log_api_usage(
                    model=model,
                    tier=tier,
                    task_type=task_type,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=cost,
                )

            # Update conversation history (only for standard/deep conversation)
            if include_history and task_type == "conversation":
                self.conversation_history.append({"role": "user", "content": message})
                self.conversation_history.append({"role": "assistant", "content": reply})

                if len(self.conversation_history) > self.max_history * 2:
                    self.conversation_history = self.conversation_history[-self.max_history * 2:]

            return reply

        except anthropic.APIError as e:
            logger.error(f"Claude API error ({tier}/{model}): {e}")
            return f"API error: {e}"
        except Exception as e:
            logger.error(f"Brain error: {e}")
            return f"Error: {e}"

    # ── Fast Tier (Haiku) — cheap structured tasks ───────────────────

    async def extract_entities(self, text: str) -> dict:
        """Extract people, places, decisions, emotions, topics from text.
        Uses HAIKU — structured JSON extraction doesn't need a big model.
        """
        prompt = f"""Extract structured information from this text. Return ONLY valid JSON with these fields:
- people: list of names mentioned
- places: list of locations mentioned
- decisions: list of any decisions mentioned or implied
- emotions: list of emotions expressed
- topics: list of key topics/themes
- action_items: list of any action items or commitments
- importance: 1-5 rating of how important this content is
- category: one of [personal, work, trading, health, social, learning, general]

Text: {text}"""

        response = await self.think(
            message=prompt,
            include_history=False,
            system_override="You are a precise entity extraction system. Return ONLY valid JSON, no other text.",
            max_tokens=1024,
            tier="local",
            task_type="entity_extraction",
        )

        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse entity extraction: {response[:200]}")
            return {
                "people": [], "places": [], "decisions": [], "emotions": [],
                "topics": [], "action_items": [], "importance": 3, "category": "general",
            }

    async def evaluate_email(self, email_data: dict) -> dict:
        """Score an email for urgency and importance.
        Uses HAIKU — simple classification + JSON output.
        """
        prompt = f"""Evaluate this email. Return ONLY valid JSON.

From: {email_data.get('from', 'unknown')}
Subject: {email_data.get('subject', '')}
Body preview: {email_data.get('body', '')[:500]}

Return JSON with:
- urgency: 1-5 (5 = needs immediate attention)
- importance: 1-5 (5 = critical to user's work/life)
- category: one of [work_boldr, personal, trading, newsletter, marketing, spam]
- summary: one-sentence summary
- suggested_action: one of [reply_now, reply_today, review_later, archive, ignore]
- draft_needed: true/false"""

        response = await self.think(
            message=prompt,
            include_history=False,
            system_override="You are an email triage system. Return ONLY valid JSON.",
            max_tokens=512,
            tier="fast",
            task_type="email_triage",
        )

        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "urgency": 3, "importance": 3, "category": "general",
                "summary": "Could not evaluate", "suggested_action": "review_later",
                "draft_needed": False,
            }

    # ── Standard Tier (Sonnet) — balanced tasks ──────────────────────

    async def analyse(self, content: str, task: str) -> str:
        """Analyse content for a specific task. Uses SONNET."""
        return await self.think(
            message=f"Task: {task}\n\nContent:\n{content}",
            include_history=False,
            max_tokens=2048,
            tier="standard",
            task_type="analysis",
        )

    async def draft_reply(
        self,
        original_message: str,
        sender: str,
        context: str = None,
        tone: str = "natural",
    ) -> str:
        """Draft a reply in the user's voice. Uses SONNET — needs personality."""
        prompt = f"""Draft a reply to this message as if you ARE the user (not as an AI assistant).
Write in their natural voice — direct, authentic, not corporate.

From: {sender}
Message: {original_message}

{"Context: " + context if context else ""}
Tone: {tone}

Write ONLY the reply text, nothing else."""

        return await self.think(
            message=prompt,
            include_history=False,
            max_tokens=1024,
            tier="standard",
            task_type="draft_reply",
        )

    async def generate_briefing(self, data: dict) -> str:
        """Generate the daily morning briefing. Uses SONNET."""
        prompt = f"""Generate Mira's daily morning briefing. Be conversational but structured.
Not a bullet list — a coherent briefing like a trusted advisor would deliver.

Data to include:
{json.dumps(data, indent=2, default=str)}

Format:
1. Open with a brief, human greeting appropriate to the time and day
2. Overnight trading/crypto highlights (if any)
3. Today's calendar with prep notes
4. Priority emails needing attention
5. Important news relevant to their world
6. One insight from memory patterns
7. Mira's plan for the day

Keep it concise but warm. You're a trusted partner, not a report generator."""

        return await self.think(
            message=prompt,
            include_history=False,
            max_tokens=2048,
            tier="standard",
            task_type="daily_briefing",
        )

    # ── Deep Tier (Opus) — complex reasoning ─────────────────────────

    async def deep_research(self, topic: str, context: str = None) -> str:
        """Deep research on a topic. Uses OPUS — needs best reasoning."""
        prompt = (
            f"Research the following topic thoroughly. Provide a comprehensive briefing with "
            f"key facts, current state, multiple perspectives, and actionable insights.\n\n"
            f"Topic: {topic}"
        )
        if context:
            prompt += f"\n\nAdditional context: {context}"

        return await self.think(
            message=prompt,
            include_history=False,
            max_tokens=4096,
            tier="deep",
            task_type="deep_research",
        )

    async def generate_decision_brief(self, decision: str, context: str = None) -> str:
        """Generate a structured decision brief. Uses OPUS — high stakes."""
        prompt = f"""Prepare a structured decision brief.

Decision: {decision}
{"Context: " + context if context else ""}

Follow this structure:
1. Pull all relevant facts
2. Research external context (market conditions, comparable decisions)
3. Model 3 scenarios: optimistic, realistic, pessimistic
4. Identify decision-making blind spots
5. Play devil's advocate — argue the opposite position
6. Present structured brief with recommendation

Be thorough. This is a real decision with real consequences."""

        return await self.think(
            message=prompt,
            include_history=False,
            max_tokens=4096,
            tier="deep",
            task_type="decision_brief",
        )

    async def analyse_polymarket(self, market_data: dict) -> dict:
        """Analyse a prediction market for mispriced probabilities. Uses OPUS."""
        prompt = f"""Analyse this prediction market for potential mispricing.

Market data:
{json.dumps(market_data, indent=2, default=str)}

Consider:
1. Current probability vs your assessment of true probability
2. What information the market may not have priced in yet
3. Key risks and unknowns
4. Recommended position (if any) with sizing rationale
5. Confidence level (1-10)

Return analysis with a clear recommendation."""

        response = await self.think(
            message=prompt,
            include_history=False,
            max_tokens=2048,
            tier="deep",
            task_type="polymarket_analysis",
        )
        return {"analysis": response, "model_used": "opus"}

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history.clear()
