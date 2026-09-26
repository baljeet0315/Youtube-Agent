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


def _font(size: int):
    try:
        return ImageFont.truetype(config.CAPTION_FONT, size)
    except Exception:
        return ImageFont.load_default()


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
                or text.endswith((".", "!", "?", ",", ";", ":", "—"))):
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
        font = _font(max(28, int(font.size * scale)))
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

    font = _font(config.CAPTION_FONT_SIZE)
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
