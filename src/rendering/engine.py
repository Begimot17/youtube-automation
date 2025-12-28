import logging
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

    def _create_text_clip_pil(self, text, duration, color="yellow", font_size=80):
        """
        Creates a text clip using PIL (no ImageMagick dependency).
        """
        try:
            # Create a transparent image
            img = PIL.Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            draw = PIL.ImageDraw.Draw(img)

            # Try to load a font
            font = None
            font_paths = [
                "C:/Windows/Fonts/arialbd.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/seguiemj.ttf",
            ]
            for p in font_paths:
                if os.path.exists(p):
                    try:
                        font = PIL.ImageFont.truetype(p, font_size)
                        break
                    except Exception:
                        continue

            if not font:
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
        Assembles the final Shorts video.
        """
        logger.info("Assembling video...")

        # Normalize path for FFMPEG compatibility on Windows
        output_path = os.path.abspath(output_path).replace("\\", "/")
        audio_path = os.path.abspath(audio_path).replace("\\", "/")

        # 1. Audio
        audio = AudioFileClip(audio_path)
        total_duration = audio.duration

        # 2. Visuals
        clips = []
        current_duration = 0
        visual_index = 0

        if not visual_paths:
            logger.warning("No visuals provided. Using black screen.")
            clips.append(
                ColorClip(
                    size=(self.width, self.height),
                    color=(0, 0, 0),
                    duration=total_duration,
                )
            )
            current_duration = total_duration

        # Cycle through visuals until we cover the audio duration
        max_attempts = len(visual_paths) * 2 + 10
        attempt_count = 0

        while current_duration < total_duration and attempt_count < max_attempts:
            if visual_index >= len(visual_paths):
                visual_index = 0

            v_path = os.path.abspath(visual_paths[visual_index]).replace("\\", "/")
            visual_index += 1
            attempt_count += 1

            try:
                clip = VideoFileClip(v_path)

                # Resize to fill 9:16
                if clip.w / clip.h > self.width / self.height:
                    clip = clip.resize(height=self.height)
                else:
                    clip = clip.resize(width=self.width)

                # Center crop
                clip = clip.crop(
                    x1=clip.w / 2 - self.width / 2,
                    width=self.width,
                    y1=clip.h / 2 - self.height / 2,
                    height=self.height,
                )

                # Each visual plays for ~4s
                clip_duration = min(clip.duration, 4.0)
                if clip_duration < 1.0:
                    clip_duration = clip.duration

                remaining_audio = total_duration - current_duration
                if remaining_audio < clip_duration:
                    clip_duration = remaining_audio

                if clip_duration > 0:
                    clip = clip.subclip(0, clip_duration).set_duration(clip_duration)
                    clips.append(clip)
                    current_duration += clip_duration

            except Exception as e:
                logger.error(f"Error loading clip {v_path}: {e}")

        # Gap filler
        if current_duration < total_duration:
            logger.warning(
                f"Filling gap of {total_duration - current_duration}s with black."
            )
            clips.append(
                ColorClip(
                    size=(self.width, self.height),
                    color=(0, 0, 0),
                    duration=total_duration - current_duration,
                )
            )

        final_video = concatenate_videoclips(clips, method="compose")
        final_video = final_video.set_audio(audio)

        # 3. Subtitles
        if subtitles:
            logger.info("Adding subtitles...")
            text_clips = []
            for word in subtitles:
                txt = word["word"]
                start = word["start"]
                end = word["end"]
                duration = max(0.1, end - start)

                # Try TextClip (ImageMagick) first, then fallback to PIL
                txt_clip = None
                try:
                    txt_clip = TextClip(
                        txt,
                        fontsize=80,
                        color="yellow",
                        stroke_color="black",
                        stroke_width=2,
                        font="Arial-Bold",
                        method="caption",
                        size=(self.width * 0.8, None),
                    )
                    txt_clip = (
                        txt_clip.set_position(("center", "center"))
                        .set_start(start)
                        .set_duration(duration)
                    )
                except Exception:
                    # Fallback to PIL
                    txt_clip = self._create_text_clip_pil(txt, duration)
                    if txt_clip:
                        txt_clip = txt_clip.set_start(start).set_position("center")

                if txt_clip:
                    text_clips.append(txt_clip)

            if text_clips:
                final_video = CompositeVideoClip([final_video] + text_clips)

        # Write
        preset = "ultrafast" if quality == "easy" else "medium"
        logger.info(f"Writing video with preset: {preset}")

        final_video.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            preset=preset,
            threads=4,
        )
        logger.info(f"Video saved to {output_path}")


if __name__ == "__main__":
    renderer = VideoRenderer()
