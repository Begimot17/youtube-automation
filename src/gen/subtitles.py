import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_subtitles(audio_path):
    """
    Transcribes audio using Whisper to get word-level timestamps.
    Returns the verbose JSON object.
    """
    print(f"Transcribing audio: {audio_path}...")
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["word"],
            )
        return transcript.words  # List of {'word':str, 'start':float, 'end':float}
    except Exception as e:
        print(f"Error generating subtitles: {e}")
        return []


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    # Test
    # print(generate_subtitles("test_audio.mp3"))
