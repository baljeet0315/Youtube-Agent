"""
captions.py — Word-level "pop" captions rendered with Pillow (no ImageMagick).

Input : words = [{text, start, end}, ...] from voiceover timestamps
Output: list of MoviePy ImageClips, each a transparent PNG showing a 2–3 word
        chunk with the currently spoken word highlighted.
"""
import os
import re
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import agent_config as config

MAX_WORDS_PER_CHUNK = 3
MAX_CHUNK_SECONDS = 1.6
STROKE_W = 4


# Script detection → (fontconfig language tag, Noto family name). DejaVu covers Latin/Cyrillic/Greek.
SCRIPTS = [
    ((0x0A00, 0x0A7F), "pa", "NotoSansGurmukhi"),    # Punjabi
    ((0x0900, 0x097F), "hi", "NotoSansDevanagari"),  # Hindi / Marathi
    ((0x0600, 0x06FF), "ur", "NotoSansArabic"),      # Urdu / Arabic
    ((0x0980, 0x09FF), "bn", "NotoSansBengali"),
    ((0x0B80, 0x0BFF), "ta", "NotoSansTamil"),
    ((0x0C00, 0x0C7F), "te", "NotoSansTelugu"),
    ((0x0A80, 0x0AFF), "gu", "NotoSansGujarati"),
]
NOTO_URLS = [
    "https://github.com/notofonts/notofonts.github.io/raw/main/fonts/{fam}/full/ttf/{fam}-Bold.ttf",
    "https://github.com/notofonts/notofonts.github.io/raw/main/fonts/{fam}/hinted/ttf/{fam}-Bold.ttf",
    # Google Fonts mirror (variable font; default instance renders fine)
    "https://github.com/google/fonts/raw/main/ofl/{fam_lower}/{fam}%5Bwdth%2Cwght%5D.ttf",
    "https://github.com/google/fonts/raw/main/ofl/{fam_lower}/{fam}%5Bwght%5D.ttf",
]
_font_for_text_cache = {}
_font_path_cache = {}


def _fc_match(lang: str) -> str | None:
    """Ask fontconfig for any installed font covering `lang`, preferring bold."""
    import subprocess
    try:
        out = subprocess.run(["fc-list", f":lang={lang}", "file", "style"],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return None
    files = []
    for line in out.splitlines():
        path = line.split(":")[0].strip()
        if path.lower().endswith((".ttf", ".otf")):
            files.append((("bold" in line.lower()) * -1, path))   # bold first
    files.sort()
    return files[0][1] if files else None


def _download_noto(fam: str) -> str | None:
    """Fetch Noto Sans <script> Bold once and cache it under OUTPUT_DIR/fonts."""
    import requests
    d = os.path.join(config.OUTPUT_DIR, "fonts")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{fam}-Bold.ttf")
    if os.path.exists(path):
        return path
    for url in NOTO_URLS:
        url = url.format(fam=fam, fam_lower=fam.lower())
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200 or len(r.content) < 20_000:
                continue
            with open(path, "wb") as f:
                f.write(r.content)
            print(f"   ⬇️  Downloaded caption font {fam} from {url.split('/')[2]}")
            return path
        except Exception as e:
            print(f"   ⚠️  font download failed ({url.split('/')[2]}): {e}")
    return None


def _font_path_for(text: str) -> str:
    """Pick a font that has glyphs for the dominant non-Latin script in `text`."""
    for (lo, hi), lang, fam in SCRIPTS:
        if not any(lo <= ord(ch) <= hi for ch in text):
            continue
        if lang in _font_path_cache:
            return _font_path_cache[lang]
        candidates = [
            f"/usr/share/fonts/truetype/noto/{fam}-Bold.ttf",
            f"/usr/share/fonts/truetype/noto/{fam}-Regular.ttf",
            f"/usr/share/fonts/opentype/noto/{fam}-Bold.ttf",
        ]
        path = next((p for p in candidates if os.path.exists(p)), None) or _fc_match(lang) or _download_noto(fam)
        if path:
            print(f"   🔤 Caption font for '{lang}': {os.path.basename(path)}")
            _font_path_cache[lang] = path
            return path
        print(f"   ⚠️  No font found for '{lang}' — captions may show boxes")
        break
    return config.CAPTION_FONT


def _font(size: int, text: str = ""):
    path = _font_path_for(text) if text else config.CAPTION_FONT
    key = (path, size)
    if key not in _font_for_text_cache:
        try:
            _font_for_text_cache[key] = ImageFont.truetype(path, size)
        except Exception:
            _font_for_text_cache[key] = ImageFont.load_default()
    return _font_for_text_cache[key]


def _clean(w: str) -> str:
    # Keep apostrophes/hyphens; drop trailing punctuation that looks odd alone
    return re.sub(r'^[\"“”(\[]+|[\"“”)\],;:]+$', "", w)


def chunk_words(words: list) -> list:
    """Group words into short chunks that read naturally: break on punctuation,
    on chunk length, or on time span."""
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        text = w["text"]
        span = cur[-1]["end"] - cur[0]["start"]
        if (len(cur) >= MAX_WORDS_PER_CHUNK
                or span >= MAX_CHUNK_SECONDS
                or text.endswith((".", "!", "?", ",", ";", ":", "—", "।", "॥"))):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def _render_chunk(chunk: list, active_idx: int, video_w: int, font, highlight: str) -> Image.Image:
    """Render one chunk with word `active_idx` highlighted. Returns RGBA image
    sized to the text block (not the whole frame) to keep clips small."""
    texts = [_clean(w["text"]) for w in chunk]
    draw_probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    space_w = draw_probe.textlength(" ", font=font)
    widths = [draw_probe.textlength(t, font=font) for t in texts]
    total_w = sum(widths) + space_w * (len(texts) - 1)

    # Shrink font if a chunk is wider than the safe area
    max_w = video_w - 80
    if total_w > max_w:
        scale = max_w / total_w
        font = _font(max(28, int(font.size * scale)), " ".join(texts))
        widths = [draw_probe.textlength(t, font=font) for t in texts]
        space_w = draw_probe.textlength(" ", font=font)
        total_w = sum(widths) + space_w * (len(texts) - 1)

    ascent, descent = font.getmetrics()
    h = ascent + descent + STROKE_W * 2 + 8
    img = Image.new("RGBA", (int(total_w) + STROKE_W * 2 + 8, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    x = STROKE_W + 4
    y = STROKE_W + 2
    for i, (t, w) in enumerate(zip(texts, widths)):
        fill = highlight if i == active_idx else "white"
        draw.text((x, y), t, font=font, fill=fill, stroke_width=STROKE_W, stroke_fill="black")
        x += w + space_w
    return img


def build_caption_clips(words: list, video_w: int, video_h: int, fps: int) -> list:
    """Return MoviePy ImageClips positioned and timed for compositing."""
    if not words:
        return []
    from moviepy.editor import ImageClip

    all_text = " ".join(w["text"] for w in words)
    font = _font(config.CAPTION_FONT_SIZE, all_text)
    highlight = config.CAPTION_HIGHLIGHT
    y_center = int(video_h * config.CAPTION_Y_RATIO)
    clips = []

    for chunk in chunk_words(words):
        for i, w in enumerate(chunk):
            start = w["start"]
            # Hold the last word of a chunk until the next chunk starts (no flicker gaps)
            end = chunk[i + 1]["start"] if i + 1 < len(chunk) else w["end"]
            dur = max(0.05, end - start)
            img = _render_chunk(chunk, i, video_w, font, highlight)
            arr = np.array(img)
            clip = (ImageClip(arr, ismask=False, transparent=True)
                    .set_start(start)
                    .set_duration(dur)
                    .set_position(("center", y_center - img.height // 2)))
            clips.append(clip)
    return clips


if __name__ == "__main__":
    # Quick visual check: writes one caption frame to /tmp
    sample = [{"text": "Rain", "start": 0, "end": 0.3}, {"text": "hit", "start": 0.3, "end": 0.5},
              {"text": "the", "start": 0.5, "end": 0.6}, {"text": "glass.", "start": 0.6, "end": 1.0}]
    ch = chunk_words(sample)
    img = _render_chunk(ch[0], 1, 720, _font(config.CAPTION_FONT_SIZE), config.CAPTION_HIGHLIGHT)
    img.save("/tmp/caption_test.png")
    print("chunks:", [[w["text"] for w in c] for c in ch], "→ /tmp/caption_test.png")
