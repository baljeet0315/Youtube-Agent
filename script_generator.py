"""
script_generator.py — Generate YouTube Shorts scripts using Claude
"""
import json
import anthropic
import agent_config as config


def generate_script(topic: str, style: str = "educational", duration_seconds: int = 45) -> dict:
    """
    Generate a structured script for a YouTube Short.

    Args:
        topic: The video topic or idea (e.g. "why cats purr")
        style: One of 'educational', 'motivational', 'story', 'news'
        duration_seconds: Target video length (30–60 seconds recommended)

    Returns:
        dict with keys: title, description, tags, narration, scenes, hook
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    word_target = int(duration_seconds * 2.5)  # ~150 words/min speaking pace

    system_prompt = """You are a writer in the tradition of David Attenborough — calm, wise, observational.
You watch humanity from a great distance, with neither judgment nor comfort.
You tell stories the way Christopher Nolan makes films: layered, atmospheric, non-linear if it serves the idea.
You never explain. You never resolve. You provoke.
You speak in images, not arguments. In questions, not answers.
Always output valid JSON — no extra text outside the JSON block."""

    user_prompt = f"""Write a YouTube Shorts narration about this idea: "{topic}"

Target duration: {duration_seconds} seconds (~{word_target} spoken words)

Tone and style rules — follow these strictly:
- Narrate like David Attenborough observing a strange species called humans
- Build like a Nolan film: open on something specific and concrete, spiral inward, end on an open question with no answer
- Do NOT explain the idea. Do NOT offer solutions or comfort. Do NOT moralize.
- Every sentence should make the viewer feel something they cannot name
- The final line must be a question — haunting, open, unresolvable
- Write for silence. Short sentences. Pauses. Weight.
- No corporate language, no YouTube filler, no "in conclusion", no "today we explore"

Return a JSON object with exactly these fields:
{{
  "title": "Intriguing YouTube title — mysterious, not clickbait (max 60 chars)",
  "description": "2–3 sentences in the same Attenborough tone + relevant hashtags",
  "tags": ["tag1", "tag2", ...],
  "hook": "The opening line — a single concrete image or fact that pulls you in immediately",
  "narration": "Full narration. No scene directions. Just the spoken words. Target {word_target} words. Must end with an unanswered question.",
  "scenes": [
    {{
      "timestamp": 0,
      "duration": 5,
      "caption": "3–5 words max. Atmospheric, not explanatory.",
      "visual_query": "Concrete Pexels search query (2-4 words, searchable)"
    }}
  ]
}}

Important:
- The hook must be the first sentence of the narration
- Create 5–8 scenes covering the full duration
- visual_query should be cinematic and concrete (e.g. "lone figure foggy road", not "loneliness")
- captions should feel like film title cards — sparse, weighted
"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    script = json.loads(raw)

    # Validate required keys
    required = ["title", "description", "tags", "hook", "narration", "scenes"]
    for key in required:
        if key not in script:
            raise ValueError(f"Script missing required key: '{key}'")

    print(f"\n✅ Script generated: \"{script['title']}\"")
    print(f"   Narration length: {len(script['narration'].split())} words")
    print(f"   Scenes: {len(script['scenes'])}")

    return script


if __name__ == "__main__":
    # Quick test
    import sys
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "The science of why we dream"
    config.validate_config()
    result = generate_script(topic, style="educational", duration_seconds=45)
    print(json.dumps(result, indent=2))
