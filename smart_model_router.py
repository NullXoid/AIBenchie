# smart_model_router.py
# Description: Routes tasks to text, vision, or tool-based models (Playwright or Open Interpreter) based on the user's input. Automatically closes browser on failure and captures screenshots for debugging.

import base64
import requests
import os
import asyncio

OLLAMA_API_URL = "http://localhost:11434/api/generate"
VISION_MODELS = ["llava", "llava:13b", "bakllava"]  # Add more if needed
TEXT_MODEL_DEFAULT = "deepseek-r1:14b"
VISION_MODEL_DEFAULT = "llava:13b"

def encode_image(image_path):
    """Encode an image to base64 for Ollama vision model input."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def smart_model_router(prompt=None, image_path=None, model_hint=None, stream=False):
    """
    Auto-detects input type and routes to vision or text model accordingly.

    Parameters:
        prompt (str): User's prompt.
        image_path (str): Optional image file path.
        model_hint (str): Optional override for the model name.
        stream (bool): Whether to use streaming responses.

    Returns:
        tuple: (response, source) where source is one of "text", "vision", "oi", or "playwright".
    """
    if not prompt and not image_path:
        return ("You must provide at least a prompt or an image.", "text")

    # --- Source Routing Logic ---
    lower_prompt = (prompt or "").lower()

    if image_path:
        source = "vision"
    elif any(word in lower_prompt for word in ["http", ".com", "search", "go to", "navigate"]):
        source = "playwright"
    elif any(word in lower_prompt for word in ["run", "open", ".py", ".lnk", "execute"]):
        source = "oi"
    else:
        source = "text"

    # --- Handle vision if image present ---
    if source == "vision":
        try:
            payload = {
                "model": model_hint or VISION_MODEL_DEFAULT,
                "prompt": prompt or "What do you see in this image?",
                "stream": stream,
                "images": [encode_image(image_path)]
            }
            response = requests.post(OLLAMA_API_URL, json=payload)
            response.raise_for_status()
            return (response.json().get("response", "[Vision] No response."), source)
        except Exception as e:
            return (f"[Vision Error] {e}", source)

    # --- Handle text or routeable prompt ---
    try:
        payload = {
            "model": model_hint or TEXT_MODEL_DEFAULT,
            "prompt": prompt or "",
            "stream": stream
        }
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        return (response.json().get("response", "[Text] No response."), source)

    except requests.exceptions.RequestException as e:
        if source == "playwright":
            print("❌ All search engines failed. Closing browser.")
            try:
                capture_failed_screenshot(prompt)  # Custom debugging screenshot for failed route
            except Exception as screenshot_error:
                print(f"⚠️ Screenshot capture failed: {screenshot_error}")
            try:
                close_browser()
            except Exception as close_error:
                print(f"⚠️ Browser close failed: {close_error}")
            return ("❌ All search engines failed. Browser closed.", source)

        return (f"[Ollama Error] {e}", source)
