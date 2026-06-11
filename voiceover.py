"""
voiceover.py — Generate voiceover audio using ElevenLabs TTS
"""
import os
import requests
import agent_config as config


def generate_voiceover(text: str, output_filename: str = "voiceover.mp3") -> str:
    """
    Convert text to speech using ElevenLabs API.

    Args:
        text: The narration script text
        output_filename: Output filename (saved in OUTPUT_DIR/audio/)

    Returns:
        Full path to the generated MP3 file
    """
    output_path = os.path.join(config.OUTPUT_DIR, "audio", output_filename)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": config.ELEVENLABS_API_KEY,
    }

    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.3,
            "use_speaker_boost": True,
        },
    }

    print(f"\n🎙️  Generating voiceover ({len(text.split())} words)...")

    response = requests.post(url, json=payload, headers=headers, timeout=60)

    if response.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs API error {response.status_code}: {response.text}"
        )

    with open(output_path, "wb") as f:
        f.write(response.content)

    file_size_kb = os.path.getsize(output_path) / 1024
    print(f"✅ Voiceover saved: {output_path} ({file_size_kb:.1f} KB)")

    return output_path


def get_audio_duration(audio_path: str) -> float:
    """
    Get the duration of an audio file in seconds.
    Uses moviepy to avoid adding mutagen as a dependency.
    """
    try:
        from moviepy.editor import AudioFileClip
        clip = AudioFileClip(audio_path)
        duration = clip.duration
        clip.close()
        return duration
    except Exception as e:
        print(f"⚠️  Could not determine audio duration: {e}")
        return 45.0  # Fallback estimate


def list_voices() -> list:
    """
    Fetch available voices from ElevenLabs account.
    Returns list of dicts with 'voice_id' and 'name'.
    """
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": config.ELEVENLABS_API_KEY}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    voices = response.json().get("voices", [])
    return [{"voice_id": v["voice_id"], "name": v["name"]} for v in voices]


if __name__ == "__main__":
    config.validate_config()
    print("Available voices:")
    for v in list_voices():
        print(f"  {v['name']:30s} {v['voice_id']}")
