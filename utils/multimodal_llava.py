# multimodal_llava.py

import base64
import requests

# 🧠 This points to your local Ollama instance running LLaVA
OLLAMA_LLAVA_MODEL = "llava"  # Update if you use a different model name
OLLAMA_URL = "http://localhost:11434/api/generate"

def query_llava_image(image_path, prompt):
    """
    Sends a prompt and image to a locally running LLaVA model via Ollama.

    Args:
        image_path (str): Path to the image file
        prompt (str): Vision question

    Returns:
        str: Response from LLaVA model
    """
    try:
        with open(image_path, "rb") as img_file:
            image_base64 = base64.b64encode(img_file.read()).decode("utf-8")

        payload = {
            "model": OLLAMA_LLAVA_MODEL,
            "prompt": prompt,
            "images": [image_base64],
            "stream": False
        }

        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "⚠️ LLaVA responded without content")

    except Exception as e:
        return f"❌ [query_llava_image error] {e}"

# Optional: Add auto-routing for vision model in the future
