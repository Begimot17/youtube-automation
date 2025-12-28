import json
import logging
import os

# Global client
_client = None
logger = logging.getLogger(__name__)

MODEL_ID = "gemini-2.0-flash"


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


def generate_subtitles(audio_path):
    """
    Transcribes audio using Gemini 1.5 Flash to get word-level timestamps.
    Returns a list of word objects: [{'word': str, 'start': float, 'end': float}]
    """
    logger.info(f"Transcribing audio with Gemini: {audio_path}...")
    try:
        client = get_client()
        # 1. Upload the file
        # The correct parameter is 'file' for the path or file-like object
        audio_file = client.files.upload(file=audio_path)
        logger.info(f"Uploaded file: {audio_file.name}")

        # 2. Transcribe with prompt
        prompt = """
        Analyze the provided audio and transcribe it. 
        For each word, provide the start and end time in seconds.
        Return the result STRICTLY as a JSON array of objects.
        Each object should have keys: "word", "start", "end".
        Example: [{"word": "Hello", "start": 0.1, "end": 0.5}]
        """

        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[prompt, audio_file],
            config={"response_mime_type": "application/json"},
        )

        content = response.text
        if not content:
            logger.error("Empty response from Gemini.")
            return []

        words = json.loads(content)
        logger.info(f"Transcription complete. Found {len(words)} words.")
        return words

    except Exception as e:
        logger.error(f"Error generating subtitles with Gemini: {e}")
        return []


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    # Test
    # print(generate_subtitles("test_audio.mp3"))
