import logging
import os
import sys
import time

# Add project root to sys.path to support 'from src...' imports when run directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.gen import scenes as scenes_module
from src.gen import script_generator, subtitles, tts, visuals
from src.rendering.engine import VideoRenderer

logger = logging.getLogger(__name__)


def create_content(
    topic, channel_name="TestChannel", language="ru", quality="easy", voice=None
):
    """
    Full pipeline to create a video from a topic.
    """
    logger.info(
        f"Starting content creation for: {topic} (Lang: {language}, Quality: {quality}, Voice: {voice})"
    )

    # Paths
    base_dir = f"data/output/{channel_name}/{int(time.time())}"
    os.makedirs(base_dir, exist_ok=True)

    audio_path = os.path.join(base_dir, "voiceover.mp3")
    video_output = os.path.join(base_dir, "final.mp4")

    # 1. Script
    logger.info("Step 1: generating Script")
    script_data = script_generator.generate_script(topic, language=language)
    if not script_data:
        logger.error("Failed to generate script.")
        return None

    script_text = script_data.get("script", "")
    if not script_text.strip():
        logger.error("Script is empty.")
        return None
    logger.info(f"Script length: {len(script_text)} chars")

    # 2. Audio
    logger.info("Step 2: Generating Audio")
    if not tts.generate_voiceover(script_text, audio_path, lang=language, voice=voice):
        logger.error("Failed to generate voiceover.")
        return None

    # 3. Subtitles
    logger.info("Step 3: Generating Subtitles")
    subs = subtitles.generate_subtitles_v2(audio_path, language=language)

    # 4. Visuals
    logger.info("Step 4: Fetching Visuals")
    visual_paths = scenes_module.collect_visuals(
        script_data.get("scenes", []),
        topic,
        base_dir,
        lambda query, out, used: visuals.get_stock_footage(query, out, used_urls=used),
    )

    if not visual_paths:
        logger.error("No visuals downloaded.")

    # 5. Assemble
    logger.info("Step 5: Assembling Video")
    renderer = VideoRenderer()
    renderer.assemble_short(
        audio_path,
        visual_paths,
        subtitles=subs,
        output_path=video_output,
        quality=quality,
    )

    logger.info(f"Video created successfully: {video_output}")
    return video_output


if __name__ == "__main__":
    import argparse

    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Generate YouTube Short from Topic")
    parser.add_argument(
        "--topic", type=str, default="DefaultTopic", help="Topic for the video script"
    )
    parser.add_argument(
        "--channel", type=str, default="DefaultChannel", help="Target channel name"
    )
    parser.add_argument(
        "--lang",
        type=str,
        default="ru",
        choices=["en", "ru"],
        help="Language for content",
    )
    parser.add_argument("--quality", type=str, default="easy", help="Rendering quality")
    parser.add_argument("--voice", type=str, default=None, help="TTS voice name")

    args = parser.parse_args()

    create_content(args.topic, args.channel, args.lang, args.quality, args.voice)
