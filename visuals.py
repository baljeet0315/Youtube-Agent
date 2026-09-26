"""
visuals.py — One AI-generated image per scene (fal.ai Flux by default).

Provider interface is deliberately tiny so Replicate / OpenAI / Ideogram can be
dropped in later:  generate_image(prompt, width, height, seed) -> local path

Failures are per-scene and non-fatal: a scene with no image falls back to
stock footage (or a colour card) in video_creator.
"""
import os
import time
import random
import hashlib
import requests
import agent_config as config


class ImageProvider:
    name = "base"

    def generate_image(self, prompt: str, width: int, height: int, seed: int, out_path: str) -> str:
        raise NotImplementedError


class FalFluxProvider(ImageProvider):
    """
    Sync REST call: POST https://fal.run/<model>
    Docs: https://fal.ai/models/fal-ai/flux/schnell/api
    """
    name = "fal"

    def __init__(self, model: str = None, api_key: str = None):
        self.model = model or config.FAL_IMAGE_MODEL
        self.api_key = api_key or config.FAL_KEY
        if not self.api_key:
            raise RuntimeError("FAL_KEY is not set")

    def generate_image(self, prompt: str, width: int, height: int, seed: int, out_path: str) -> str:
        url = f"https://fal.run/{self.model}"
        headers = {"Authorization": f"Key {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "prompt": prompt,
            "image_size": {"width": width, "height": height},
            "num_images": 1,
            "num_inference_steps": 4,
            "seed": seed,
            "output_format": "jpeg",
            "enable_safety_checker": True,
        }
        last_err = None
        for attempt in range(3):
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=120)
                if r.status_code == 429 or r.status_code >= 500:
                    raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
                r.raise_for_status()
                data = r.json()
                images = data.get("images") or []
                if not images or not images[0].get("url"):
                    raise RuntimeError(f"no image in response: {str(data)[:200]}")
                img = requests.get(images[0]["url"], timeout=60)
                img.raise_for_status()
                with open(out_path, "wb") as f:
                    f.write(img.content)
                return out_path
            except Exception as e:
                last_err = e
                wait = 2 ** attempt
                print(f"   ⚠️  fal attempt {attempt + 1} failed: {e} — retry in {wait}s")
                time.sleep(wait)
        raise RuntimeError(f"fal image generation failed: {last_err}")


def get_provider() -> ImageProvider:
    # Only one provider today; env switch reserved for later.
    return FalFluxProvider()


# ── Prompt assembly ──────────────────────────────────────────────────────────

def build_image_prompt(scene: dict, style_guide: dict) -> str:
    """Scene prompt + global style + hard 'no text' rule. Flux schnell has no
    negative prompt, so negatives are phrased positively where possible."""
    parts = [scene.get("visual_prompt") or scene.get("visual_query") or "cinematic still"]
    vs = (style_guide or {}).get("visual_style")
    if vs:
        parts.append(vs)
    parts.append("vertical 9:16 composition, subject centred with headroom, "
                 "no text, no letters, no captions, no watermark, no logo")
    return ". ".join(p.strip().rstrip(".") for p in parts if p) + "."


def job_seed(script: dict) -> int:
    """Stable per-script seed so re-renders of the same script look the same,
    and scenes share a base seed for a more consistent look."""
    key = (script.get("title", "") + "|" + script.get("narration", "")[:200]).encode()
    return int(hashlib.sha256(key).hexdigest()[:8], 16) % (2**31)


# ── Public API ───────────────────────────────────────────────────────────────

def generate_scene_images(script: dict, job_id: str, progress=None) -> dict:
    """
    Generate one image per scene. Returns {scene_id: path or None}.
    `progress(i, n)` is called after each scene if provided.
    Never raises for a single bad scene; raises only if the provider can't init.
    """
    provider = get_provider()
    scenes = script.get("scenes", [])
    style_guide = script.get("style_guide") or {}
    base_seed = job_seed(script)
    out_dir = os.path.join(config.OUTPUT_DIR, "images", job_id)
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n🖼️  Generating {len(scenes)} scene images via {provider.name} ({provider.model})")
    results = {}
    for i, scene in enumerate(scenes):
        sid = scene.get("id", i + 1)
        prompt = build_image_prompt(scene, style_guide)
        out_path = os.path.join(out_dir, f"scene_{sid:02d}.jpg")
        seed = base_seed + sid  # deterministic but different per scene
        t0 = time.time()
        try:
            provider.generate_image(prompt, config.IMAGE_GEN_WIDTH, config.IMAGE_GEN_HEIGHT, seed, out_path)
            results[sid] = out_path
            print(f"   ✓ scene {sid}: {os.path.basename(out_path)} ({time.time() - t0:.1f}s)")
        except Exception as e:
            results[sid] = None
            print(f"   ✗ scene {sid}: {e} — will fall back to stock footage")
        if progress:
            try:
                progress(i + 1, len(scenes))
            except Exception:
                pass
    ok = sum(1 for v in results.values() if v)
    print(f"   {ok}/{len(scenes)} images generated")
    return results


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) < 2:
        print("Usage: python visuals.py <script.json>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        s = json.load(f)
    print(generate_scene_images(s, "manual_test"))
