from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    TextClip,
    ColorClip,
    CompositeVideoClip,
    concatenate_videoclips,
)
import os


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
        print(f"Rendering test video to {output_path}...")

        # 1. Create a background (solid color for now, logic for file later)
        # Duration: 5 seconds
        bg_clip = ColorClip(
            size=(self.width, self.height), color=(0, 0, 255), duration=5
        )

        # 2. Add Text
        # Note: TextClip requires ImageMagick binary on Windows usually.
        # Fallback to simple composition if TextClip fails might be needed,
        # but for this specific "Text on Screen" requirement, ImageMagick is crucial.
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
            print(f"Warning: TextClip failed (ImageMagick missing?). Error: {e}")
            print("Rendering without text.")


from moviepy.editor import *
import os


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
        print(f"Rendering test video to {output_path}...")

        # 1. Create a background (solid color for now, logic for file later)
        # Duration: 5 seconds
        bg_clip = ColorClip(
            size=(self.width, self.height), color=(0, 0, 255), duration=5
        )

        # 2. Add Text
        # Note: TextClip requires ImageMagick binary on Windows usually.
        # Fallback to simple composition if TextClip fails might be needed,
        # but for this specific "Text on Screen" requirement, ImageMagick is crucial.
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
            print(f"Warning: TextClip failed (ImageMagick missing?). Error: {e}")
            print("Rendering without text.")
            final_clip = bg_clip

        # 3. Write file
        final_clip.write_videofile(output_path, fps=24)
        print("Done.")

    def assemble_short(
        self, audio_path, visual_paths, subtitles=None, output_path="output.mp4"
    ):
        """
        Assembles the final Shorts video.
        args:
            audio_path: Path to mp3 voiceover.
            visual_paths: List of paths to background videos.
            subtitles: List of word objects (optional).
            output_path: Destination file.
        """
        print("Assembling video...")

        # 1. Audio
        audio = AudioFileClip(audio_path)
        total_duration = audio.duration

        # 2. Visuals
        clips = []
        current_duration = 0
        visual_index = 0

        # Simple logic: Cycle through visuals until we cover the audio duration
        while current_duration < total_duration:
            if visual_index >= len(visual_paths):
                visual_index = 0  # Loop visuals if not enough

            v_path = visual_paths[visual_index]
            try:
                clip = VideoFileClip(v_path)

                # Resize to fill 9:16 (vertical)
                # Target is self.width x self.height (e.g., 1080x1920)
                # First resize keeping aspect ratio
                if clip.w / clip.h > self.width / self.height:
                    # Video is wider than target aspect -> resize by height
                    clip = clip.resize(height=self.height)
                else:
                    # Video is taller/thinner -> resize by width
                    clip = clip.resize(width=self.width)

                # Center crop
                clip = clip.crop(
                    x1=clip.w / 2 - self.width / 2,
                    width=self.width,
                    y1=clip.h / 2 - self.height / 2,
                    height=self.height,
                )

                # Determine how long this clip should play
                # For now, let's say each visual plays for ~3-5s or until end of audio
                clip_duration = min(clip.duration, 4.0)

                remaining_audio = total_duration - current_duration
                if remaining_audio < clip_duration:
                    clip_duration = remaining_audio

                clip = clip.subclip(0, clip_duration).set_duration(clip_duration)
                clips.append(clip)
                current_duration += clip_duration
                visual_index += 1

            except Exception as e:
                print(f"Error loading clip {v_path}: {e}")
                # Fallback to black screen if visual fails
                if not clips and current_duration == 0:
                    clips.append(
                        ColorClip(
                            size=(self.width, self.height),
                            color=(0, 0, 0),
                            duration=total_duration,
                        )
                    )
                    current_duration = total_duration

        final_video = concatenate_videoclips(clips, method="compose")
        final_video = final_video.set_audio(audio)

        # 3. Subtitles (Basic Overlay)
        if subtitles:
            # Very basic implementation: TextClip for chunks of words
            # Real "MrBeast" style needs complex dynamic positioning logic
            print("Adding subtitles...")
            text_clips = []
            for word in subtitles:
                txt = word["word"]
                start = word["start"]
                end = word["end"]
                duration = end - start

                try:
                    # Ensure font is available or use default
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
                    text_clips.append(txt_clip)
                except Exception as e:
                    print(f"Subtitle error: {e}")

            if text_clips:
                final_video = CompositeVideoClip([final_video] + text_clips)

        # Write
        final_video.write_videofile(
            output_path, fps=24, codec="libx264", audio_codec="aac"
        )
        print(f"Video saved to {output_path}")


if __name__ == "__main__":
    renderer = VideoRenderer()
    renderer.create_test_video("test_short.mp4")
