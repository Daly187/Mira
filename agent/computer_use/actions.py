"""
Computer Use Actions Library — reusable high-level action sequences built on top
of the ComputerUseAgent low-level primitives (click, type, screenshot).

Provides named operations like open_application, navigate_to_url, fill_form, etc.
that compose the raw pyautogui actions into reliable, retryable workflows.
"""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger("mira.computer_use.actions")

# Common application launch commands (Windows-centric, matching the runtime environment)
APP_LAUNCH_MAP = {
    # Trading
    "mt5": {"type": "search", "query": "MetaTrader 5"},
    "metatrader": {"type": "search", "query": "MetaTrader 5"},
    # Browsers
    "chrome": {"type": "search", "query": "Google Chrome"},
    "firefox": {"type": "search", "query": "Firefox"},
    "edge": {"type": "search", "query": "Microsoft Edge"},
    "brave": {"type": "search", "query": "Brave"},
    # Communication
    "telegram": {"type": "search", "query": "Telegram"},
    "whatsapp": {"type": "search", "query": "WhatsApp"},
    "discord": {"type": "search", "query": "Discord"},
    "slack": {"type": "search", "query": "Slack"},
    "teams": {"type": "search", "query": "Microsoft Teams"},
    # Productivity
    "notepad": {"type": "search", "query": "Notepad"},
    "excel": {"type": "search", "query": "Excel"},
    "word": {"type": "search", "query": "Word"},
    "vscode": {"type": "search", "query": "Visual Studio Code"},
    "terminal": {"type": "search", "query": "Terminal"},
    "cmd": {"type": "search", "query": "Command Prompt"},
    "powershell": {"type": "search", "query": "PowerShell"},
    # File management
    "explorer": {"type": "hotkey", "keys": ["win", "e"]},
    "file_explorer": {"type": "hotkey", "keys": ["win", "e"]},
    # System
    "settings": {"type": "hotkey", "keys": ["win", "i"]},
    "task_manager": {"type": "hotkey", "keys": ["ctrl", "shift", "escape"]},
}


class ComputerActions:
    """High-level reusable action sequences for desktop automation."""

    def __init__(self, agent):
        """
        Args:
            agent: A ComputerUseAgent instance providing low-level primitives
                   (take_screenshot, click, type_text, hotkey, scroll, analyse_screen).
        """
        self.agent = agent

    # ── Application Management ────────────────────────────────────────

    async def open_application(self, app_name: str) -> dict:
        """Launch an application by name using the Windows Start menu search.

        Looks up the app in APP_LAUNCH_MAP for known shortcuts; falls back
        to Start menu search for any arbitrary app name.

        Args:
            app_name: Application name (e.g. "chrome", "mt5", "excel").

        Returns:
            dict with status and any details.
        """
        import pyautogui

        app_key = app_name.lower().replace(" ", "_")
        launch_info = APP_LAUNCH_MAP.get(app_key)

        if launch_info and launch_info["type"] == "hotkey":
            # Direct hotkey launch (e.g. Win+E for Explorer)
            await self.agent.hotkey(*launch_info["keys"])
            await asyncio.sleep(1.0)
            logger.info(f"Launched {app_name} via hotkey {launch_info['keys']}")
            return {"status": "success", "method": "hotkey", "app": app_name}

        # Start menu search approach
        search_query = launch_info["query"] if launch_info else app_name

        # Open Start menu
        await self.agent.hotkey("win")
        await asyncio.sleep(0.5)

        # Type the app name to search
        await self.agent.type_text(search_query, interval=0.03)
        await asyncio.sleep(1.0)

        # Press Enter to launch the top result
        pyautogui.press("enter")
        await asyncio.sleep(1.5)

        logger.info(f"Launched {app_name} via Start menu search")
        return {"status": "success", "method": "start_search", "app": app_name}

    # ── Browser Navigation ────────────────────────────────────────────

    async def navigate_to_url(self, url: str) -> dict:
        """Open a browser and navigate to a URL.

        If no browser window is detected, launches Chrome first.
        Uses Ctrl+L to focus the address bar, types the URL, and presses Enter.

        Args:
            url: The full URL to navigate to.

        Returns:
            dict with status.
        """
        import pyautogui

        # Focus address bar (works in all major browsers)
        await self.agent.hotkey("ctrl", "l")
        await asyncio.sleep(0.3)

        # Clear any existing text and type the URL
        await self.agent.hotkey("ctrl", "a")
        await asyncio.sleep(0.1)
        await self.agent.type_text(url, interval=0.01)
        await asyncio.sleep(0.2)

        # Navigate
        pyautogui.press("enter")
        await asyncio.sleep(2.0)

        logger.info(f"Navigated to {url}")
        return {"status": "success", "url": url}

    # ── Screenshot & Analysis ─────────────────────────────────────────

    async def take_and_analyse_screenshot(self, question: str) -> dict:
        """Capture the current screen and analyse it with Claude Vision.

        Args:
            question: What to look for / ask about the screen content.

        Returns:
            dict with the analysis text and status.
        """
        analysis = await self.agent.analyse_screen(task=question)

        if analysis and not analysis.startswith("Could not") and not analysis.startswith("Analysis failed"):
            logger.info(f"Screen analysis complete: {analysis[:100]}...")
            return {"status": "success", "analysis": analysis}

        return {"status": "error", "message": analysis or "Screenshot analysis failed"}

    # ── Form Filling ──────────────────────────────────────────────────

    async def fill_form(self, fields: dict) -> dict:
        """Fill form fields by tabbing through them and typing values.

        Assumes the first form field is already focused (or clicks into the
        first field using the field descriptions). Tabs between fields in order.

        Args:
            fields: Ordered dict of {field_label: value}. Values are typed in
                    the order provided, with Tab pressed between each.

        Returns:
            dict with status and number of fields filled.
        """
        import pyautogui

        filled = 0
        for label, value in fields.items():
            try:
                # Type the value
                await self.agent.type_text(str(value), interval=0.02)
                filled += 1

                # Tab to next field
                pyautogui.press("tab")
                await asyncio.sleep(0.2)

            except Exception as e:
                logger.error(f"Error filling field '{label}': {e}")
                return {
                    "status": "partial",
                    "fields_filled": filled,
                    "total_fields": len(fields),
                    "error": f"Failed on '{label}': {e}",
                }

        logger.info(f"Filled {filled}/{len(fields)} form fields")
        return {
            "status": "success",
            "fields_filled": filled,
            "total_fields": len(fields),
        }

    # ── Screen Reading (OCR) ──────────────────────────────────────────

    async def read_screen_text(self) -> dict:
        """Take a screenshot and extract all visible text using Claude Vision OCR.

        Returns:
            dict with the extracted text.
        """
        screenshot = await self.agent.take_screenshot()
        if not screenshot:
            return {"status": "error", "message": "Screenshot capture failed"}

        try:
            response = self.agent.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
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
                        {
                            "type": "text",
                            "text": (
                                "Extract ALL visible text from this screenshot. "
                                "Preserve the layout and structure as much as possible. "
                                "Include window titles, menu items, button labels, and any "
                                "other readable text. Return only the extracted text."
                            ),
                        },
                    ],
                }],
            )

            text = response.content[0].text
            logger.info(f"Screen OCR extracted {len(text)} characters")
            return {"status": "success", "text": text}

        except Exception as e:
            logger.error(f"Screen OCR failed: {e}")
            return {"status": "error", "message": str(e)}

    # ── Element Interaction ───────────────────────────────────────────

    async def wait_for_element(
        self, description: str, timeout: int = 30, poll_interval: float = 2.0
    ) -> dict:
        """Poll screenshots until a described element appears on screen.

        Uses Claude Vision to check each screenshot for the presence of the
        described element.

        Args:
            description: Natural language description of the element to wait for
                         (e.g. "a green Submit button", "the login page").
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between screenshot polls.

        Returns:
            dict with status and whether the element was found.
        """
        start = time.time()
        attempts = 0

        while (time.time() - start) < timeout:
            attempts += 1
            screenshot = await self.agent.take_screenshot()
            if not screenshot:
                await asyncio.sleep(poll_interval)
                continue

            try:
                response = self.agent.client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=256,
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
                            {
                                "type": "text",
                                "text": (
                                    f"Is the following element visible on screen: '{description}'?\n"
                                    f"Reply with ONLY 'YES' or 'NO'."
                                ),
                            },
                        ],
                    }],
                )

                answer = response.content[0].text.strip().upper()
                if answer.startswith("YES"):
                    elapsed = time.time() - start
                    logger.info(
                        f"Element found: '{description}' after {elapsed:.1f}s ({attempts} polls)"
                    )
                    return {
                        "status": "found",
                        "description": description,
                        "elapsed_seconds": round(elapsed, 1),
                        "attempts": attempts,
                    }

            except Exception as e:
                logger.warning(f"Vision check failed during wait: {e}")

            await asyncio.sleep(poll_interval)

        logger.warning(f"Element not found after {timeout}s: '{description}'")
        return {
            "status": "timeout",
            "description": description,
            "timeout_seconds": timeout,
            "attempts": attempts,
        }

    async def click_element(self, description: str) -> dict:
        """Find an element on screen by description and click its centre.

        Takes a screenshot, asks Claude Vision to locate the element and return
        its centre coordinates, then clicks there.

        Args:
            description: Natural language description of what to click
                         (e.g. "the blue Login button", "the search bar").

        Returns:
            dict with status and the coordinates clicked.
        """
        screenshot = await self.agent.take_screenshot()
        if not screenshot:
            return {"status": "error", "message": "Screenshot capture failed"}

        try:
            response = self.agent.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=256,
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
                        {
                            "type": "text",
                            "text": (
                                f"Find the element described as: '{description}'\n"
                                f"The screen resolution is {self.agent.screen_width}x{self.agent.screen_height}.\n"
                                f"Return ONLY the centre coordinates as two integers separated by a comma, "
                                f"e.g. '540,320'. If the element is not visible, reply with 'NOT_FOUND'."
                            ),
                        },
                    ],
                }],
            )

            answer = response.content[0].text.strip()

            if "NOT_FOUND" in answer.upper():
                logger.warning(f"Element not found on screen: '{description}'")
                return {
                    "status": "not_found",
                    "description": description,
                }

            # Parse coordinates
            parts = answer.replace(" ", "").split(",")
            x, y = int(parts[0]), int(parts[1])

            # Validate coordinates are within screen bounds
            x = max(0, min(x, self.agent.screen_width - 1))
            y = max(0, min(y, self.agent.screen_height - 1))

            await self.agent.click(x, y)
            logger.info(f"Clicked element '{description}' at ({x}, {y})")

            return {
                "status": "success",
                "description": description,
                "coordinates": {"x": x, "y": y},
            }

        except (ValueError, IndexError) as e:
            logger.error(f"Failed to parse coordinates for '{description}': {e}")
            return {
                "status": "error",
                "description": description,
                "message": f"Coordinate parsing failed: {e}",
            }
        except Exception as e:
            logger.error(f"click_element failed: {e}")
            return {"status": "error", "message": str(e)}

    # ── Composite Workflows ───────────────────────────────────────────

    async def open_url_in_browser(self, url: str, browser: str = "chrome") -> dict:
        """Launch a browser (if needed) and navigate to a URL.

        Combines open_application and navigate_to_url into one call.

        Args:
            url: Target URL.
            browser: Browser to use (default "chrome").

        Returns:
            dict with combined status.
        """
        # Launch browser
        launch_result = await self.open_application(browser)
        await asyncio.sleep(2.0)

        # Navigate
        nav_result = await self.navigate_to_url(url)

        return {
            "status": nav_result.get("status", "error"),
            "browser": browser,
            "url": url,
            "launch": launch_result,
            "navigation": nav_result,
        }

    async def type_and_submit(self, text: str, submit_key: str = "enter") -> dict:
        """Type text and press a submit key (Enter by default).

        Useful for search bars, command inputs, chat boxes, etc.

        Args:
            text: Text to type.
            submit_key: Key to press after typing (default "enter").

        Returns:
            dict with status.
        """
        import pyautogui

        await self.agent.type_text(text, interval=0.02)
        await asyncio.sleep(0.2)
        pyautogui.press(submit_key)

        logger.info(f"Typed and submitted: '{text[:50]}...' + {submit_key}")
        return {"status": "success", "text": text[:50], "submit_key": submit_key}
