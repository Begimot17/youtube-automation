import logging
import os
import time

logger = logging.getLogger(__name__)


def generate_video_v2(
    action_prompt: str,
    output_dir: str,
    output_filename: str = None,
) -> str:
    """
    Generates a video via RunPod/ComfyUI for the given prompt.
    Returns the absolute path to the saved output file.
    Raises RuntimeError or TimeoutError on failure.
    """
    from src.gen_v2.main import generate_scene

    os.makedirs(output_dir, exist_ok=True)
    if not output_filename:
        output_filename = f"gen_v2_{int(time.time())}.mp4"
    output_path = os.path.join(output_dir, output_filename)

    logger.info(f"gen_v2 renderer: prompt='{action_prompt}' → {output_path}")
    generate_scene(action_prompt, output_path)
    return output_path
