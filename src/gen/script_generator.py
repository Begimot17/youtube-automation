import json
import logging
import os

from openai import OpenAI

# Initialize Client
# Assumes OPENAI_API_KEY is set in environment variables
logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DEFAULT_PROMPT = """
Act as a YouTube Shorts expert. Write a script on the topic: "{topic}".
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


def generate_script(topic):
    """
    Generates a YouTube Shorts script for the given topic using GPT-4o.
    """
    logger.info(f"Generating script for topic: {topic}...")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a creative content generator for viral YouTube Shorts.",
                },
                {"role": "user", "content": DEFAULT_PROMPT.format(topic=topic)},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        script_data = json.loads(content)
        return script_data

    except Exception as e:
        logger.error(f"Error generating script: {e}")
        return None


if __name__ == "__main__":
    # Test run
    # Ensure OPENAI_API_KEY is in env or .env
    from dotenv import load_dotenv

    load_dotenv()

    test_topic = "Top 3 Space Facts"
    result = generate_script(test_topic)
    print(json.dumps(result, indent=2))
