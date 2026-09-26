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
        "model_id": getattr(config, "ELEVENLABS_MODEL", "eleven_multilingual_v2"),
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


DEFAULT_VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.3,
    "use_speaker_boost": True,
}


def _alignment_to_words(alignment: dict) -> list:
    """
    ElevenLabs returns character-level alignment:
      {"characters": [...], "character_start_times_seconds": [...], "character_end_times_seconds": [...]}
    Group consecutive non-whitespace characters into words with start/end.
    """
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    words, buf, w_start, w_end = [], [], None, None
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if buf:
                words.append({"text": "".join(buf), "start": float(w_start), "end": float(w_end)})
                buf, w_start = [], None
            continue
        if w_start is None:
            w_start = s
        w_end = e
        buf.append(ch)
    if buf:
        words.append({"text": "".join(buf), "start": float(w_start), "end": float(w_end)})
    return words


TTS_MODELS = {
    # id: (label, notes)
    "eleven_multilingual_v2": ("Multilingual v2", "29 languages, most stable. No Punjabi."),
    "eleven_v3": ("Eleven v3", "70+ languages incl. Punjabi. Most expressive, newest."),
    "eleven_turbo_v2_5": ("Turbo v2.5", "Fast, 32 languages incl. Hindi. No Punjabi."),
    "eleven_turbo_v2": ("Turbo v2 (English only)", "Fastest. English only."),
}


def generate_voiceover_with_timestamps(text: str, output_filename: str = "voiceover.mp3",
                                       voice_id: str = None, voice_settings: dict = None,
                                       model_id: str = None) -> tuple:
    """
    TTS + per-word timestamps via /with-timestamps.
    Returns (mp3_path, words) where words = [{text, start, end}, ...].
    Falls back to plain TTS with words=[] if the timestamps endpoint fails.
    Also writes <output_filename>.words.json next to the mp3.
    """
    import json, base64

    voice_id = voice_id or config.ELEVENLABS_VOICE_ID
    model_id = model_id or getattr(config, "ELEVENLABS_MODEL", "eleven_multilingual_v2")
    # Only keep known keys, clamp to 0..1
    clean = {}
    for k in ("stability", "similarity_boost", "style"):
        v = (voice_settings or {}).get(k)
        if isinstance(v, (int, float)):
            clean[k] = max(0.0, min(1.0, float(v)))
    settings = dict(DEFAULT_VOICE_SETTINGS, **clean)
    if "speed" in (voice_settings or {}):
        try:
            settings["speed"] = max(0.7, min(1.2, float(voice_settings["speed"])))
        except Exception:
            pass
    output_path = os.path.join(config.OUTPUT_DIR, "audio", output_filename)
    words_path = output_path + ".words.json"

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    headers = {"Content-Type": "application/json", "xi-api-key": config.ELEVENLABS_API_KEY}
    payload = {"text": text, "model_id": model_id, "voice_settings": settings}

    print(f"\n🎙️  Voiceover: {len(text.split())} words · voice {voice_id} · model {model_id} · {settings}")
    words = []
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=90)
        if r.status_code != 200:
            raise RuntimeError(f"{r.status_code}: {r.text[:200]}")
        data = r.json()
        audio_b64 = data.get("audio_base64") or data.get("audio")
        if not audio_b64:
            raise RuntimeError("no audio_base64 in response")
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(audio_b64))
        alignment = data.get("normalized_alignment") or data.get("alignment") or {}
        words = _alignment_to_words(alignment)
        if not words:
            print("   ⚠️  Timestamps response had no alignment — captions will use estimated timing")
    except Exception as e:
        print(f"   ⚠️  with-timestamps failed ({e}); falling back to plain TTS")
        original_voice, original_model = config.ELEVENLABS_VOICE_ID, getattr(config, "ELEVENLABS_MODEL", None)
        config.ELEVENLABS_VOICE_ID = voice_id
        config.ELEVENLABS_MODEL = model_id
        try:
            generate_voiceover(text, output_filename=output_filename)
        finally:
            config.ELEVENLABS_VOICE_ID = original_voice
            config.ELEVENLABS_MODEL = original_model
        words = []

    with open(words_path, "w") as f:
        json.dump(words, f)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"✅ Voiceover saved: {output_path} ({size_kb:.1f} KB, {len(words)} timed words)")
    return output_path, words


def estimate_words(text: str, total_duration: float) -> list:
    """Even-spaced fallback timings when real alignment is unavailable."""
    toks = text.split()
    if not toks:
        return []
    per = total_duration / len(toks)
    return [{"text": t, "start": i * per, "end": (i + 1) * per} for i, t in enumerate(toks)]


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
    out = []
    for v in response.json().get("voices", []):
        labels = v.get("labels") or {}
        out.append({
            "voice_id": v["voice_id"],
            "name": v["name"],
            "category": v.get("category", ""),          # premade | cloned | generated | professional
            "accent": labels.get("accent", ""),
            "language": labels.get("language", ""),
            "gender": labels.get("gender", ""),
            "age": labels.get("age", ""),
            "use_case": labels.get("use case") or labels.get("use_case", ""),
            "description": labels.get("description", ""),
            "preview_url": v.get("preview_url", ""),
        })
    return out


if __name__ == "__main__":
    config.validate_config()
    print("Available voices:")
    for v in list_voices():
        print(f"  {v['name']:30s} {v['voice_id']}")
