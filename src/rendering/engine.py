import logging
import math
import os

import numpy as np
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

# Monkeypatch for PIL.Image.ANTIALIAS (removed in Pillow 10.0.0)
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = getattr(
        PIL.Image, "LANCZOS", getattr(PIL.Image, "BICUBIC", None)
    )

from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)

logger = logging.getLogger(__name__)


class VideoRenderer:
    def __init__(self, resolution=(1080, 1920)):
        """
        Initialize renderer. Default resolution is 1080x1920 (9:16 Short).
        """
        self.width = resolution[0]
        self.height = resolution[1]

    def create_test_video(self, output_path, text="Hello World"):
        """
        Creates a simple test video (colors + text) to verify MoviePy is working.
        """
        logger.info(f"Rendering test video to {output_path}...")
        final_clip = None
        try:
            # 1. Create a background
            bg_clip = ColorClip(
                size=(self.width, self.height), color=(0, 0, 255), duration=5
            )

            # 2. Add Text
            try:
                txt_clip = TextClip(
                    text,
                    fontsize=70,
                    color="white",
                    size=(self.width, None),
                    method="caption",
                )
                txt_clip = txt_clip.set_position("center").set_duration(5)
                final_clip = CompositeVideoClip([bg_clip, txt_clip])
            except Exception as e:
                logger.warning(f"TextClip failed (ImageMagick missing?). Error: {e}")
                # Try PIL fallback for test
                txt_clip = self._create_text_clip_pil(text, 5)
                if txt_clip:
                    final_clip = CompositeVideoClip([bg_clip, txt_clip])
                else:
                    final_clip = bg_clip

            # 3. Write file
            final_clip.write_videofile(output_path, fps=24)
            logger.info("Done.")
        finally:
            # Ensure clips are closed to release file handles
            if final_clip:
                final_clip.close()

    def _create_text_clip_pil(self, text, duration, color="yellow", font_size=120):
        """
        Creates a text clip using PIL (no ImageMagick dependency).
        """
        try:
            # Create a transparent image
            img = PIL.Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            draw = PIL.ImageDraw.Draw(img)

            # Try to load a font from the local 'fonts' directory first
            font_dir = os.path.join(os.path.dirname(__file__), "..", "fonts")
            font_paths = [
                os.path.join(font_dir, "LiberationSans-Bold.ttf"),
                "C:/Windows/Fonts/arialbd.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/seguiemj.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "LiberationSans-Bold",
                "Arial.ttf",
                "sans-serif",
            ]
            font = None
            for p in font_paths:
                try:
                    if os.path.exists(p):
                        font = PIL.ImageFont.truetype(p, font_size)
                        break
                except Exception:
                    continue

            if not font:
                logger.warning("No suitable font found. Loading default.")
                font = PIL.ImageFont.load_default()

            # Measure text
            try:
                # Newer versions of Pillow
                bbox = draw.textbbox((0, 0), text, font=font)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
            except AttributeError:
                # Older versions
                w, h = draw.textsize(text, font=font)

            # Calculate position (center)
            x = (self.width - w) / 2
            y = (self.height - h) / 2

            # Draw background/outline (simple stroke)
            stroke_width = 3
            for offset_x in range(-stroke_width, stroke_width + 1):
                for offset_y in range(-stroke_width, stroke_width + 1):
                    draw.text(
                        (x + offset_x, y + offset_y), text, font=font, fill="black"
                    )

            # Draw main text
            draw.text((x, y), text, font=font, fill=color)

            # Convert to numpy array for MoviePy
            img_np = np.array(img)

            # Create ImageClip
            return ImageClip(img_np).set_duration(duration)

        except Exception as e:
            logger.error(f"PIL Text rendering failed: {e}")
            return None

    def assemble_short(
        self,
        audio_path,
        visual_paths,
        subtitles=None,
        output_path="output.mp4",
        quality="easy",
    ):
        """
        Assembles the final Shorts video, ensuring all resources are closed.
        """
        logger.info("Assembling video...")
        audio = None
        final_video = None
        try:
            # Normalize path for FFMPEG compatibility on Windows
            output_path = os.path.abspath(output_path).replace("\\", "/")
            audio_path = os.path.abspath(audio_path).replace("\\", "/")

            # 1. Audio
            audio = AudioFileClip(audio_path)
            total_duration = audio.duration

            # 2. Visuals
            clips = []
            current_duration = 0

            if not visual_paths:
                logger.warning("No visuals provided. Using black screen.")
                clips.append(
                    ColorClip(
                        size=(self.width, self.height),
                        color=(0, 0, 0),
                        duration=total_duration,
                    )
                )
            else:
                from random import shuffle, uniform

                original_visuals = list(visual_paths)
                shuffle(original_visuals)
                visual_pool = list(original_visuals)

                # If the pool is smaller than needed, extend it by repeating the shuffled list
                # to avoid reshuffling during video generation.
                if visual_pool:
                    # Estimate clips needed. A clip's duration is uniform(3.0, 5.0).
                    # Use the minimum duration (3.0s) for a conservative estimate.
                    estimated_clips_needed = math.ceil(total_duration / 3.0)
                    if len(visual_pool) < estimated_clips_needed:
                        num_repeats = math.ceil(
                            estimated_clips_needed / len(visual_pool)
                        )
                        visual_pool = visual_pool * int(num_repeats)
                        shuffle(visual_pool)  # Shuffle the extended pool for variety

                while current_duration < total_duration:
                    if not visual_pool:
                        logger.warning(
                            "Visual pool ran out unexpectedly. "
                            "This might happen if source videos are very short. "
                            "Filling the rest with a black screen."
                        )
                        break

                    v_path = os.path.abspath(visual_pool.pop(0)).replace("\\", "/")
                    clip = None
                    try:
                        clip = VideoFileClip(v_path)
                        if clip.w / clip.h > self.width / self.height:
                            clip = clip.resize(height=self.height)
                        else:
                            clip = clip.resize(width=self.width)

                        clip = clip.crop(
                            x_center=clip.w / 2,
                            y_center=clip.h / 2,
                            width=self.width,
                            height=self.height,
                        )

                        target_clip_dur = uniform(3.0, 5.0)
                        start_t = 0
                        if clip.duration > target_clip_dur + 1.0:
                            start_t = uniform(0, clip.duration - target_clip_dur)

                        clip_duration = min(
                            clip.duration - start_t,
                            target_clip_dur,
                            total_duration - current_duration,
                        )

                        if clip_duration > 0.5:
                            sub_clip = clip.subclip(start_t, start_t + clip_duration)
                            clips.append(sub_clip)
                            current_duration += sub_clip.duration

                    except Exception as e:
                        logger.error(f"Error loading clip {v_path}: {e}")
                    finally:
                        if clip:
                            clip.close()  # Close each visual clip after processing

            if not clips:  # Safety net if all visuals failed
                clips.append(
                    ColorClip(
                        size=(self.width, self.height),
                        color=(0, 0, 0),
                        duration=total_duration,
                    )
                )

            final_video = concatenate_videoclips(clips, method="compose")
            final_video = final_video.set_audio(audio)

            # 3. Subtitles
            if subtitles:
                logger.info("Adding subtitles...")
                text_clips = []
                for word in subtitles:
                    txt, start, end = word["word"], word["start"], word["end"]
                    duration = max(0.1, end - start)
                    txt_clip = self._create_text_clip_pil(txt, duration)
                    if txt_clip:
                        txt_clip = txt_clip.set_start(start).set_position("center")
                        text_clips.append(txt_clip)

                if text_clips:
                    final_video = CompositeVideoClip([final_video] + text_clips)

            # Write
            preset = "faster" if quality == "easy" else "medium"
            logger.info(f"Writing video with preset: {preset}")
            final_video.write_videofile(
                output_path,
                fps=24,
                audio_codec="aac",
                preset=preset,
                threads=12,
            )
            logger.info(f"Video saved to {output_path}")

        finally:
            # Explicitly close all major clips to release file handles
            if audio:
                audio.close()
            if final_video:
                final_video.close()
            logger.info("Video rendering process finished and resources released.")


if __name__ == "__main__":
    renderer = VideoRenderer()
    # Example of how to run (requires test files)
    # renderer.assemble_short("path/to/audio.mp3", ["path/to/video1.mp4"], output_path="test_output.mp4")
