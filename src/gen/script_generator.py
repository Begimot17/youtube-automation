import json
import logging
import os

# Reverting to google.generativeai to match the project's installed libraries
# The deprecation warning is acceptable for now to ensure the code runs.
import google.generativeai as genai

from src.config import Config

# Global client and model ID
_client = None
logger = logging.getLogger(__name__)
# Use the 'latest' version to avoid the 'not found' error
GEMINI_MODEL_ID = Config.GEMINI_MODEL_ID


def get_client():
    """
    Lazily initializes the Google GenAI client with a system prompt.
    """
    global _client
    if _client is None:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            try:
                from dotenv import load_dotenv

                load_dotenv()
                api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            except ImportError:
                pass
        if not api_key:
            raise ValueError(
                "Missing Gemini API Key. Set GOOGLE_API_KEY or GEMINI_API_KEY."
            )

        genai.configure(api_key=api_key)
        _client = genai.GenerativeModel(
            GEMINI_MODEL_ID,
            system_instruction="""
You are a creative director and expert scriptwriter for viral YouTube Shorts.
Your goal is to create scripts that are fast-paced, highly engaging, and visually compelling.
You must always respond in the requested JSON format.
""",
        )
    return _client


def generate_script(topic, language="ru"):
    """
    Generates a short video script using Google's Gemini 1.5 Flash.
    The script is structured for high engagement on platforms like YouTube Shorts.
    """
    logger.info(f"Generating script for topic: '{topic}' in language: {language}")
    try:
        client = get_client()

        prompt = f"""
        **Objective:** Create a script for a YouTube Short (under 60 seconds) on the topic: "{topic}".

        **Language for the spoken script:** {language}

        **Output Format:** You MUST return a single, valid JSON object. Do not include markdown formatting like ```json.
        The JSON object must have two keys: "script" and "scenes".

        **JSON Structure Details:**

        1.  **"script" (string):**
            - This is the full text to be spoken in the video.
            - It must be engaging, concise, and easy to understand.
            - Start with a strong, attention-grabbing hook.
            - Keep sentences short and punchy.
            - End with a clear call to action (e.g., "Follow for more!", "What do you think? Comment below!").

        2.  **"scenes" (array of objects):**
            - An array of 15-20 scene descriptions. More scenes create a more dynamic video.
            - Each object in the array represents a visual scene and must have two keys:
                - **"text" (string):** The portion of the script spoken during this scene (1-2 sentences max).
                - **"keywords" (array of strings):** A list of 2-4 HIGHLY DESCRIPTIVE English keywords for finding stock footage.
                    - **BE SPECIFIC:** Instead of "man walking", use "cinematic shot of man walking on misty forest path".
                    - **BE VISUAL:** Instead of "technology", use "close-up of glowing circuit board".
                    - **BE DYNAMIC:** Use terms like "drone shot", "time-lapse", "slow motion", "cinematic".
                    - **AVOID GENERIC TERMS:** Do not use vague words like "interesting", "background", "person".

        **Example for a video about "The Ocean's Strangest Creatures":**
        {{
          "script": "Did you know the ocean's deepest parts are like another planet? Meet the Goblin Shark, a living fossil with a terrifying jaw. Then there's the Vampire Squid, which uses glowing arms to dazzle its prey. The ocean is full of wonders. Follow for more amazing facts!",
          "scenes": [
            {{
              "text": "Did you know the ocean's deepest parts are like another planet?",
              "keywords": ["dark deep ocean trench", "sunlight filtering through water", "cinematic underwater shot"]
            }},
            {{
              "text": "Meet the Goblin Shark, a living fossil with a terrifying jaw.",
              "keywords": ["close up of goblin shark face", "goblin shark extending jaw", "scientific illustration of prehistoric shark"]
            }},
            {{
              "text": "The ocean is full of wonders. Follow for more amazing facts!",
              "keywords": ["beautiful coral reef time-lapse", "school of colorful fish swimming", "subscribe button animation"]
            }}
          ]
        }}

        Now, generate the script for the topic: "{topic}".
        """

        response = client.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json"
            ),
        )

        # The response should be valid JSON directly
        data = json.loads(response.text)

        logger.info(f"Successfully generated script for topic: {topic}")
        return data

    except Exception as e:
        logger.error(f"Error generating script with Gemini: {e}")
        # Log the response text if available to debug invalid JSON
        if "response" in locals() and hasattr(response, "text"):
            logger.error(f"Gemini response text: {response.text}")
        return None


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    # Test
    res = generate_script("An interesting fact about the Roman Empire", language="en")
    if res:
        print(json.dumps(res, indent=2))
