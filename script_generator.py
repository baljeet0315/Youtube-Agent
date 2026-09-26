"""
script_generator.py — Generate YouTube Shorts scripts using Claude

Two input modes:
  idea  — user gives a topic; Claude writes the narration.
  text  — user pastes their own paragraph; it is used VERBATIM as the narration
          and Claude builds title / tags / scenes / visual prompts around it.

Output follows scene schema v2 (see PHASE2_PLAN.md §1) and stays backward
compatible with the v1 assembler: every scene still has `timestamp`,
`duration`, `caption`, `visual_query`.
"""
import json
import re
import anthropic
import agent_config as config

MODEL = "claude-opus-4-6"

# Speaking pace used for all length math. ~150 wpm.
WORDS_PER_SECOND = 2.5
MAX_SHORT_SECONDS = 60
MAX_WORDS = int(MAX_SHORT_SECONDS * WORDS_PER_SECOND)  # 150

# ── Narration presets ────────────────────────────────────────────────────────
# Frontend offers these as chips; the chip fills the narration_style text box
# with the key. Free text is also accepted and used as-is.

NARRATION_PRESETS = {
    "documentary": (
        "A nature-documentary narrator: calm, precise, observational. Speaks slowly, "
        "lets facts land, never hypes. Occasional dry wonder."
    ),
    "storyteller": (
        "A fireside storyteller: warm, intimate, second-person when it helps. Builds "
        "tension sentence by sentence and pays it off at the end."
    ),
    "energetic": (
        "A fast, punchy YouTube host: short sentences, direct address, playful "
        "confidence. Every line earns the next second of attention. No shouting, no cringe."
    ),
    "philosopher": (
        "A calm philosopher thinking out loud: unhurried, curious, concrete images over "
        "abstractions. Ends on a question that lingers rather than a lesson."
    ),
    "news": (
        "A sharp news explainer: clear, neutral, specific. Leads with the most surprising "
        "fact, gives context in plain language, closes with why it matters."
    ),
}

CONTENT_STYLE_HINTS = {
    "educational": "Teach one thing clearly. Lead with the surprising part, then the why.",
    "motivational": "Earn the emotion with specifics, not slogans. One honest turn, no clichés.",
    "storytelling": "One character, one moment, one change. Show, don't summarize.",
    "story": "One character, one moment, one change. Show, don't summarize.",
    "news": "Most important fact first. Plain language. Say why it matters.",
    "philosophical": "Start from something ordinary and make it strange. End open.",
}

BANNED_PHRASES = [
    "in conclusion", "today we explore", "today we're going to", "let's dive in",
    "did you know", "welcome back", "in this video", "without further ado",
    "at the end of the day", "it's important to note", "game-changer", "unlock",
]


# ── Validation helpers ───────────────────────────────────────────────────────

def estimate_seconds(text: str) -> float:
    return len(text.split()) / WORDS_PER_SECOND


def validate_source_text(text: str) -> dict:
    """
    Check pasted text against the Shorts limit.
    Returns {ok, words, est_seconds, max_words, message}.
    Used by both the API (reject early) and the generator.
    """
    words = len(text.split())
    est = words / WORDS_PER_SECOND
    if words == 0:
        return {"ok": False, "words": 0, "est_seconds": 0, "max_words": MAX_WORDS,
                "message": "Paste the text you want narrated."}
    if words > MAX_WORDS:
        return {
            "ok": False, "words": words, "est_seconds": round(est), "max_words": MAX_WORDS,
            "message": (
                f"That's about {round(est)} seconds at speaking pace — Shorts max is "
                f"{MAX_SHORT_SECONDS}s. Trim to roughly {MAX_WORDS} words "
                f"(you're {words - MAX_WORDS} over)."
            ),
        }
    return {"ok": True, "words": words, "est_seconds": round(est), "max_words": MAX_WORDS,
            "message": f"About {round(est)} seconds."}


# ── Prompt pieces ────────────────────────────────────────────────────────────

def _resolve_narration_style(narration_style: str) -> str:
    key = (narration_style or "").strip().lower()
    if not key:
        return NARRATION_PRESETS["documentary"]
    return NARRATION_PRESETS.get(key, narration_style.strip())


def _schema_block(narration_instruction: str, word_target: int) -> str:
    return f"""Return ONE JSON object with exactly these fields and nothing else:
{{
  "version": 2,
  "title": "YouTube title. Specific and curiosity-driven, matches the tone. Max 60 chars. No clickbait words like SHOCKING.",
  "description": "2–3 sentences in the same voice, then 3–5 relevant hashtags on a new line.",
  "tags": ["8–12 short lowercase tags, no # symbol"],
  "hook": "The first sentence of the narration, copied exactly.",
  "narration": "{narration_instruction}",
  "music_mood": "one of: calm, mysterious, tense, uplifting, energetic, none",
  "style_guide": {{
    "visual_style": "One line describing the look for ALL images: medium (photoreal / painterly / 3D), palette, lighting, lens, grain. Cinematic 9:16.",
    "subject_consistency": "If a person, animal or object recurs across scenes, describe it once in concrete visual terms (age, build, clothing, colour, species). Otherwise null.",
    "negative_prompt": "text, watermark, logo, caption, extra fingers, deformed, blurry, low quality"
  }},
  "scenes": [
    {{
      "id": 1,
      "narration_excerpt": "The exact sentence(s) from `narration` this scene plays under. Must be a verbatim substring. Scenes must cover the whole narration in order with no overlap.",
      "duration_hint": 5,
      "caption": "3–5 word title-card text, or null. Not a subtitle — a mood line.",
      "visual_prompt": "A standalone image prompt (25–50 words): subject, setting, action, lighting, camera angle, mood. If subject_consistency is set and the subject appears, repeat that wording exactly. No text or letters in the image.",
      "motion": "one of: zoom_in, zoom_out, pan_left, pan_right, static",
      "visual_query": "2–4 word stock-footage search fallback, concrete (e.g. 'rain on window night')"
    }}
  ]
}}

Scene rules:
- 5–8 scenes. Every scene 3–8 seconds. Cut on sentence boundaries.
- Vary shot scale: mix wide, medium, close-up. Vary motion. Never two identical prompts.
- visual_prompt describes what the camera SEES, not the idea. "Empty playground at dusk, single swing moving" not "loneliness".
- Target narration length: ~{word_target} words."""


def _idea_prompt(topic: str, style: str, narration_desc: str, duration: int) -> tuple[str, str]:
    word_target = int(duration * WORDS_PER_SECOND)
    hard_max = min(int(word_target * 1.15), MAX_WORDS)
    style_hint = CONTENT_STYLE_HINTS.get(style.lower(), CONTENT_STYLE_HINTS["educational"])
    banned = ", ".join(BANNED_PHRASES)
    schema = _schema_block("Full spoken narration only. No stage directions, no speaker labels.", word_target)

    system = f"""You write narration for vertical short-form video (YouTube Shorts).
Voice: {narration_desc}
You always answer with valid JSON only — no prose, no markdown fences."""

    user = f"""The user asked for a {duration}-second Short. Their request, in their own words:

<request>
{topic}
</request>

The request may be phrased as an instruction ("create me a script for…", "make a video about…").
Extract the actual SUBJECT and write about that — never echo the instruction wording in the title
or narration. If the request itself specifies a tone, audience, angle or length, honour it; it
overrides the defaults below.

Content style: {style_hint}

Writing rules — these decide whether the video gets watched:
- HOOK: the first sentence must be under 12 words and contain something specific and surprising — a number, a contradiction, an image, a claim the viewer wants to check. No greetings, no questions like "have you ever wondered".
- ONE idea. If you feel a second idea coming, cut it.
- Concrete over abstract. Nouns you can picture. Numbers where true. Sensory details.
- Spoken rhythm: mostly short sentences, one longer one for breath. Read it aloud in your head.
- No filler. Never use: {banned}.
- The last line must land — a turn, a callback to the hook, or a question that stays. Not a summary, not a call to action.
- Length: about {word_target} words. Hard maximum {hard_max}.

{schema}"""
    return system, user


def _text_prompt(source_text: str, style: str, narration_desc: str) -> tuple[str, str]:
    words = len(source_text.split())
    style_hint = CONTENT_STYLE_HINTS.get(style.lower(), CONTENT_STYLE_HINTS["storytelling"])
    schema = _schema_block("The provided narration, copied EXACTLY. Do not change a single word.", words)

    system = f"""You are a film editor turning a given passage into a vertical short-form video.
The narration is FIXED — the user wrote it. You do not rewrite, trim, or improve it.
Delivery voice (for title/description tone only): {narration_desc}
You always answer with valid JSON only — no prose, no markdown fences."""

    user = f"""Here is the narration, exactly as it will be spoken ({words} words):

<narration>
{source_text}
</narration>

Your job: build the video around it.
- Copy the narration into the "narration" field EXACTLY, character for character.
- Break it into scenes on sentence boundaries; each scene's narration_excerpt must be a verbatim substring, in order, covering all of it.
- Write visual prompts that illustrate what each passage evokes — literal when the text is concrete, atmospheric when it is abstract.
- Content style for framing: {style_hint}

{schema}"""
    return system, user


# ── Post-processing ──────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    # Tolerate stray text before/after the object
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model did not return a JSON object")
    return json.loads(raw[start:end + 1])


def _normalize(script: dict, narration_override: str | None, duration_hint_total: int) -> dict:
    """Validate, enforce verbatim narration in text mode, add v1-compat fields."""
    required = ["title", "description", "tags", "narration", "scenes"]
    for key in required:
        if key not in script:
            raise ValueError(f"Script missing required key: '{key}'")

    script["version"] = 2

    if narration_override is not None:
        script["narration"] = narration_override  # guarantee verbatim

    narration = script["narration"].strip()
    script["narration"] = narration

    # Hook = first sentence, always derived so it can't drift
    first = re.split(r"(?<=[.!?])\s+", narration, maxsplit=1)[0]
    script["hook"] = first.strip()

    script.setdefault("music_mood", "calm")
    if script["music_mood"] not in {"calm", "mysterious", "tense", "uplifting", "energetic", "none"}:
        script["music_mood"] = "calm"

    sg = script.get("style_guide") or {}
    sg.setdefault("visual_style", "cinematic photoreal, soft natural light, shallow depth of field, subtle film grain")
    sg.setdefault("subject_consistency", None)
    sg.setdefault("negative_prompt", "text, watermark, logo, caption, extra fingers, deformed, blurry, low quality")
    script["style_guide"] = sg

    scenes = script["scenes"]
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Script has no scenes")

    # Tags: clean
    script["tags"] = [str(t).lstrip("#").strip().lower() for t in script.get("tags", []) if str(t).strip()][:15]

    # Scenes: fill defaults + v1 compat (timestamp/duration)
    total_hint = 0
    for i, s in enumerate(scenes, start=1):
        s["id"] = i
        s.setdefault("narration_excerpt", "")
        s["duration_hint"] = max(3, min(8, int(s.get("duration_hint") or s.get("duration") or 5)))
        s.setdefault("caption", None)
        s.setdefault("visual_prompt", s.get("visual_query", ""))
        s.setdefault("visual_query", " ".join(str(s.get("visual_prompt", "")).split()[:4]))
        if s.get("motion") not in {"zoom_in", "zoom_out", "pan_left", "pan_right", "static"}:
            s["motion"] = "zoom_in" if i % 2 else "pan_right"
        if s["narration_excerpt"] and s["narration_excerpt"] not in narration:
            # Keep going, but flag it so the assembler falls back to proportional timing
            s["excerpt_verified"] = False
        else:
            s["excerpt_verified"] = bool(s["narration_excerpt"])
        total_hint += s["duration_hint"]

    # v1 compat: timestamp + duration scaled to the intended length
    t = 0.0
    for s in scenes:
        dur = round(s["duration_hint"] / total_hint * duration_hint_total, 2)
        s["timestamp"] = round(t, 2)
        s["duration"] = dur
        t += dur

    return script


# ── Public API ───────────────────────────────────────────────────────────────

def generate_script(
    topic: str = "",
    style: str = "educational",
    duration_seconds: int = 45,
    narration_style: str = "",
    input_mode: str = "idea",
    source_text: str = "",
) -> dict:
    """
    Generate a structured Shorts script (schema v2, v1-compatible).

    input_mode="idea": `topic` is a subject; Claude writes narration of ~duration_seconds.
    input_mode="text": `source_text` is used verbatim as narration (≤150 words); `topic`
                       is optional context. Raises ValueError if over the 60 s limit.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    narration_desc = _resolve_narration_style(narration_style)

    if input_mode == "text":
        check = validate_source_text(source_text)
        if not check["ok"]:
            raise ValueError(check["message"])
        system, user = _text_prompt(source_text.strip(), style, narration_desc)
        narration_override = source_text.strip()
        intended_seconds = max(15, check["est_seconds"])
    else:
        if not topic.strip():
            raise ValueError("Topic is required in idea mode")
        duration_seconds = max(15, min(MAX_SHORT_SECONDS, int(duration_seconds)))
        system, user = _idea_prompt(topic.strip(), style, narration_desc, duration_seconds)
        narration_override = None
        intended_seconds = duration_seconds

    message = client.messages.create(
        model=MODEL,
        max_tokens=2500,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    script = _parse_json(message.content[0].text)
    script = _normalize(script, narration_override, intended_seconds)

    # Idea mode: enforce the hard cap even if the model overshoots
    if input_mode == "idea":
        wc = len(script["narration"].split())
        if wc > MAX_WORDS:
            raise ValueError(f"Generated narration is {wc} words (> {MAX_WORDS}). Retry with a shorter duration.")

    script["input_mode"] = input_mode
    script["narration_style"] = narration_style or "documentary"
    script["style"] = style
    script["intended_seconds"] = intended_seconds

    print(f"\n✅ Script generated: \"{script['title']}\"")
    print(f"   Mode: {input_mode} · {len(script['narration'].split())} words · "
          f"{len(script['scenes'])} scenes · music: {script['music_mood']}")
    return script


# ── Review-gate helpers ──────────────────────────────────────────────────────

EDITABLE_TOP = {"title", "description", "tags", "narration", "music_mood"}
EDITABLE_SCENE = {"visual_prompt", "caption", "motion", "visual_query", "narration_excerpt"}


def apply_script_edits(script: dict, edits: dict) -> dict:
    """
    Merge user edits from the Script Review UI and re-normalize.
    edits = {"title"?, "description"?, "tags"?, "narration"?, "music_mood"?,
             "scenes"?: [{"id": 1, "visual_prompt"?, "caption"?, "motion"?}, ...]}
    In text mode the narration is locked (it's the user's own words by design);
    to change it they start a new job.
    """
    script = json.loads(json.dumps(script))  # deep copy
    for k in EDITABLE_TOP:
        if k in edits and edits[k] is not None:
            if k == "narration" and script.get("input_mode") == "text":
                continue
            script[k] = edits[k]

    if edits.get("scenes"):
        by_id = {s.get("id"): s for s in script.get("scenes", [])}
        for e in edits["scenes"]:
            target = by_id.get(e.get("id"))
            if not target:
                continue
            for k in EDITABLE_SCENE:
                if k in e and e[k] is not None:
                    target[k] = e[k]

    narration_override = script["narration"] if script.get("input_mode") == "text" else None
    intended = int(script.get("intended_seconds") or max(15, round(estimate_seconds(script["narration"]))))
    normalized = _normalize(script, narration_override, intended)
    normalized["edited"] = True
    return normalized


def regenerate_script(script: dict, feedback: str) -> dict:
    """
    Rewrite a script using the user's feedback (Approach 3).
    Idea mode: narration, scenes, title etc. may all change.
    Text mode:  narration is fixed; only title/description/scenes/prompts change.
    """
    feedback = (feedback or "").strip()
    if not feedback:
        raise ValueError("Feedback is empty")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    input_mode = script.get("input_mode", "idea")
    narration_desc = _resolve_narration_style(script.get("narration_style", ""))
    style = script.get("style", "educational")
    intended = int(script.get("intended_seconds") or 45)
    word_target = int(intended * WORDS_PER_SECOND)

    # Strip derived/compat fields so the model sees the clean v2 shape
    prev = {k: v for k, v in script.items()
            if k in {"title", "description", "tags", "narration", "music_mood", "style_guide", "scenes"}}
    prev["scenes"] = [{k: v for k, v in s.items()
                       if k in {"id", "narration_excerpt", "duration_hint", "caption",
                                "visual_prompt", "motion", "visual_query"}}
                      for s in prev.get("scenes", [])]
    prev_json = json.dumps(prev, ensure_ascii=False, indent=1)
    banned = ", ".join(BANNED_PHRASES)

    if input_mode == "text":
        narration_override = script["narration"]
        schema = _schema_block("The existing narration, copied EXACTLY. It must not change.", word_target)
        lock_rule = ("The narration is the user's own text and is LOCKED. Do not change a single word of it. "
                     "Apply the feedback to title, description, tags, music mood, scene breakdown and visual prompts only.")
    else:
        narration_override = None
        schema = _schema_block("Full spoken narration only. No stage directions.", word_target)
        lock_rule = (f"You may rewrite anything, including the narration. Keep it about {word_target} words "
                     f"(hard max {min(int(word_target * 1.15), MAX_WORDS)}). Keep the hook rules: first sentence "
                     f"under 12 words, specific and surprising. Never use: {banned}.")

    system = f"""You revise narration and shot lists for vertical short-form video (YouTube Shorts).
Voice: {narration_desc}
You always answer with valid JSON only — no prose, no markdown fences."""

    user = f"""Here is the current script:

<current_script>
{prev_json}
</current_script>

The user reviewed it and said:

<feedback>
{feedback}
</feedback>

Revise the script to address the feedback directly and specifically. Change what the feedback asks
for; keep what it doesn't mention unless it must change to stay coherent. {lock_rule}

{schema}"""

    message = client.messages.create(
        model=MODEL,
        max_tokens=2500,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    new = _parse_json(message.content[0].text)
    new = _normalize(new, narration_override, intended)

    if input_mode == "idea" and len(new["narration"].split()) > MAX_WORDS:
        raise ValueError("Revised narration is too long for a Short — ask for something shorter.")

    # Carry job-level metadata forward
    for k in ("input_mode", "narration_style", "style", "intended_seconds"):
        if k in script:
            new[k] = script[k]
    new["regenerated_from_feedback"] = feedback

    print(f"\n♻️  Script regenerated: \"{new['title']}\" (feedback: {feedback[:60]}…)")
    return new


if __name__ == "__main__":
    import sys
    config.validate_config()
    if len(sys.argv) > 2 and sys.argv[1] == "--text":
        result = generate_script(input_mode="text", source_text=" ".join(sys.argv[2:]))
    else:
        topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "The science of why we dream"
        result = generate_script(topic, style="educational", duration_seconds=45)
    print(json.dumps(result, indent=2))
