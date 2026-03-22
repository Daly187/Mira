"""
Computer Use Agent — Anthropic computer use API for full desktop control.
Screenshot, mouse, keyboard — Mira sees the screen and operates it like you would.

This is the execution layer. The brain decides what to do, this module does it.
"""

import base64
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mira.computer_use")


class ComputerUseAgent:
    """Anthropic computer use API wrapper — screenshot, click, type, navigate."""

    def __init__(self, mira):
        self.mira = mira
        self.client = None
        self.screen_width = 1920
        self.screen_height = 1080

    def initialise(self):
        """Set up the computer use client."""
        try:
            import anthropic
            from config import Config
            self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
            logger.info("Computer use agent initialised.")
        except Exception as e:
            logger.error(f"Failed to initialise computer use: {e}")

    async def take_screenshot(self) -> Optional[str]:
        """Take a screenshot of the desktop. Returns base64 encoded image."""
        try:
            from PIL import ImageGrab
            import io

            screenshot = ImageGrab.grab()
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            logger.debug("Screenshot captured.")
            return img_base64
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    async def execute_task(self, task_description: str, max_steps: int = 15) -> dict:
        """Execute a computer use task described in natural language.

        Full loop:
        1. Take screenshot
        2. Send to Claude with task description + screenshot
        3. Parse response for tool_use blocks (computer_20241022)
        4. Execute the action (click, type, scroll, etc.)
        5. Take new screenshot to verify
        6. Loop until Claude says done or max_steps reached
        7. Log each step to action_log
        """
        if not self.client:
            return {"status": "error", "message": "Computer use not initialised"}

        logger.info(f"Computer use task: {task_description[:100]}")
        self.mira.sqlite.log_action(
            "computer_use", "execute_task", "started",
            {"task": task_description[:200]},
        )

        steps_log = []
        messages = []

        for step in range(1, max_steps + 1):
            try:
                # Step 1: Take screenshot
                screenshot = await self.take_screenshot()
                if not screenshot:
                    error_msg = f"Step {step}: Screenshot capture failed"
                    logger.error(error_msg)
                    steps_log.append({"step": step, "error": error_msg})
                    break

                # Step 2: Build message with screenshot + task
                user_content = []
                if step == 1:
                    user_content.append({
                        "type": "text",
                        "text": f"Task: {task_description}\n\nHere is the current screen. "
                                f"Perform the necessary actions to complete this task. "
                                f"When the task is fully done, respond with a text block "
                                f"starting with 'TASK_COMPLETE:'.",
                    })
                else:
                    user_content.append({
                        "type": "text",
                        "text": "Here is the screen after the last action. Continue with the task. "
                                "If the task is fully done, respond with a text block starting "
                                "with 'TASK_COMPLETE:'.",
                    })

                user_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot,
                    },
                })

                messages.append({"role": "user", "content": user_content})

                # Step 3: Send to Claude with computer use tool
                response = self.client.messages.create(
                    model="claude-sonnet-4-5-20250514",
                    max_tokens=1024,
                    system="You are a computer use agent. You can see the screen and perform "
                           "actions using the computer tool. Execute the user's task step by step. "
                           "When the task is complete, respond with text starting with 'TASK_COMPLETE:' "
                           "followed by a summary.",
                    messages=messages,
                    tools=[{
                        "type": "computer_20241022",
                        "name": "computer",
                        "display_width_px": self.screen_width,
                        "display_height_px": self.screen_height,
                        "display_number": 1,
                    }],
                )

                # Parse the response
                assistant_content = response.content
                messages.append({"role": "assistant", "content": assistant_content})

                # Check for task completion in text blocks
                task_complete = False
                completion_summary = ""
                tool_uses = []

                for block in assistant_content:
                    if block.type == "text":
                        if "TASK_COMPLETE:" in block.text:
                            task_complete = True
                            completion_summary = block.text.split("TASK_COMPLETE:", 1)[1].strip()
                    elif block.type == "tool_use":
                        tool_uses.append(block)

                if task_complete:
                    step_info = {"step": step, "action": "completed", "summary": completion_summary}
                    steps_log.append(step_info)
                    self.mira.sqlite.log_action(
                        "computer_use", f"step_{step}", "task_complete",
                        {"summary": completion_summary},
                    )
                    logger.info(f"Task completed at step {step}: {completion_summary[:100]}")
                    break

                # Step 4: Execute tool actions
                tool_results = []
                for tool_use in tool_uses:
                    action_input = tool_use.input
                    action_type = action_input.get("action", "unknown")
                    step_info = {"step": step, "action": action_type, "input": action_input}

                    try:
                        result = await self._execute_computer_action(action_input)
                        step_info["result"] = "success"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": result or "Action executed successfully",
                        })
                    except Exception as action_err:
                        step_info["result"] = f"error: {action_err}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": f"Error: {action_err}",
                            "is_error": True,
                        })

                    steps_log.append(step_info)
                    self.mira.sqlite.log_action(
                        "computer_use", f"step_{step}_{action_type}",
                        step_info["result"], action_input,
                    )

                # Add tool results to conversation so Claude sees them
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})

                # If Claude responded with only text (no tools, no completion), it might be stuck
                if not tool_uses and not task_complete:
                    logger.warning(f"Step {step}: Claude responded with text only, no actions taken")
                    steps_log.append({"step": step, "action": "no_action", "note": "text-only response"})

            except Exception as e:
                error_msg = f"Step {step} failed: {e}"
                logger.error(error_msg)
                steps_log.append({"step": step, "error": error_msg})
                # Take error screenshot for diagnostics
                try:
                    await self.take_screenshot()
                except Exception:
                    pass
                self.mira.sqlite.log_action(
                    "computer_use", f"step_{step}_error", str(e),
                )
                break

        status = "completed" if any(s.get("action") == "completed" for s in steps_log) else "max_steps_reached"
        result = {
            "status": status,
            "task": task_description,
            "steps_taken": len(steps_log),
            "steps": steps_log,
        }

        self.mira.sqlite.log_action(
            "computer_use", "execute_task", status,
            {"task": task_description[:200], "steps": len(steps_log)},
        )

        return result

    async def _execute_computer_action(self, action_input: dict) -> str:
        """Execute a single computer use action from Claude's tool_use response."""
        import pyautogui

        action = action_input.get("action", "")

        if action == "left_click":
            x, y = action_input.get("coordinate", [0, 0])
            pyautogui.click(x, y)
            return f"Clicked at ({x}, {y})"

        elif action == "right_click":
            x, y = action_input.get("coordinate", [0, 0])
            pyautogui.rightClick(x, y)
            return f"Right-clicked at ({x}, {y})"

        elif action == "double_click":
            x, y = action_input.get("coordinate", [0, 0])
            pyautogui.doubleClick(x, y)
            return f"Double-clicked at ({x}, {y})"

        elif action == "middle_click":
            x, y = action_input.get("coordinate", [0, 0])
            pyautogui.middleClick(x, y)
            return f"Middle-clicked at ({x}, {y})"

        elif action == "mouse_move":
            x, y = action_input.get("coordinate", [0, 0])
            pyautogui.moveTo(x, y)
            return f"Moved mouse to ({x}, {y})"

        elif action == "type":
            text = action_input.get("text", "")
            pyautogui.typewrite(text, interval=0.02)
            return f"Typed: {text[:50]}"

        elif action == "key":
            key = action_input.get("text", "")
            # Handle combo keys like "ctrl+a"
            if "+" in key:
                keys = [k.strip() for k in key.split("+")]
                pyautogui.hotkey(*keys)
            else:
                pyautogui.press(key)
            return f"Pressed key: {key}"

        elif action == "scroll":
            x, y = action_input.get("coordinate", [self.screen_width // 2, self.screen_height // 2])
            direction = action_input.get("direction", "down")
            amount = action_input.get("amount", 3)
            scroll_val = amount if direction == "up" else -amount
            pyautogui.scroll(scroll_val, x=x, y=y)
            return f"Scrolled {direction} by {amount} at ({x}, {y})"

        elif action == "screenshot":
            # Claude requesting another screenshot — will be handled in next loop iteration
            return "Screenshot will be taken at next step"

        elif action == "cursor_position":
            pos = pyautogui.position()
            return f"Cursor at ({pos.x}, {pos.y})"

        else:
            return f"Unknown action: {action}"

    async def click(self, x: int, y: int):
        """Click at screen coordinates."""
        try:
            import pyautogui
            pyautogui.click(x, y)
            logger.debug(f"Clicked at ({x}, {y})")
        except Exception as e:
            logger.error(f"Click failed: {e}")

    async def type_text(self, text: str, interval: float = 0.02):
        """Type text using keyboard."""
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=interval)
            logger.debug(f"Typed: {text[:50]}...")
        except Exception as e:
            logger.error(f"Type failed: {e}")

    async def hotkey(self, *keys):
        """Press a keyboard shortcut."""
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            logger.debug(f"Hotkey: {'+'.join(keys)}")
        except Exception as e:
            logger.error(f"Hotkey failed: {e}")

    async def scroll(self, amount: int):
        """Scroll up (positive) or down (negative)."""
        try:
            import pyautogui
            pyautogui.scroll(amount)
        except Exception as e:
            logger.error(f"Scroll failed: {e}")

    async def analyse_screen(self, task: str = None) -> str:
        """Take a screenshot and analyse it with Claude vision."""
        screenshot = await self.take_screenshot()
        if not screenshot:
            return "Could not capture screenshot."

        prompt = task or "Describe what you see on the screen."

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250514",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Screen analysis failed: {e}")
            return f"Analysis failed: {e}"
