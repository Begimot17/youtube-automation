import os
import time

from src.gen import script_generator, subtitles, tts, visuals
from src.rendering.engine import VideoRenderer


def create_content(topic, channel_name="TestChannel"):
    """
    Full pipeline to create a video from a topic.
    """
    print(f"🚀 Starting content creation for: {topic}")

    # Paths
    base_dir = f"output/{channel_name}/{int(time.time())}"
    os.makedirs(base_dir, exist_ok=True)

    audio_path = f"{base_dir}/voiceover.mp3"
    video_output = f"{base_dir}/final.mp4"

    # 1. Script
    print("\n--- Step 1: generating Script ---")
    script_data = script_generator.generate_script(topic)
    if not script_data:
        return

    script_text = script_data.get("script", "")
    print(f"Script length: {len(script_text)} chars")

    # 2. Audio
    print("\n--- Step 2: Generating Audio ---")
    if not tts.generate_voiceover(script_text, audio_path):
        return

    # 3. Subtitles
    print("\n--- Step 3: Generating Subtitles ---")
    subs = subtitles.generate_subtitles(audio_path)

    # 4. Visuals
    print("\n--- Step 4: Fetching Visuals ---")
    visual_paths = []
    scenes = script_data.get("scenes", [])
    for i, scene in enumerate(scenes):
        keywords = scene.get("keywords", [])
        if not keywords:
            keywords = [topic]

        # Try first keyword
        query = keywords[0]
        v_path = f"{base_dir}/scene_{i}.mp4"

        downloaded = visuals.get_stock_footage(query, v_path)
        if downloaded:
            visual_paths.append(downloaded)
        else:
            print(f"Warning: Could not download visual for {query}")

    if not visual_paths:
        print("Error: No visuals downloaded.")
        return

    # 5. Assemble
    print("\n--- Step 5: Assembling Video ---")
    renderer = VideoRenderer()
    renderer.assemble_short(
        audio_path, visual_paths, subtitles=subs, output_path=video_output
    )

    print(f"\n✅ Video created successfully: {video_output}")
    return video_output


if __name__ == "__main__":
    import argparse

    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Generate YouTube Short from Topic")
    parser.add_argument(
        "--topic", type=str, required=True, help="Topic for the video script"
    )
    parser.add_argument(
        "--channel",
        type=str,
        default="DefaultChannel",
        help="Target channel name (for folder organization)",
    )

    args = parser.parse_args()

    create_content(args.topic, args.channel)
