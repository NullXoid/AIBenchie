# playwright.py
# Description: Handles browser automation using Playwright. Supports persistent sessions, dynamic query execution, screenshot capture, and failure logging with LLaVA. Closes browser automatically on failure or explicit request. Also enforces shutdown of browser on all error paths.

import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright
from utils.memory import save_memory_item, save_note
from utils.multimodal_llava import query_llava_image
from utils.grid_tools import grid_cell_to_coordinates
from utils.memory_tiers import get_identity_value  # 🔐 Access tier level
import warnings
import os

# ⚠️ Suppress Windows pipe cleanup noise
warnings.filterwarnings("ignore", category=ResourceWarning)

# 🔧 Config loader
def get_browser_mode():
    try:
        with open("config.json", "r") as f:
            return json.load(f).get("browser_mode", "auto")
    except Exception:
        return "auto"

# 🧠 Prompt for LLaVA grid overlay
def grid_overlay_prompt(query):
    return (
        f"This is a screenshot from a web browser. Imagine the screen is divided into a 10x10 grid labeled A1 to J10. "
        f"Which grid cell most likely contains the search or input box if the user is trying to: '{query}'? "
        f"Respond with a single cell label (like D5)."
    )

def address_bar_prompt(url):
    return (
        f"This is a screenshot from a web browser. Imagine the screen is divided into a 10x10 grid labeled A1 to J10. "
        f"Which grid cell most likely contains the browser's address bar so the user can type in: '{url}'? "
        f"Respond with a single cell label (like B2)."
    )

# ♻️ Screenshot logic
MAX_SCREENSHOTS = 12
screenshot_dir = Path("screenshots")
screenshot_dir.mkdir(exist_ok=True)

def get_next_screenshot_path():
    existing = sorted(screenshot_dir.glob("search_result_*.png"))
    if len(existing) >= MAX_SCREENSHOTS:
        existing[0].unlink()
    index = len(existing) + 1
    return screenshot_dir / f"search_result_{index}.png"

# 🌍 Global state for persistent browser
_browser_instance = {"context": None, "browser": None, "page": None}

async def _store_browser_instances(context, browser, page):
    _browser_instance["context"] = context
    _browser_instance["browser"] = browser
    _browser_instance["page"] = page

# 🔐 Ensures browser gets closed completely even if outside normal loop
async def _close_browser_async():
    try:
        if _browser_instance["context"]:
            await _browser_instance["context"].close()
        elif _browser_instance["browser"]:
            await _browser_instance["browser"].close()
        print("🥸 Browser closed.")
    except Exception as e:
        print(f"❌ Failed to close browser: {e}")
    finally:
        _browser_instance["context"] = None
        _browser_instance["browser"] = None
        _browser_instance["page"] = None

def close_browser():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_close_browser_async())
        else:
            loop.run_until_complete(_close_browser_async())
    except RuntimeError:
        asyncio.run(_close_browser_async())

# 🆕 Awaitable variant for async contexts
async def close_browser_async():
    await _close_browser_async()

# 📸 Screenshot + LLaVA summary on failure
def capture_failed_screenshot(context_text=""):
    screenshot_path = get_next_screenshot_path()
    page = _browser_instance["page"]
    if not page:
        print("⚠️ No active page to capture.")
        return
    async def _capture():
        try:
            await page.screenshot(path=str(screenshot_path))
            print(f"📸 [Debug Screenshot] saved: {screenshot_path}")
            summary = query_llava_image(str(screenshot_path), f"Summarize why this failed. Context: {context_text}")
            save_note(f"[Browser Failure] {context_text}\nSummary: {summary}")
            print("🧠 [Failure Summary Saved]")
        except Exception as e:
            print(f"❌ Failed to capture or analyze screenshot: {e}")
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_capture())
        else:
            loop.run_until_complete(_capture())
    except RuntimeError:
        asyncio.run(_capture())

# 🌐 Main browser logic
async def perform_search(query):
    browser_mode = get_browser_mode()
    tier = (get_identity_value("Trust Tier") or "low").lower()

    p = await async_playwright().start()

    if tier == "high" and browser_mode == "auto":
        browser_mode = "manual"
    elif tier == "mid" and browser_mode == "auto":
        browser_mode = "persistent"

    if browser_mode == "persistent":
        user_data_dir = "playwright-user-data"
        context = await p.chromium.launch_persistent_context(user_data_dir, headless=False)
        page = await context.new_page()
        browser = None
    else:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

    await _store_browser_instances(context, browser, page)

    screenshot_path = get_next_screenshot_path()

    try:
        if query.startswith("http://") or query.startswith("https://"):
            await page.goto(query, timeout=15000)
            await page.wait_for_load_state("domcontentloaded")
            dom_text = await page.content()
            await page.screenshot(path=str(screenshot_path))
            vision_summary = query_llava_image(str(screenshot_path), f"What is this webpage about?")
            print("🤖 [Vision Summary]:", vision_summary)
            save_memory_item("web", f"Visited: {query}", description=vision_summary, tags=["visit", "browser"])
            return vision_summary

        search_engines = [
            ("https://search.brave.com", ["input[name='q']", "textarea[name='q']", "input[type='search']"]),
            ("https://www.google.com", ["input[name='q']", "textarea[name='q']"])
        ]

        for engine_url, selectors in search_engines:
            try:
                print(f"🌐 [Search] Searching: {query} via {engine_url}")
                await page.goto(engine_url, timeout=15000)
                for selector in selectors:
                    try:
                        await page.wait_for_selector(selector, timeout=4000)
                        input_box = await page.query_selector(selector)
                        if input_box:
                            await input_box.fill(query)
                            await page.keyboard.press("Enter")
                            await page.wait_for_load_state("networkidle")
                            await page.wait_for_timeout(3000)
                            break
                    except Exception as e:
                        print(f"⚠️ Selector failed: {selector} - {e}")
                        continue
                else:
                    raise Exception("No valid input selector found.")

                dom_text = await page.content()
                await page.screenshot(path=str(screenshot_path))
                vision_prompt = grid_overlay_prompt(query)
                vision_summary = query_llava_image(str(screenshot_path), vision_prompt)
                print("🤖 [Vision Summary]:", vision_summary)
                save_memory_item("web", f"Query: {query}", description=vision_summary, tags=["search", "browser"])
                return vision_summary

            except Exception as e:
                print(f"❌ [Search Error] {e}\nTrying next search engine...")
                capture_failed_screenshot(f"Search engine error: {e}")
                continue

        raise Exception("All search engines failed.")

    except Exception as final_error:
        print(f"❌ Final failure: {final_error}")
        capture_failed_screenshot(query)
        await _close_browser_async()
        return "Search failed across all engines. Browser closed."

if __name__ == "__main__":
    query = input("🔍 Enter search query: ")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(perform_search(query))
