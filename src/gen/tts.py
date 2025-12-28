import asyncio
import logging
from pathlib import Path

import edge_tts
import nest_asyncio

logger = logging.getLogger(__name__)


def generate_voiceover(text, output_path, lang="en", voice=None):
    """
    Generates an MP3 file from text using edge-tts.
    """
    if not voice:
        # Default voices if none provided
        if lang == "ru":
            voice = "ru-RU-SvetlanaNeural"
        else:
            voice = "en-US-AriaNeural"

    logger.info(f"Generating voiceover ({voice}): {output_path}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:

        async def _generate():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                nest_asyncio.apply()
            asyncio.run(_generate())
        except Exception:
            asyncio.run(_generate())

        logger.info(f"Audio saved to {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Error generating voiceover with edge-tts: {e}")
        return None


if __name__ == "__main__":
    test_text = (
        "This is a test of the automatic voice generation system using edge-tts."
    )
    generate_voiceover(test_text, "test_audio.mp3")
