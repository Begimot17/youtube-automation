import os
from openai import OpenAI
from pathlib import Path

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_voiceover(text, output_path, voice="onyx", model="tts-1"):
    """
    Generates audio from text using OpenAI TTS.

    Args:
        text (str): The text to recite.
        output_path (str): Path to save the .mp3 file.
        voice (str): OpenAI voice option (alloy, echo, fable, onyx, nova, shimmer).
        model (str): 'tts-1' (faster) or 'tts-1-hd' (better quality).
    """
    print(f"Generating voiceover: {text[:30]}...")

    try:
        response = client.audio.speech.create(model=model, voice=voice, input=text)

        # Save to file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        response.stream_to_file(output_path)
        print(f"Audio saved to {output_path}")
        return output_path

    except Exception as e:
        print(f"Error generating voiceover: {e}")
        return None


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    test_text = "This is a test of the automatic voice generation system."
    generate_voiceover(test_text, "test_audio.mp3")
