"""
main.py — YouTube Shorts Agent
Orchestrates the full pipeline: Topic → Script → Voiceover → Video → Upload

Usage:
  # Interactive mode (prompts for topic)
  python main.py

  # Direct mode
  python main.py --topic "Why do cats purr" --style educational --upload

  # Skip upload (create video only)
  python main.py --topic "5 sleep hacks" --no-upload

  # List available ElevenLabs voices
  python main.py --list-voices
"""

import os
import re
import json
import argparse
from datetime import datetime

import config
from script_generator import generate_script
from voiceover import generate_voiceover
from video_creator import create_video
from youtube_uploader import upload_video


STYLES = ["educational", "motivational", "story", "news"]

BANNER = """
╔══════════════════════════════════════════════════════╗
║         🎬  YouTube Shorts Agent  🎬                ║
║   Topic → Script → Voice → Video → YouTube         ║
╚══════════════════════════════════════════════════════╝
"""


def safe_filename(text: str) -> str:
    """Convert text to a safe filename."""
    clean = re.sub(r"[^\w\s-]", "", text.lower())
    clean = re.sub(r"[\s-]+", "_", clean).strip("_")
    return clean[:50]


def run_pipeline(
    topic: str,
    style: str = "educational",
    duration: int = 45,
    privacy: str = "private",
    upload: bool = True,
    save_script: bool = True,
) -> dict:
    """
    Run the full pipeline for a single video.

    Args:
        topic: Video topic / idea
        style: Script style (educational, motivational, story, news)
        duration: Target video duration in seconds
        privacy: YouTube privacy (private, unlisted, public)
        upload: Whether to upload to YouTube
        save_script: Save script JSON to output folder

    Returns:
        dict with paths and YouTube URL (if uploaded)
    """
    config.validate_config()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = safe_filename(topic)
    base_name = f"{timestamp}_{slug}"

    result = {
        "topic": topic,
        "style": style,
        "timestamp": timestamp,
        "script_path": None,
        "audio_path": None,
        "video_path": None,
        "youtube_url": None,
    }

    # ── Step 1: Generate Script ─────────────────────────────────────────────
    print("\n📝 STEP 1/4 — Generating script...")
    script = generate_script(topic, style=style, duration_seconds=duration)

    if save_script:
        script_path = os.path.join(config.OUTPUT_DIR, f"{base_name}_script.json")
        with open(script_path, "w") as f:
            json.dump(script, f, indent=2)
        result["script_path"] = script_path
        print(f"   Script saved: {script_path}")

    # ── Step 2: Generate Voiceover ──────────────────────────────────────────
    print("\n🎙️  STEP 2/4 — Generating voiceover...")
    audio_path = generate_voiceover(
        script["narration"],
        output_filename=f"{base_name}_voice.mp3",
    )
    result["audio_path"] = audio_path

    # ── Step 3: Create Video ────────────────────────────────────────────────
    print("\n🎬 STEP 3/4 — Creating video...")
    video_path = create_video(
        script,
        audio_path,
        output_filename=f"{base_name}.mp4",
    )
    result["video_path"] = video_path

    # ── Step 4: Upload to YouTube ───────────────────────────────────────────
    if upload:
        print("\n📤 STEP 4/4 — Uploading to YouTube...")
        youtube_url = upload_video(video_path, script, privacy=privacy)
        result["youtube_url"] = youtube_url
    else:
        print("\n⏭️  STEP 4/4 — Skipping upload (--no-upload flag)")

    # ── Summary ─────────────────────────────────────────────────────────────
    print("\n" + "═" * 56)
    print("🎉  PIPELINE COMPLETE")
    print("═" * 56)
    print(f"  Topic:    {topic}")
    print(f"  Title:    {script.get('title', '')}")
    if result["video_path"]:
        size_mb = os.path.getsize(result["video_path"]) / (1024**2)
        print(f"  Video:    {result['video_path']} ({size_mb:.1f} MB)")
    if result["youtube_url"]:
        print(f"  YouTube:  {result['youtube_url']}")
    print("═" * 56)

    return result


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    print(BANNER)

    parser = argparse.ArgumentParser(
        description="YouTube Shorts Agent — create and upload short videos automatically"
    )
    parser.add_argument("--topic", type=str, help="Video topic or idea")
    parser.add_argument(
        "--style",
        type=str,
        choices=STYLES,
        default="educational",
        help=f"Script style: {', '.join(STYLES)} (default: educational)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=45,
        help="Target video duration in seconds (default: 45)",
    )
    parser.add_argument(
        "--privacy",
        type=str,
        choices=["private", "unlisted", "public"],
        default="private",
        help="YouTube privacy setting (default: private — review before publishing!)",
    )
    parser.add_argument(
        "--no-upload",
        dest="upload",
        action="store_false",
        help="Create video without uploading to YouTube",
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List available ElevenLabs voices and exit",
    )
    args = parser.parse_args()

    if args.list_voices:
        config.validate_config()
        from voiceover import list_voices
        print("Available ElevenLabs voices:")
        for v in list_voices():
            print(f"  {v['name']:35s}  {v['voice_id']}")
        return

    # Interactive topic prompt if not provided
    topic = args.topic
    if not topic:
        topic = input("📌 Enter your video topic or idea: ").strip()
        if not topic:
            print("❌ No topic provided. Exiting.")
            return

    # Interactive style selection if default
    if not args.topic:
        print(f"\nAvailable styles: {', '.join(STYLES)}")
        style_input = input(f"🎨 Style [{args.style}]: ").strip().lower()
        if style_input in STYLES:
            args.style = style_input

    run_pipeline(
        topic=topic,
        style=args.style,
        duration=args.duration,
        privacy=args.privacy,
        upload=args.upload,
    )


if __name__ == "__main__":
    main()
