"""
video_creator.py — Fetch stock footage from Pexels and assemble final video with MoviePy
"""
import os
import math
import requests

# Patch for Pillow 10+ compatibility (ANTIALIAS was removed)
from PIL import Image
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
    ColorClip,
    TextClip,
)
from moviepy.config import change_settings
import agent_config as config


# ── Pexels ──────────────────────────────────────────────────────────────────

def fetch_pexels_video(query: str, clip_index: int = 0, min_duration: float = 5.0) -> str:
    """
    Search Pexels for a video clip matching the query.

    Args:
        query: Search term (e.g. "cat sleeping cozy")
        clip_index: Which result to use (0 = first best match)
        min_duration: Skip clips shorter than this

    Returns:
        Path to downloaded video file
    """
    headers = {"Authorization": config.PEXELS_API_KEY}
    params = {
        "query": query,
        "per_page": 10,
        "orientation": "portrait",  # Vertical/short-form
        "size": "medium",
    }

    try:
        response = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params=params,
            timeout=15,
        )
        response.raise_for_status()
    except Exception as e:
        print(f"⚠️  Pexels error for '{query}': {e} — using fallback color clip")
        return None
    data = response.json()

    videos = data.get("videos", [])
    if not videos:
        print(f"⚠️  No Pexels results for '{query}', using fallback color clip")
        return None

    # Pick a usable clip (prefer portrait, min duration)
    chosen_video_file = None
    for video in videos:
        if video["duration"] < min_duration:
            continue
        # Prefer HD portrait files
        files = sorted(
            video.get("video_files", []),
            key=lambda f: f.get("width", 0),
        )
        for f in files:
            if f.get("width", 9999) <= 1080:
                chosen_video_file = f
                break
        if chosen_video_file:
            break

    if not chosen_video_file and videos:
        # Fallback: just take any file from first result
        files = videos[0].get("video_files", [])
        if files:
            chosen_video_file = files[0]

    if not chosen_video_file:
        return None

    # Download the file
    safe_query = query.replace(" ", "_")[:30]
    filename = f"{safe_query}_{clip_index}.mp4"
    output_path = os.path.join(config.OUTPUT_DIR, "footage", filename)

    if os.path.exists(output_path):
        print(f"  ♻️  Using cached: {filename}")
        return output_path

    video_url = chosen_video_file["link"]
    print(f"  ⬇️  Downloading footage: '{query}'")
    r = requests.get(video_url, stream=True, timeout=60)
    with open(output_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 64):
            f.write(chunk)

    return output_path


# ── Text Overlays ────────────────────────────────────────────────────────────

def make_caption_clip(text: str, duration: float, video_w: int, video_h: int) -> TextClip:
    """Create a styled caption text overlay."""
    try:
        clip = (
            TextClip(
                text,
                fontsize=72,
                color="white",
                font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                stroke_color="black",
                stroke_width=3,
                method="caption",
                size=(video_w - 80, None),
                align="center",
            )
            .set_duration(duration)
            .set_position(("center", int(video_h * 0.75)))
        )
        return clip
    except Exception as e:
        print(f"  ⚠️  Caption rendering issue: {e} — skipping caption")
        return None


# ── Scene Assembly ───────────────────────────────────────────────────────────

def build_scene_clip(scene: dict, scene_duration: float) -> VideoFileClip:
    """
    Build a single scene: fetch/crop stock footage + caption overlay.
    Falls back to a colored clip if footage is unavailable.
    """
    query = scene.get("visual_query", "nature landscape")
    caption = scene.get("caption", "")

    footage_path = fetch_pexels_video(query, clip_index=scene.get("timestamp", 0))

    target_w = config.VIDEO_WIDTH
    target_h = config.VIDEO_HEIGHT

    # ── Build base video clip ────────────────────────────────────────────────
    if footage_path and os.path.exists(footage_path):
        raw = VideoFileClip(footage_path)

        # Loop if shorter than needed
        if raw.duration < scene_duration:
            repeats = math.ceil(scene_duration / raw.duration)
            from moviepy.editor import concatenate_videoclips
            raw = concatenate_videoclips([raw] * repeats)

        raw = raw.subclip(0, scene_duration)

        # Crop/resize to target aspect ratio (9:16)
        raw_ratio = raw.w / raw.h
        target_ratio = target_w / target_h

        if raw_ratio > target_ratio:
            # Too wide — scale by height then crop width
            new_h = target_h
            new_w = int(raw.w * (target_h / raw.h))
        else:
            # Too tall — scale by width then crop height
            new_w = target_w
            new_h = int(raw.h * (target_w / raw.w))

        raw = raw.resize((new_w, new_h))
        raw = raw.crop(
            x_center=new_w / 2,
            y_center=new_h / 2,
            width=target_w,
            height=target_h,
        )
        base = raw.set_fps(config.VIDEO_FPS)
    else:
        # Fallback: solid dark-blue background
        base = ColorClip(
            size=(target_w, target_h),
            color=(20, 30, 60),
            duration=scene_duration,
        ).set_fps(config.VIDEO_FPS)

    # ── Add caption overlay ──────────────────────────────────────────────────
    # TEMPORARILY DISABLED: ImageMagick/font issues on Railway. Re-enable once
    # caption rendering is fixed (see make_caption_clip).
    CAPTIONS_ENABLED = False

    if CAPTIONS_ENABLED and caption:
        caption_clip = make_caption_clip(caption, scene_duration, target_w, target_h)
        if caption_clip:
            return CompositeVideoClip([base, caption_clip])

    return base


# ── Main Video Builder ───────────────────────────────────────────────────────

def create_video(script: dict, audio_path: str, output_filename: str = "final_video.mp4") -> str:
    """
    Assemble the final video from script scenes + voiceover audio.

    Args:
        script: Script dict from script_generator.py
        audio_path: Path to voiceover MP3
        output_filename: Output filename (saved in OUTPUT_DIR/videos/)

    Returns:
        Full path to the rendered video file
    """
    output_path = os.path.join(config.OUTPUT_DIR, "videos", output_filename)

    print(f"\n🎬 Building video...")

    # Measure actual audio duration
    from voiceover import get_audio_duration
    audio_duration = get_audio_duration(audio_path)
    print(f"   Audio duration: {audio_duration:.1f}s")

    scenes = script.get("scenes", [])
    if not scenes:
        raise ValueError("Script has no scenes defined")

    # Distribute duration across scenes
    total_scene_declared = sum(s.get("duration", 5) for s in scenes)
    scene_clips = []

    for i, scene in enumerate(scenes):
        declared = scene.get("duration", 5)
        # Scale scene durations proportionally to match audio
        scene_dur = (declared / total_scene_declared) * audio_duration
        scene_dur = round(scene_dur, 2)

        print(f"   Scene {i+1}/{len(scenes)}: '{scene.get('visual_query', '')}' ({scene_dur:.1f}s)")
        clip = build_scene_clip(scene, scene_dur)
        scene_clips.append(clip)

    # Concatenate all scenes
    print("   Concatenating scenes...")
    video = concatenate_videoclips(scene_clips, method="compose")

    # Attach voiceover audio
    audio = AudioFileClip(audio_path)

    # Trim/pad video to match audio
    if video.duration > audio_duration:
        video = video.subclip(0, audio_duration)
    elif video.duration < audio_duration:
        pad = ColorClip(
            size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT),
            color=(20, 30, 60),
            duration=audio_duration - video.duration,
        ).set_fps(config.VIDEO_FPS)
        video = concatenate_videoclips([video, pad], method="compose")

    final = video.set_audio(audio)

    # Render
    print(f"   Rendering to {output_path}...")
    final.write_videofile(
        output_path,
        fps=config.VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=os.path.join(config.OUTPUT_DIR, "temp_audio.aac"),
        remove_temp=True,
        threads=4,
        logger="bar",
    )

    # Cleanup clips
    for c in scene_clips:
        try:
            c.close()
        except Exception:
            pass
    audio.close()
    final.close()

    print(f"✅ Video created: {output_path}")
    return output_path


if __name__ == "__main__":
    import json
    import sys
    config.validate_config()
    if len(sys.argv) < 3:
        print("Usage: python video_creator.py <script.json> <audio.mp3>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        script = json.load(f)
    create_video(script, sys.argv[2])
