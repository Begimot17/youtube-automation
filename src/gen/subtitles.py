import json
import logging
import os

import assemblyai
import google.generativeai as genai

logger = logging.getLogger(__name__)

# --- Gemini Configuration (Original) ---
_gemini_client = None
GEMINI_MODEL_ID = "gemini-2.5-flash-lite"


def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
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
        _gemini_client = genai.GenerativeModel(
            GEMINI_MODEL_ID,
            system_instruction="You are an expert audio transcriptionist. Your task is to return word-level timestamps with the highest possible accuracy.",
        )
    return _gemini_client


def generate_subtitles(audio_path):
    """
    Transcribes audio using Gemini 1.5 Flash to get word-level timestamps.
    Returns a list of word objects: [{'word': str, 'start': float, 'end': float}]
    """
    logger.info(f"Transcribing audio with Gemini: {audio_path}...")
    audio_file = None
    try:
        client = get_gemini_client()
        # 1. Upload the file
        logger.info(f"Uploading file to Gemini: {audio_path}")
        audio_file = genai.upload_file(path=audio_path)
        logger.info(f"Uploaded file: {audio_file.name}")

        # 2. Transcribe with prompt
        prompt = """
        Analyze the provided audio and transcribe it.
        For each word, provide the start and end time in seconds.
        Return the result STRICTLY as a JSON array of objects.
        Each object should have keys: "word", "start", "end".
        Example: [{"word": "Hello", "start": 0.1, "end": 0.5}]
        """

        response = client.generate_content(
            contents=[prompt, audio_file],
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json"
            ),
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
    finally:
        if audio_file:
            try:
                logger.info(f"Deleting uploaded file: {audio_file.name}")
                genai.delete_file(audio_file.name)
            except Exception as e:
                logger.error(f"Failed to delete uploaded file {audio_file.name}: {e}")


# --- AssemblyAI Configuration (V2) ---
def configure_assemblyai():
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        try:
            from dotenv import load_dotenv

            load_dotenv()
            api_key = os.getenv("ASSEMBLYAI_API_KEY")
        except ImportError:
            pass
    if not api_key:
        raise ValueError(
            "Missing AssemblyAI API Key. Set ASSEMBLYAI_API_KEY environment variable."
        )
    assemblyai.settings.api_key = api_key


def generate_subtitles_v2(audio_path, language="en"):
    """
    Transcribes audio using AssemblyAI to get word-level timestamps. (V2)

    Args:
        audio_path (str): Path to the audio file.
        language (str): Language code for transcription (e.g., 'en', 'es', 'ru').
                        Defaults to 'en'.

    Returns:
        list: A list of word objects with timestamps, or an empty list on failure.
    """
    logger.info(
        f"Transcribing audio with AssemblyAI (v2) in '{language}': {audio_path}..."
    )
    try:
        configure_assemblyai()
        config = assemblyai.TranscriptionConfig(
            speaker_labels=False, disfluencies=False, language_code=language
        )
        transcriber = assemblyai.Transcriber(config=config)
        transcript = transcriber.transcribe(audio_path)

        if transcript.status == assemblyai.TranscriptStatus.error:
            logger.error(f"AssemblyAI transcription failed: {transcript.error}")
            return []

        if not transcript.words:
            logger.warning("AssemblyAI transcription did not return any words.")
            return []

        subtitles = [
            {"word": word.text, "start": word.start / 1000.0, "end": word.end / 1000.0}
            for word in transcript.words
        ]
        logger.info(
            f"Transcription complete with AssemblyAI. Found {len(subtitles)} words."
        )
        return subtitles
    except Exception as e:
        logger.error(f"Error generating subtitles with AssemblyAI: {e}")
        return []


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    test_audio_path = "test_audio.mp3"
    if os.path.exists(test_audio_path):
        print("--- Testing Gemini (v1) ---")
        subs_v1 = generate_subtitles(test_audio_path)
        if subs_v1:
            print(json.dumps(subs_v1[:5], indent=2, ensure_ascii=False))
        else:
            print("Gemini (v1) failed.")

        print("\n--- Testing AssemblyAI (v2) ---")
        subs_v2 = generate_subtitles_v2(test_audio_path, language="ru")
        if subs_v2:
            print(json.dumps(subs_v2[:5], indent=2, ensure_ascii=False))
        else:
            print("AssemblyAI (v2) failed.")
    else:
        print(f"Create a file named '{test_audio_path}' to run tests.")
