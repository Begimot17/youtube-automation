import asyncio
import logging
from pathlib import Path

import edge_tts

logger = logging.getLogger(__name__)


def generate_voiceover(text, output_path, language="ru"):
    """
    Generates audio from text using edge-tts (free Microsoft Edge voices).

    Args:
        text (str): The text to recite.
        output_path (str): Path to save the .mp3 file.
        language (str): 'en' or 'ru'.
    """
    voice_map = {"ru": "ru-RU-DmitryNeural", "en": "en-US-ChristopherNeural"}
    voice = voice_map.get(language, "ru-RU-DmitryNeural")

    logger.info(f"Generating voiceover with edge-tts: {text[:30]}... (Voice: {voice})")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:

        async def _generate():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))

        # Since we might be calling this from a synchronous context,
        # we handle the event loop accordingly.
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # This is tricky in some environments, but for our CLI/Scripts:
                import nest_asyncio

                nest_asyncio.apply()
            asyncio.run(_generate())
        except Exception:
            # Fallback for simple standalone runs
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
