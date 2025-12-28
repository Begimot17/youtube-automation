import json
import logging
import os

# Global client
_client = None
logger = logging.getLogger(__name__)

# Model ID
MODEL_ID = "gemini-flash-latest"


def get_client():
    """
    Lazily initializes the Google GenAI client.
    """
    global _client
    if _client is None:
        # Assumes GOOGLE_API_KEY or GEMINI_API_KEY is set in environment variables
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            # Try loading dotenv just in case
            try:
                from dotenv import load_dotenv

                load_dotenv()
                api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            except ImportError:
                pass

        if not api_key:
            raise ValueError(
                "Missing Gemini API Key. Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable."
            )

        from google import genai

        _client = genai.Client(api_key=api_key)
    return _client


DEFAULT_PROMPT = """
Act as a YouTube Shorts expert. Write a script on the topic: "{topic}".
Language of the script (narration and hook) must be: {language_name}.
Structure the response STRICTLY as valid JSON with the following keys:
- "hook": A catchy opening sentence (max 5 seconds).
- "script": The main narration text (approx 45-50 seconds).
- "scenes": A list of objects, each containing:
    - "visual_prompt": Description of the image/video to show.
    - "duration": Approx duration in seconds (3-5s).
    - "keywords": List of keywords to search for stock footage.
- "hashtags": List of relevant hashtags.

Make sure the total duration is under 60 seconds.
"""


def generate_script(topic, language="ru"):
    """
    Generates a YouTube Shorts script for the given topic using Gemini.
    """
    logger.info(f"Generating script for topic: {topic} (Lang: {language})...")

    language_name = "Russian" if language == "ru" else "English"

    try:
        client = get_client()
        prompt = DEFAULT_PROMPT.format(topic=topic, language_name=language_name)
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        content = response.text
        script_data = json.loads(content)
        return script_data

    except Exception as e:
        logger.error(f"Error generating script: {e}")
        return None


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    test_topic = "Top 3 Space Facts"
    result = generate_script(test_topic, language="en")
    print(json.dumps(result, indent=2))
