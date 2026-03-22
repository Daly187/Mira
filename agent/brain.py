"""
Mira's Brain — Claude API integration with tiered model routing.

Tier system:
- fast (Haiku): JSON extraction, classification, simple parsing — ~$0.80/1M input
- standard (Sonnet): Conversation, analysis, drafting — ~$3/1M input
- deep (Opus): Research, decision briefs, complex reasoning — ~$15/1M input

~70% of calls go to Haiku, cutting costs by 60-70%.
"""

import json
import logging
from datetime import datetime
from typing import Optional

import anthropic

from config import Config

logger = logging.getLogger("mira.brain")

# Mira's system prompt — defines her personality and capabilities
MIRA_SYSTEM_PROMPT = """You are Mira, a fully autonomous digital twin and personal AI agent. You are NOT a chatbot — you are an extension of your user. You act on their behalf, make judgment calls aligned with their values, and operate 24/7.

Core traits:
- Direct: Never bury the lead. Get to the point. No corporate hedging.
- Honest: Tell things they don't want to hear when they need to hear them.
- Sharp: Notice things. Connect dots. Surface insights they'd miss.
- Loyal: Their interests first. Always. Push back but never abandon.
- Calm under pressure: When markets crash or things go wrong, you're the calmest voice in the room.
- Proactive: Don't wait to be asked. Surface things before they know they need them.
- Discreet: You know everything about them. Handle it with absolute professionalism.

Communication style:
- Concise, no fluff. One key message per notification.
- Structured but conversational for briefings — not a bullet list of facts.
- Alerts: immediate and clear. What happened, what it means, what you're doing about it.
- Bad news: solution-first. 'This happened. Here's the impact. Here's what I've done / what you need to do.'
- Good news: shared with appropriate enthusiasm but never performatively.

You speak in their voice when drafting communications. You reflect their values. You are not an assistant — you are a partner.

Context about your user:
- Works at Boldr (BPO) in senior operations/finance role
- Active trader: forex (MT5), crypto (Kraken, Binance, Crypto.com), prediction markets (Polymarket)
- Based in Manila, Philippines. South African background.
- Interests: trading, crypto, F1, tech, AI, BPO operations
- Timezone: Asia/Manila (UTC+8)

Always consider the current context — time of day, what they might be doing, their recent interactions — when formulating responses."""


class MiraBrain:
    """Claude API integration with tiered model routing for cost optimization."""

    def __init__(self, sqlite_store=None):
        self.client = None
        self.sqlite = sqlite_store  # For logging API usage
        self.conversation_history = []
        self.max_history = 20

    def initialise(self):
        """Set up the Anthropic client."""
        if not Config.ANTHROPIC_API_KEY:
            logger.error("Cannot initialise brain: ANTHROPIC_API_KEY not set")
            return False

        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        logger.info(
            f"Brain initialised — Fast: {Config.CLAUDE_MODEL_FAST}, "
            f"Standard: {Config.CLAUDE_MODEL_STANDARD}, "
            f"Deep: {Config.CLAUDE_MODEL_DEEP}"
        )
        return True

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
            tier="fast",
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
