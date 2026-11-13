import asyncio
import logging
from pathlib import Path

import edge_tts

logger = logging.getLogger(__name__)


def _run(coro):
    """Runs a coroutine from sync code, also when an event loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import nest_asyncio

    nest_asyncio.apply()
    return asyncio.get_event_loop().run_until_complete(coro)


DEFAULT_VOICES = {"ru": "ru-RU-SvetlanaNeural", "en": "en-US-AriaNeural"}


def generate_voiceover(text, output_path, lang="en", voice=None):
    """
    Generates an MP3 file from text using edge-tts.
    """
    if not voice:
        # Default voices if none provided
        voice = DEFAULT_VOICES.get(lang, DEFAULT_VOICES["en"])

    if not text or not str(text).strip():
        logger.error("Cannot generate voiceover from empty text.")
        return None

    logger.info(f"Generating voiceover ({voice}): {output_path}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:

        async def _generate():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))

        _run(_generate())

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
