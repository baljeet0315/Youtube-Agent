"""
video_creator.py — Assemble the final Short.

Phase 2 pipeline (per scene):
  AI image (visuals.py) → Ken Burns motion  ─┐
  or Pexels stock clip (fallback)            ├─ concat → captions → voice + music → mp4
  or colour card (last resort)              ─┘

Scene cut points come from the voice word timestamps (each scene ends where its
narration_excerpt ends). If timestamps are missing, scenes are distributed
proportionally like v1.
"""
import os
import re
import math
import requests
import numpy as np

# Pillow 10+ compatibility (ANTIALIAS was removed)
from PIL import Image
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import (
    VideoClip, VideoFileClip, AudioFileClip, CompositeVideoClip, CompositeAudioClip,
    concatenate_videoclips, ColorClip,
)
import moviepy.audio.fx.all as afx
import agent_config as config


# ── Pexels (stock fallback) ─────────────────────────────────────────────────

def fetch_pexels_video(query: str, clip_index: int = 0, min_duration: float = 5.0) -> str | None:
    headers = {"Authorization": config.PEXELS_API_KEY}
    params = {"query": query, "per_page": 10, "orientation": "portrait", "size": "medium"}
    try:
        response = requests.get("https://api.pexels.com/videos/search",
                                headers=headers, params=params, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"⚠️  Pexels error for '{query}': {e}")
        return None

    videos = response.json().get("videos", [])
    if not videos:
        print(f"⚠️  No Pexels results for '{query}'")
        return None

    chosen = None
    for video in videos:
        if video["duration"] < min_duration:
            continue
        files = sorted(video.get("video_files", []), key=lambda f: f.get("width", 0))
        for f in files:
            if f.get("width", 9999) <= 1080:
                chosen = f
                break
        if chosen:
            break
    if not chosen and videos:
        files = videos[0].get("video_files", [])
        chosen = files[0] if files else None
    if not chosen:
        return None

    safe_query = re.sub(r"[^a-z0-9]+", "_", query.lower())[:30]
    output_path = os.path.join(config.OUTPUT_DIR, "footage", f"{safe_query}_{clip_index}.mp4")
    if os.path.exists(output_path):
        return output_path

    print(f"  ⬇️  Downloading footage: '{query}'")
    r = requests.get(chosen["link"], stream=True, timeout=60)
    with open(output_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 64):
            f.write(chunk)
    return output_path


def stock_clip(scene: dict, duration: float) -> VideoClip | None:
    """9:16 crop of a Pexels clip, looped/trimmed to `duration`."""
    query = scene.get("visual_query") or "nature landscape"
    path = fetch_pexels_video(query, clip_index=scene.get("id", 0))
    if not path or not os.path.exists(path):
        return None
    W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    raw = VideoFileClip(path)
    if raw.duration < duration:
        raw = concatenate_videoclips([raw] * math.ceil(duration / raw.duration))
    raw = raw.subclip(0, duration)
    if raw.w / raw.h > W / H:
        new_h, new_w = H, int(raw.w * (H / raw.h))
    else:
        new_w, new_h = W, int(raw.h * (W / raw.w))
    raw = raw.resize((new_w, new_h)).crop(x_center=new_w / 2, y_center=new_h / 2, width=W, height=H)
    return raw.set_fps(config.VIDEO_FPS)


def color_card(duration: float) -> VideoClip:
    return ColorClip(size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT),
                     color=(20, 30, 60), duration=duration).set_fps(config.VIDEO_FPS)


# ── Ken Burns on a still image ──────────────────────────────────────────────

ZOOM_AMOUNT = 0.12   # 12% travel over the scene


def ken_burns_clip(image_path: str, duration: float, motion: str = "zoom_in") -> VideoClip:
    """Animate a still: slow zoom or pan, eased. Frame-by-frame with Pillow
    (cheap: one crop+resize per frame, no video decoding)."""
    W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    img = Image.open(image_path).convert("RGB")
    iw, ih = img.size

    # Crop source to exactly 9:16 first so all motion math is uniform
    if iw / ih > W / H:
        nw = int(ih * W / H)
        img = img.crop(((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih))
    else:
        nh = int(iw * H / W)
        img = img.crop((0, (ih - nh) // 2, iw, (ih - nh) // 2 + nh))
    iw, ih = img.size

    def box_at(p: float):
        if motion == "zoom_in":
            s = 1.0 - ZOOM_AMOUNT * p
        elif motion == "zoom_out":
            s = 1.0 - ZOOM_AMOUNT * (1.0 - p)
        elif motion == "static":
            s = 1.0
        else:                       # pans use a fixed, smaller window
            s = 1.0 - ZOOM_AMOUNT
        bw, bh = iw * s, ih * s
        if motion == "pan_left":
            x = (iw - bw) * (1.0 - p)
        elif motion == "pan_right":
            x = (iw - bw) * p
        else:
            x = (iw - bw) / 2
        y = (ih - bh) / 2
        return (x, y, x + bw, y + bh)

    def make_frame(t: float):
        p = 0.0 if duration <= 0 else min(1.0, t / duration)
        p = p * p * (3 - 2 * p)                     # smoothstep ease-in-out
        frame = img.resize((W, H), Image.LANCZOS, box=box_at(p))
        return np.asarray(frame)

    return VideoClip(make_frame, duration=duration).set_fps(config.VIDEO_FPS)


# ── Scene timing from word timestamps ───────────────────────────────────────

def _norm_tokens(text: str) -> list:
    return [t for t in re.sub(r"[^\w'\s-]", " ", text.lower()).split() if t]


def scene_timings(script: dict, words: list, audio_duration: float) -> list:
    """
    Return [(start, end), ...] per scene.
    Uses word timestamps when every scene's excerpt is verified and the word
    counts line up; otherwise proportional to duration hints (v1 behaviour).
    """
    scenes = script.get("scenes", [])
    n = len(scenes)

    def proportional():
        total = sum(float(s.get("duration_hint") or s.get("duration") or 5) for s in scenes) or 1
        out, t = [], 0.0
        for s in scenes:
            d = float(s.get("duration_hint") or s.get("duration") or 5) / total * audio_duration
            out.append((t, t + d))
            t += d
        return out

    if not words or not all(s.get("excerpt_verified") for s in scenes):
        return proportional()

    word_tokens = [_norm_tokens(w["text"]) for w in words]
    # flatten: one timestamp per normalized token (hyphenated words may split)
    flat = []
    for w, toks in zip(words, word_tokens):
        for tk in toks:
            flat.append((tk, w["start"], w["end"]))
    if not flat:
        return proportional()

    out, ptr = [], 0
    for i, s in enumerate(scenes):
        toks = _norm_tokens(s.get("narration_excerpt", ""))
        if not toks:
            return proportional()
        end_idx = ptr + len(toks) - 1
        if end_idx >= len(flat):
            return proportional()
        # light sanity check: first and last token should match
        if flat[ptr][0] != toks[0] or flat[end_idx][0] != toks[-1]:
            return proportional()
        start = 0.0 if i == 0 else out[-1][1]
        end = audio_duration if i == n - 1 else flat[end_idx][2]
        out.append((start, max(end, start + 0.5)))
        ptr = end_idx + 1
    return out


# ── Main builder ────────────────────────────────────────────────────────────

def create_video(script: dict, audio_path: str, output_filename: str = "final_video.mp4",
                 words: list | None = None, images: dict | None = None,
                 music_path: str | None = None) -> str:
    """
    Assemble the final video.

    script      : schema v2 (v1 still works — no images/words → stock path)
    audio_path  : voiceover mp3
    words       : [{text,start,end}] from voiceover timestamps (optional)
    images      : {scene_id: image_path or None} from visuals.py (optional)
    music_path  : background track (optional)
    """
    from voiceover import get_audio_duration, estimate_words

    W, H, FPS = config.VIDEO_WIDTH, config.VIDEO_HEIGHT, config.VIDEO_FPS
    output_path = os.path.join(config.OUTPUT_DIR, "videos", output_filename)
    images = images or {}

    print("\n🎬 Building video...")
    audio_duration = get_audio_duration(audio_path)
    tail = float(getattr(config, "TAIL_SECONDS", 2.0))
    total_duration = audio_duration + tail
    print(f"   Voice {audio_duration:.1f}s + tail {tail:.1f}s = {total_duration:.1f}s")

    scenes = script.get("scenes", [])
    if not scenes:
        raise ValueError("Script has no scenes defined")

    timings = scene_timings(script, words or [], audio_duration)
    timed = words and all(s.get("excerpt_verified") for s in scenes)
    print(f"   Scene cuts: {'from word timestamps' if timed else 'proportional'}")

    # ── Scenes ──────────────────────────────────────────────────────────
    scene_clips = []
    for i, (scene, (start, end)) in enumerate(zip(scenes, timings)):
        dur = round(end - start, 3)
        if i == len(scenes) - 1:
            dur += tail
        sid = scene.get("id", i + 1)
        img_path = images.get(sid) or images.get(str(sid))
        src = "image" if img_path and os.path.exists(img_path) else "stock"
        print(f"   Scene {sid}/{len(scenes)} [{src}] {dur:.1f}s  {scene.get('motion', '')}")

        clip = None
        if src == "image":
            try:
                clip = ken_burns_clip(img_path, dur, scene.get("motion", "zoom_in"))
            except Exception as e:
                print(f"   ⚠️  image scene failed ({e}) — trying stock")
        if clip is None:
            try:
                clip = stock_clip(scene, dur)
            except Exception as e:
                print(f"   ⚠️  stock scene failed ({e})")
        if clip is None:
            clip = color_card(dur)
        scene_clips.append(clip)

    video = concatenate_videoclips(scene_clips, method="compose")

    # Exact length + fade to black at the very end
    if video.duration > total_duration:
        video = video.subclip(0, total_duration)
    elif video.duration < total_duration:
        video = concatenate_videoclips([video, color_card(total_duration - video.duration)], method="compose")
    video = video.fadeout(min(1.0, tail))

    # ── Captions ────────────────────────────────────────────────────────
    if getattr(config, "CAPTIONS_ENABLED", True):
        try:
            from captions import build_caption_clips
            cap_words = words or estimate_words(script.get("narration", ""), audio_duration)
            cap_clips = build_caption_clips(cap_words, W, H, FPS)
            if cap_clips:
                video = CompositeVideoClip([video] + cap_clips, size=(W, H)).set_duration(total_duration)
                print(f"   Captions: {len(cap_clips)} word frames")
        except Exception as e:
            print(f"   ⚠️  captions skipped: {e}")

    # ── Audio: voice + music ────────────────────────────────────────────
    voice = AudioFileClip(audio_path)
    tracks = [voice]
    music = None
    if music_path and os.path.exists(music_path):
        try:
            music = AudioFileClip(music_path)
            if music.duration < total_duration:
                music = afx.audio_loop(music, duration=total_duration)
            else:
                music = music.subclip(0, total_duration)
            music = music.fx(afx.volumex, config.MUSIC_VOLUME).fx(afx.audio_fadeout, min(2.0, tail + 0.5))
            tracks.append(music)
            print(f"   Music: {os.path.basename(music_path)} @ {config.MUSIC_VOLUME:.0%}")
        except Exception as e:
            print(f"   ⚠️  music skipped: {e}")
            music = None
    final_audio = CompositeAudioClip(tracks).set_duration(total_duration) if len(tracks) > 1 else voice
    final = video.set_audio(final_audio)

    # ── Render ──────────────────────────────────────────────────────────
    print(f"   Rendering to {output_path}...")
    final.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        audio_fps=44100,
        temp_audiofile=os.path.join(config.OUTPUT_DIR, "temp_audio.aac"),
        remove_temp=True,
        threads=4,
        preset="medium",
        logger="bar",
    )

    for c in scene_clips + [voice, final]:
        try:
            c.close()
        except Exception:
            pass
    if music is not None:
        try:
            music.close()
        except Exception:
            pass

    print(f"✅ Video created: {output_path}")
    return output_path


if __name__ == "__main__":
    import json
    import sys
    config.validate_config()
    if len(sys.argv) < 3:
        print("Usage: python video_creator.py <script.json> <audio.mp3> [words.json]")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        script = json.load(f)
    words = None
    if len(sys.argv) > 3:
        with open(sys.argv[3]) as f:
            words = json.load(f)
    create_video(script, sys.argv[2], words=words)
