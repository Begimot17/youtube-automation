import json
import logging

from google import genai

from src.config import Config

logger = logging.getLogger(__name__)

# Initialize Gemini Client
GEMINI_API_KEY = Config.GOOGLE_API_KEY


def generate_script(topic, language="ru"):
    """
    Generate a short video script using Google's Gemini 1.5 Flash.
    """
    if not GEMINI_API_KEY:
        logger.error("GOOGLE_API_KEY not found.")
        return None

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        prompt = f"""
        Create a high-quality script for a YouTube Short video (under 60 seconds) about: {topic}.
        The language of the spoken script MUST be: {language}.
        
        The output MUST be a JSON object with two fields:
        1. "script": a string containing the punchy, engaging text to be spoken.
        2. "scenes": a list of objects (at least 15-20 scenes for variety), each containing:
           - "text": a small snippet (1-2 sentences) of the script for this scene.
           - "keywords": a list of 2-4 HIGHLY DESCRIPTIVE English keywords to search for specific, relevant stock footage (e.g., ["close up of space star nebula", "telescope lens looking at space", "cinematic galaxy animation"]). 
           Avoid generic keywords like "man" or "business". Be specific and varied.

        Make sure the keywords are in English regardless of the output language.
        """

        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )

        if not response.text:
            logger.error("Gemini returned empty text.")
            return None

        # Parse JSON from response
        text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)

        logger.info(f"Generated script for topic: {topic}")
        return data

    except Exception as e:
        logger.error(f"Error generating script with Gemini: {e}")
        return None


if __name__ == "__main__":
    # Test
    res = generate_script("Interesting fact about space", language="en")
    print(res)
