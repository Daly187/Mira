"""
Mira Orchestrator — Multi-agent task decomposition and execution.

Spawns specialised sub-agents (Research, Writing, Review, Execution, Monitor)
that each wrap a brain.think() call with role-specific system prompts.
The orchestrator classifies incoming tasks, decides which agents to involve,
runs them in sequence or parallel, and optionally has the Review agent
quality-check output before delivery.

Spec reference: section 12.4 — multi-agent orchestration layer.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from brain import MiraBrain
from memory.sqlite_store import SQLiteStore

logger = logging.getLogger("mira.orchestrator")


# ── Agent Roles ──────────────────────────────────────────────────────────────

class AgentRole(str, Enum):
    """Specialised sub-agent types that the orchestrator can spawn."""

    RESEARCH = "research"
    WRITING = "writing"
    REVIEW = "review"
    EXECUTION = "execution"
    MONITOR = "monitor"


# ── Role Configuration ───────────────────────────────────────────────────────

@dataclass
class AgentSpec:
    """Specification for a specialised sub-agent."""

    name: str
    role: AgentRole
    tier: str
    system_prompt: str
    description: str
    max_tokens: int = 4096


AGENT_SPECS: dict[AgentRole, AgentSpec] = {
    AgentRole.RESEARCH: AgentSpec(
        name="ResearchAgent",
        role=AgentRole.RESEARCH,
        tier="deep",
        max_tokens=4096,
        description="Deep web search, synthesis, and comprehensive analysis on complex topics.",
        system_prompt=(
            "You are Mira's Research Agent — part of an autonomous digital twin system. "
            "Your job is deep research and synthesis.\n\n"
            "Guidelines:\n"
            "- Be comprehensive but concise. Surface non-obvious insights.\n"
            "- Separate facts from speculation. Cite reasoning.\n"
            "- Structure output with clear sections: Key Findings, Analysis, "
            "Implications, Unknowns/Risks.\n"
            "- If the topic involves markets or trading, include quantitative data "
            "where available.\n"
            "- Write for a sharp reader — no filler, no hedging.\n"
            "- Consider multiple perspectives before settling on conclusions.\n"
            "- Flag confidence levels for key claims."
        ),
    ),
    AgentRole.WRITING: AgentSpec(
        name="WritingAgent",
        role=AgentRole.WRITING,
        tier="standard",
        max_tokens=4096,
        description="Long-form content creation in the user's authentic voice.",
        system_prompt=(
            "You are Mira's Writing Agent — part of an autonomous digital twin system. "
            "You produce content that sounds exactly like the user.\n\n"
            "The user's voice:\n"
            "- Direct, no corporate fluff. Gets to the point.\n"
            "- Conversational but smart. Uses analogies from trading, tech, and operations.\n"
            "- Authentic — never performative or trying too hard.\n"
            "- South African background, Manila-based. Occasionally uses SA slang naturally.\n"
            "- Opinionated but backs it up with reasoning.\n\n"
            "Guidelines:\n"
            "- Match the tone to the platform (LinkedIn vs Twitter vs email vs report).\n"
            "- Write as the user, not about the user.\n"
            "- If given research context from a prior agent, weave it in naturally.\n"
            "- Keep the energy — don't flatten their personality.\n"
            "- Produce ready-to-send output that only needs a quick scan."
        ),
    ),
    AgentRole.REVIEW: AgentSpec(
        name="ReviewAgent",
        role=AgentRole.REVIEW,
        tier="standard",
        max_tokens=2048,
        description="Quality-checks output before delivery. Catches errors, tone issues, and gaps.",
        system_prompt=(
            "You are Mira's Review Agent — part of an autonomous digital twin system. "
            "Your role is quality control before output reaches the user.\n\n"
            "Review criteria:\n"
            "1. ACCURACY — Are facts correct? Any unsupported claims?\n"
            "2. VOICE — Does it sound like the user? Flag anything robotic or generic.\n"
            "3. COMPLETENESS — Does it fully address the original task?\n"
            "4. CONCISENESS — Cut anything that doesn't earn its place.\n"
            "5. ACTIONABILITY — Is the output useful? Can the user act on it?\n\n"
            "Return ONLY valid JSON with these keys:\n"
            "- verdict: one of PASS, NEEDS_REVISION, FAIL\n"
            "- issues: list of strings describing problems (empty list if PASS)\n"
            "- revised: the corrected version if NEEDS_REVISION, otherwise null\n"
            "- notes: brief reviewer notes"
        ),
    ),
    AgentRole.EXECUTION: AgentSpec(
        name="ExecutionAgent",
        role=AgentRole.EXECUTION,
        tier="standard",
        max_tokens=2048,
        description="Computer use actions — navigating UIs, filling forms, clicking buttons.",
        system_prompt=(
            "You are Mira's Execution Agent — part of an autonomous digital twin system. "
            "You translate high-level tasks into concrete computer-use action plans.\n\n"
            "Guidelines:\n"
            "- Break the task into specific, sequential steps.\n"
            "- Each step should be a single action: open app, click button, "
            "type text, navigate URL, etc.\n"
            "- Be precise about what to click, where to navigate, what to type.\n"
            "- Include verification steps (e.g. 'confirm the page loaded').\n"
            "- If a step could fail, include a fallback.\n\n"
            "Return ONLY valid JSON: an array of step objects, each with:\n"
            "- step_number (int)\n"
            "- action: one of [open_url, click, type, hotkey, scroll, wait, verify]\n"
            "- target: what to interact with\n"
            "- value: text to type or URL to open (optional)\n"
            "- fallback: what to do if step fails (optional)\n"
            "- description: human-readable description"
        ),
    ),
    AgentRole.MONITOR: AgentSpec(
        name="MonitorAgent",
        role=AgentRole.MONITOR,
        tier="fast",
        max_tokens=1024,
        description="Watches for events, conditions, and triggers. Lightweight and efficient.",
        system_prompt=(
            "You are Mira's Monitor Agent — part of an autonomous digital twin system. "
            "You evaluate conditions and detect events.\n\n"
            "Guidelines:\n"
            "- Be precise and binary where possible: condition met or not met.\n"
            "- Extract the relevant metric and compare against the threshold.\n"
            "- Surface anomalies — anything that deviates from expected patterns.\n"
            "- Keep responses short and structured.\n\n"
            "Return ONLY valid JSON with these keys:\n"
            "- triggered (bool): whether the monitored condition was met\n"
            "- current_value: the current state/value observed\n"
            "- threshold: what was being watched for\n"
            "- details: brief explanation\n"
            "- recommended_action: what should happen next"
        ),
    ),
}


# ── Sub-Agent ────────────────────────────────────────────────────────────────

class SubAgent:
    """A specialised agent that wraps brain.think() with a role-specific system prompt.

    Each SubAgent is a single-purpose worker: it receives a task, calls the brain
    with its role's system prompt and tier, logs the action, and returns the result.
    """

    def __init__(
        self,
        role: AgentRole,
        brain: MiraBrain,
        sqlite: SQLiteStore,
        run_id: str,
    ):
        self.role = role
        self.brain = brain
        self.sqlite = sqlite
        self.run_id = run_id
        self.spec = AGENT_SPECS[role]

    async def execute(
        self,
        task: str,
        context: str = None,
        tier_override: str = None,
        max_tokens_override: int = None,
    ) -> dict:
        """Run this sub-agent on a task.

        Args:
            task: The task description / prompt for this agent.
            context: Output from prior agents in the pipeline, injected as context.
            tier_override: Override the default model tier for this role.
            max_tokens_override: Override the default max tokens.

        Returns:
            dict with keys: role, agent_name, status, output, duration_ms
        """
        start = datetime.now()
        tier = tier_override or self.spec.tier
        max_tokens = max_tokens_override or self.spec.max_tokens

        # Build the full prompt with optional context from prior agents
        prompt = f"TASK:\n{task}"
        if context:
            prompt = f"CONTEXT FROM PRIOR AGENTS:\n{context}\n\n{prompt}"

        if self.sqlite:
            self.sqlite.log_action(
                module="orchestrator",
                action=f"subagent_{self.role.value}_start",
                outcome="running",
                details={
                    "run_id": self.run_id,
                    "agent": self.spec.name,
                    "task_preview": task[:300],
                    "tier": tier,
                },
            )

        try:
            output = await self.brain.think(
                message=prompt,
                system_override=self.spec.system_prompt,
                include_history=False,
                max_tokens=max_tokens,
                tier=tier,
                task_type=f"orchestrator_{self.role.value}",
            )

            duration_ms = int((datetime.now() - start).total_seconds() * 1000)

            if self.sqlite:
                self.sqlite.log_action(
                    module="orchestrator",
                    action=f"subagent_{self.role.value}_done",
                    outcome="success",
                    details={
                        "run_id": self.run_id,
                        "agent": self.spec.name,
                        "duration_ms": duration_ms,
                        "output_length": len(output),
                    },
                )

            logger.info(
                f"[{self.run_id}] {self.spec.name} completed in {duration_ms}ms "
                f"({len(output)} chars)"
            )

            return {
                "role": self.role.value,
                "agent_name": self.spec.name,
                "status": "success",
                "output": output,
                "duration_ms": duration_ms,
            }

        except Exception as e:
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            error_msg = str(e)
            logger.error(f"[{self.run_id}] {self.spec.name} failed: {error_msg}")

            if self.sqlite:
                self.sqlite.log_action(
                    module="orchestrator",
                    action=f"subagent_{self.role.value}_error",
                    outcome="error",
                    details={
                        "run_id": self.run_id,
                        "agent": self.spec.name,
                        "error": error_msg[:500],
                        "duration_ms": duration_ms,
                    },
                )

            return {
                "role": self.role.value,
                "agent_name": self.spec.name,
                "status": "error",
                "output": error_msg,
                "duration_ms": duration_ms,
            }


# ── Task Classification Prompt ───────────────────────────────────────────────

CLASSIFICATION_PROMPT = """Classify this task and determine which specialised agents are needed and in what order.

Available agents:
- research: Deep research, data gathering, synthesis of information
- writing: Long-form content generation (emails, posts, reports, summaries)
- review: Quality-check output before delivery (used after writing or research)
- execution: Computer use tasks (opening apps, clicking, typing, navigating websites)
- monitor: Checking conditions, watching for events, evaluating thresholds

Task:
{task}

Return ONLY valid JSON with these fields:
- agents: ordered list of agent roles to invoke (e.g. ["research", "writing", "review"])
- parallel_groups: list of lists grouping agents that can run simultaneously.
  Groups execute sequentially; agents within a group run in parallel.
  Common patterns:
    Research then write then review: [["research"], ["writing"], ["review"]]
    Just research with review: [["research"], ["review"]]
    Just writing with review: [["writing"], ["review"]]
    Pure execution: [["execution"]]
    Monitor only: [["monitor"]]
    Research + monitor in parallel, then writing: [["research", "monitor"], ["writing"]]
- needs_review: boolean — whether the Review agent should check the final output
- complexity: "low", "medium", or "high"
- summary: one-sentence description of the execution plan"""


# ── Orchestrator ─────────────────────────────────────────────────────────────

class Orchestrator:
    """Multi-agent orchestration layer.

    Takes a task description, uses the brain to classify it, spawns the right
    sub-agents in the right order, collects results, and optionally quality-checks
    the output with the Review agent.

    Usage:
        orchestrator = Orchestrator(brain, sqlite)
        result = await orchestrator.run("Write a market analysis on BTC/USD")
    """

    def __init__(
        self,
        brain: MiraBrain,
        sqlite: SQLiteStore,
        vector_store=None,
        knowledge_graph=None,
    ):
        self.brain = brain
        self.sqlite = sqlite
        self.vector = vector_store
        self.graph = knowledge_graph

    # ── Core Pipeline ────────────────────────────────────────────────────

    async def run(
        self,
        task: str,
        force_agents: list[str] = None,
        skip_review: bool = False,
        context: str = None,
    ) -> dict:
        """Run a multi-agent task pipeline.

        Args:
            task: Natural language task description.
            force_agents: Override auto-classification with specific agent roles.
                          e.g. ["research", "writing", "review"]
            skip_review: If True, skip the review agent even if classification
                         says to use it.
            context: Additional context to pass to the first agent group.

        Returns:
            dict with keys: run_id, task, plan, results, final_output, review,
                            status, duration_ms
        """
        run_id = uuid.uuid4().hex[:12]
        start = datetime.now()

        logger.info(f"[{run_id}] Orchestrator starting: {task[:120]}")
        if self.sqlite:
            self.sqlite.log_action(
                module="orchestrator",
                action="run_start",
                outcome="running",
                details={"run_id": run_id, "task": task[:500]},
            )

        # Step 1: Classify the task (or use forced agent list)
        if force_agents:
            valid_roles = {r.value for r in AgentRole}
            agents = [a for a in force_agents if a in valid_roles]
            plan = {
                "agents": agents,
                "parallel_groups": [[a] for a in agents],
                "needs_review": "review" in agents,
                "complexity": "medium",
                "summary": f"Forced pipeline: {' -> '.join(agents)}",
            }
        else:
            plan = await self._classify_task(task)

        logger.info(f"[{run_id}] Plan: {plan.get('summary', 'n/a')}")

        # Step 2: Gather memory context for the first group
        memory_context = await self._gather_context(task)
        initial_context = "\n\n".join(
            part for part in [memory_context, context] if part
        ) or None

        # Step 3: Execute agent groups — sequential groups, parallel within each
        all_results = []
        accumulated_context = initial_context or ""

        for group_idx, group in enumerate(plan.get("parallel_groups", [])):
            # Pull review agents out of regular groups — review runs at the end
            exec_roles = [r for r in group if r != AgentRole.REVIEW.value]
            if not exec_roles:
                continue

            logger.info(f"[{run_id}] Group {group_idx + 1}: {exec_roles}")

            # Create sub-agents for this group
            sub_agents = [
                SubAgent(
                    role=AgentRole(role_name),
                    brain=self.brain,
                    sqlite=self.sqlite,
                    run_id=run_id,
                )
                for role_name in exec_roles
            ]

            # Run in parallel within the group
            if len(sub_agents) == 1:
                group_results = [
                    await sub_agents[0].execute(task, context=accumulated_context)
                ]
            else:
                coros = [
                    agent.execute(task, context=accumulated_context)
                    for agent in sub_agents
                ]
                group_results = list(await asyncio.gather(*coros))

            all_results.extend(group_results)

            # Accumulate successful output as context for the next group
            successful = [r for r in group_results if r["status"] == "success"]
            if successful:
                accumulated_context = "\n\n".join(
                    f"--- {r['role'].upper()} AGENT OUTPUT ---\n{r['output']}"
                    for r in successful
                )

        # Step 4: Determine the final output (last successful non-review result)
        successful_results = [r for r in all_results if r["status"] == "success"]
        final_output = successful_results[-1]["output"] if successful_results else ""

        # Step 5: Review pass (if configured and there is output to review)
        review_result = None
        if plan.get("needs_review") and not skip_review and final_output:
            review_result = await self._run_review(task, final_output, run_id)

            # Apply revisions if the reviewer provided them
            if review_result and review_result.get("status") == "success":
                parsed = self._parse_review_json(review_result["output"])
                review_result["parsed"] = parsed

                if parsed["verdict"] == "NEEDS_REVISION" and parsed.get("revised"):
                    final_output = parsed["revised"]
                    logger.info(f"[{run_id}] Review agent revised the output")
                elif parsed["verdict"] == "FAIL":
                    logger.warning(
                        f"[{run_id}] Review FAILED: {parsed.get('issues')}"
                    )

        # Step 6: Wrap up
        duration_ms = int((datetime.now() - start).total_seconds() * 1000)
        status = "success" if final_output else "no_output"

        if self.sqlite:
            self.sqlite.log_action(
                module="orchestrator",
                action="run_complete",
                outcome=status,
                details={
                    "run_id": run_id,
                    "agents_used": [r["role"] for r in all_results],
                    "duration_ms": duration_ms,
                    "output_length": len(final_output),
                    "review_verdict": (
                        review_result.get("parsed", {}).get("verdict")
                        if review_result
                        else None
                    ),
                },
            )

        logger.info(
            f"[{run_id}] Complete — {status} | "
            f"{len(all_results)} agents | {duration_ms}ms"
        )

        return {
            "run_id": run_id,
            "task": task,
            "plan": plan,
            "results": all_results,
            "final_output": final_output,
            "review": review_result,
            "status": status,
            "duration_ms": duration_ms,
        }

    # ── Task Classification ──────────────────────────────────────────────

    async def _classify_task(self, task: str) -> dict:
        """Use the brain (fast tier) to classify a task and build the agent pipeline."""
        prompt = CLASSIFICATION_PROMPT.format(task=task)

        response = await self.brain.think(
            message=prompt,
            system_override=(
                "You are a task classification system for Mira's multi-agent orchestrator. "
                "Return ONLY valid JSON. No explanation, no markdown fences."
            ),
            include_history=False,
            max_tokens=512,
            tier="fast",
            task_type="orchestrator_classify",
        )

        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]
            plan = json.loads(cleaned)

            # Validate agent roles against the enum
            valid_roles = {r.value for r in AgentRole}
            plan["agents"] = [a for a in plan.get("agents", []) if a in valid_roles]
            plan["parallel_groups"] = [
                [a for a in group if a in valid_roles]
                for group in plan.get("parallel_groups", [])
            ]
            plan["parallel_groups"] = [g for g in plan["parallel_groups"] if g]

            # Fallback: if parallel_groups is empty but agents is not, run sequentially
            if not plan["parallel_groups"] and plan["agents"]:
                plan["parallel_groups"] = [[a] for a in plan["agents"]]

            return plan

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(
                f"Classification parse failed ({e}). "
                f"Falling back to research + review."
            )
            return {
                "agents": ["research", "review"],
                "parallel_groups": [["research"], ["review"]],
                "needs_review": True,
                "complexity": "medium",
                "summary": "Fallback — research with review",
            }

    # ── Simple Classification (single agent) ─────────────────────────────

    async def classify_task_simple(self, task: str) -> str:
        """Classify a task to a single agent type. Returns role name string.

        Useful for quick dispatch when you just need one agent, not a full pipeline.
        """
        prompt = (
            "Classify this task into exactly ONE agent type. "
            "Return ONLY the type name, nothing else.\n\n"
            "Types: research, writing, review, execution, monitor\n\n"
            f"Task: {task}\n\nAgent type:"
        )

        result = await self.brain.think(
            message=prompt,
            include_history=False,
            system_override="Return ONLY the agent type name. No explanation.",
            max_tokens=32,
            tier="fast",
            task_type="orchestrator_classify_simple",
        )

        agent_type = result.strip().lower().rstrip(".")
        valid_roles = {r.value for r in AgentRole}
        if agent_type not in valid_roles:
            logger.warning(
                f"Unknown agent type '{agent_type}' — defaulting to research"
            )
            agent_type = "research"

        return agent_type

    # ── Single Agent Dispatch ────────────────────────────────────────────

    async def dispatch(
        self,
        task: str,
        agent_type: str = None,
        context: str = None,
    ) -> dict:
        """Dispatch a task to a single specialised agent.

        If agent_type is not specified, classifies the task first.
        Returns the SubAgent result dict.
        """
        if agent_type is None:
            agent_type = await self.classify_task_simple(task)

        run_id = uuid.uuid4().hex[:8]

        # Gather memory context
        memory_ctx = await self._gather_context(task)
        full_context = "\n\n".join(
            part for part in [memory_ctx, context] if part
        ) or None

        agent = SubAgent(
            role=AgentRole(agent_type),
            brain=self.brain,
            sqlite=self.sqlite,
            run_id=run_id,
        )

        return await agent.execute(task, context=full_context)

    # ── Parallel Dispatch ────────────────────────────────────────────────

    async def run_parallel(self, tasks: list[dict]) -> list[dict]:
        """Run multiple independent agent tasks concurrently.

        Each task dict should have:
        - description (str, required): the task prompt
        - agent_type (str, optional): role name; auto-classified if missing

        Returns list of SubAgent result dicts in the same order as input.
        """
        logger.info(f"Running {len(tasks)} tasks in parallel")

        async def _run_one(task_dict: dict) -> dict:
            try:
                return await self.dispatch(
                    task=task_dict["description"],
                    agent_type=task_dict.get("agent_type"),
                )
            except Exception as e:
                logger.error(f"Parallel task failed: {e}")
                return {
                    "role": task_dict.get("agent_type", "unknown"),
                    "agent_name": "error",
                    "status": "error",
                    "output": str(e),
                    "duration_ms": 0,
                }

        results = list(await asyncio.gather(*[_run_one(t) for t in tasks]))

        if self.sqlite:
            self.sqlite.log_action(
                "orchestrator",
                "run_parallel",
                f"completed {len(results)} tasks",
                {"task_count": len(tasks)},
            )

        return results

    # ── Review Helpers ───────────────────────────────────────────────────

    async def _run_review(
        self, original_task: str, content: str, run_id: str
    ) -> dict:
        """Run the Review agent on final output."""
        review_agent = SubAgent(
            role=AgentRole.REVIEW,
            brain=self.brain,
            sqlite=self.sqlite,
            run_id=run_id,
        )

        review_task = (
            f"Review the following output for quality before delivery.\n\n"
            f"ORIGINAL TASK:\n{original_task}\n\n"
            f"OUTPUT TO REVIEW:\n{content}"
        )

        return await review_agent.execute(review_task)

    def _parse_review_json(self, review_output: str) -> dict:
        """Parse the Review agent's structured JSON response."""
        try:
            cleaned = review_output.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]
            parsed = json.loads(cleaned)
            return {
                "verdict": str(parsed.get("verdict", "PASS")).upper(),
                "issues": parsed.get("issues", []),
                "revised": parsed.get("revised"),
                "notes": parsed.get("notes", ""),
            }
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Review output was not valid JSON — treating as PASS")
            return {
                "verdict": "PASS",
                "issues": [],
                "revised": None,
                "notes": review_output[:500],
            }

    # ── Memory Context ───────────────────────────────────────────────────

    async def _gather_context(self, task: str) -> Optional[str]:
        """Pull relevant context from memory systems for agent grounding."""
        context_parts = []

        # Semantic search in vector store
        if self.vector:
            try:
                results = self.vector.search(task, n_results=5)
                if results:
                    context_parts.append("Relevant memories:")
                    for r in results:
                        text = r.get("text", r.get("document", ""))
                        if text:
                            context_parts.append(f"  - {text[:200]}")
            except Exception as e:
                logger.debug(f"Vector context search failed: {e}")

        # Knowledge graph relations
        if self.graph:
            try:
                related = self.graph.search_nodes(task[:100], limit=3)
                if related:
                    context_parts.append("Related knowledge:")
                    for node in related:
                        label = node.get("label", node.get("name", ""))
                        ntype = node.get("type", "unknown")
                        if label:
                            context_parts.append(f"  - [{ntype}] {label}")
            except Exception as e:
                logger.debug(f"Graph context search failed: {e}")

        return "\n".join(context_parts) if context_parts else None

    # ── Convenience Methods ──────────────────────────────────────────────

    async def research(self, topic: str, context: str = None) -> dict:
        """Shortcut: Research agent with review."""
        return await self.run(
            task=topic,
            force_agents=["research", "review"],
            context=context,
        )

    async def write(self, brief: str, research_context: str = None) -> dict:
        """Shortcut: Writing agent with review. Optionally feed in prior research."""
        return await self.run(
            task=brief,
            force_agents=["writing", "review"],
            context=research_context,
        )

    async def research_and_write(self, task: str) -> dict:
        """Shortcut: Full pipeline — research, then write, then review."""
        return await self.run(
            task=task,
            force_agents=["research", "writing", "review"],
        )

    async def execute_on_computer(self, task: str) -> dict:
        """Shortcut: Execution agent to plan computer-use steps (no review)."""
        return await self.run(
            task=task,
            force_agents=["execution"],
            skip_review=True,
        )

    async def monitor_condition(
        self, condition: str, data: str = None
    ) -> dict:
        """Shortcut: Monitor agent to evaluate a condition against data.

        Args:
            condition: What to watch for (e.g. "BTC price above 100k").
            data: Current data to evaluate against the condition.
        """
        task = f"Evaluate this condition: {condition}"
        return await self.run(
            task=task,
            force_agents=["monitor"],
            skip_review=True,
            context=f"Current data:\n{data}" if data else None,
        )

    async def write_and_review(self, writing_task: str) -> dict:
        """Shortcut: Write content with Sonnet, then review."""
        return await self.run(
            task=writing_task,
            force_agents=["writing", "review"],
        )

    async def research_and_review(self, topic: str) -> dict:
        """Shortcut: Research a topic with Opus, then review."""
        return await self.run(
            task=topic,
            force_agents=["research", "review"],
        )
