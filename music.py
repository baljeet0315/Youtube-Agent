"""
music.py — Pick a background track for a mood.

Sources, in order:
  1. Local:  <MUSIC_DIR>/<mood>/*.mp3   (bundled in the image via assets/music/)
  2. R2:     s3://<R2_BUCKET_NAME>/music/<mood>/*.mp3  (upload once, shared by all users)
Falls back to a neighbouring mood, then to None (video renders without music).
"""
import os
import random
import agent_config as config

MOOD_FALLBACK = {
    "calm": ["mysterious", "uplifting"],
    "mysterious": ["calm", "tense"],
    "tense": ["mysterious", "energetic"],
    "uplifting": ["energetic", "calm"],
    "energetic": ["uplifting", "tense"],
}
AUDIO_EXT = (".mp3", ".m4a", ".wav", ".ogg")


def _local_candidates(mood: str) -> list:
    d = os.path.join(config.MUSIC_DIR, mood)
    if not os.path.isdir(d):
        return []
    return [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.lower().endswith(AUDIO_EXT)]


def _r2_client():
    if not (config.R2_ENDPOINT and config.R2_ACCESS_KEY_ID and config.R2_SECRET_ACCESS_KEY and config.R2_BUCKET_NAME):
        return None
    try:
        import boto3
        from botocore.config import Config
        return boto3.client(
            "s3",
            endpoint_url=config.R2_ENDPOINT,
            aws_access_key_id=config.R2_ACCESS_KEY_ID,
            aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            region_name="auto",
        )
    except Exception as e:
        print(f"   ⚠️  music: R2 client unavailable ({e})")
        return None


def _r2_candidates(mood: str, client) -> list:
    try:
        resp = client.list_objects_v2(Bucket=config.R2_BUCKET_NAME, Prefix=f"music/{mood}/")
        return [o["Key"] for o in resp.get("Contents", []) if o["Key"].lower().endswith(AUDIO_EXT)]
    except Exception as e:
        print(f"   ⚠️  music: R2 list failed ({e})")
        return []


def _r2_download(key: str, client) -> str:
    local = os.path.join(config.OUTPUT_DIR, "music", os.path.basename(key))
    if not os.path.exists(local):
        client.download_file(config.R2_BUCKET_NAME, key, local)
    return local


def pick_track(mood: str) -> str | None:
    """Return a local path to a track for `mood`, or None."""
    if not config.MUSIC_ENABLED or not mood or mood == "none":
        return None

    moods = [mood] + MOOD_FALLBACK.get(mood, [])
    client = _r2_client()

    for m in moods:
        local = _local_candidates(m)
        if local:
            path = random.choice(local)
            print(f"🎵 Music: {os.path.basename(path)} (local/{m})")
            return path
        if client:
            keys = _r2_candidates(m, client)
            if keys:
                path = _r2_download(random.choice(keys), client)
                print(f"🎵 Music: {os.path.basename(path)} (r2/{m})")
                return path

    print(f"   ⚠️  No music found for mood '{mood}' — rendering without music")
    return None


if __name__ == "__main__":
    import sys
    print(pick_track(sys.argv[1] if len(sys.argv) > 1 else "calm"))
