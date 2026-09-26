# Phase 2 Plan — Script-driven, AI-generated visuals

Status: DRAFT (Sept 2026). Current pipeline works end-to-end for multiple users.
This plan upgrades output quality. Architecture stays: FastAPI + Celery worker on
Railway, Next.js on Vercel, Supabase, R2. Each "agent" below is a Python module
called by the same Celery task — no new services.

---

## 0. Target flow (what changes for the user)

```
idea ──► SCRIPT (Claude) ──► [user reviews script + scene prompts]
                                    │  approve / edit / "regenerate with feedback"
                                    ▼
             VOICE (ElevenLabs, with word timestamps)
                                    ▼
             VISUALS (one AI image per scene, animated with pan/zoom)
                                    ▼
             ASSEMBLE (scenes cut on sentence ends + word captions + music)
                                    ▼
             PREVIEW ──► approve ──► YouTube
```

Key change: a **script approval gate** before anything is rendered. Rendering
now costs money (image gen) and time, so the user sees the script and per-scene
visual prompts first, can edit text inline or ask for a rewrite with feedback,
and only then triggers render. This is "script first, video tailored to it".

---

## 1. Scene schema v2 (the contract between all stages)

```json
{
  "version": 2,
  "title": "…",
  "description": "…",
  "tags": ["…"],
  "hook": "first sentence of narration",
  "narration": "full spoken text, nothing else",
  "music_mood": "calm | mysterious | tense | uplifting | energetic | none",
  "style_guide": {
    "visual_style": "cinematic photoreal, muted teal/amber, 35mm grain, shallow DOF",
    "subject_consistency": "recurring subject description if any, e.g. 'lone man, 40s, grey wool coat, short dark hair' — or null",
    "negative_prompt": "text, watermark, logo, extra fingers, blurry, low quality"
  },
  "scenes": [
    {
      "id": 1,
      "narration_excerpt": "exact sentence(s) from narration this scene covers",
      "duration_hint": 5,
      "caption": "3–5 word title card (optional, may be null)",
      "visual_prompt": "standalone image prompt: subject + setting + lighting + camera + mood. Must repeat subject_consistency wording when the subject appears.",
      "motion": "zoom_in | zoom_out | pan_left | pan_right | static",
      "visual_query": "2–4 word Pexels fallback query"
    }
  ]
}
```

Rules
- `narration_excerpt` must be a verbatim substring of `narration`. Scene cut
  times come from where that excerpt ends in the voice timestamps — not from
  `duration_hint` (which is only a fallback).
- `visual_prompt` is self-contained (image models have no memory between calls).
  `style_guide.visual_style` is appended to every prompt automatically.
- `visual_query` stays so the Pexels path still works if image gen fails or
  the user picks "stock footage" mode.
- Version field lets old v1 scripts in the DB still render.

---

## 2. Modules ("agents")

| Module | File | Input → Output |
|---|---|---|
| Script | `script_generator.py` | topic, style, narration_style, duration → schema v2 JSON. Also `regenerate_script(script, feedback)`. |
| Voice | `voiceover.py` | narration, voice_id, settings → mp3 + `words[] {text, start, end}` (ElevenLabs `/with-timestamps`). |
| Visuals | `visuals.py` (new) | scene list + style_guide → one 9:16 image per scene (fal.ai Flux; swappable `ImageProvider` interface; Pexels fallback). |
| Captions | `captions.py` (new) | words[] → Pillow-rendered PNG overlays, grouped 2–3 words, active word highlighted. No ImageMagick. |
| Music | `music.py` (new) | mood → picks track from R2 `music/{mood}/`, returns local path. |
| Assemble | `video_creator.py` (rewrite) | images + motion + timings + captions + voice + music → mp4. |

### Provider choice for images
fal.ai + Flux (`fal-ai/flux/schnell` for drafts, `fal-ai/flux/dev` for final).
Reasons: simple REST, fast (~2–5 s/image), native 9:16 (`image_size: portrait_16_9`),
roughly $0.003–0.03 per image → well under $0.25 per Short for 6–8 scenes.
(Pricing from mid-2026 knowledge — verify on fal.ai before committing.)
Interface is `generate_image(prompt, negative, width, height) -> path`, so
Replicate / OpenAI / Ideogram can be dropped in later.

### Motion (Ken Burns)
MoviePy `ImageClip` → `resize(lambda t: 1 + k*t)` + center crop, or FFmpeg
`zoompan`. Images are generated slightly larger than 720×1280 (e.g. 832×1472)
so pans/zooms never show edges. Lighter on memory than decoding stock video.

### Captions
- ElevenLabs returns character alignment → group into words → group into
  2–3 word "chunks" per screen.
- Render each chunk with Pillow to a transparent PNG (bold font bundled in
  repo, OFL-licensed e.g. Anton/Montserrat-Black), white fill, black stroke,
  active word in accent color. Position ~62% down the frame (safe from
  YouTube UI).
- Overlay as `ImageClip` with exact start/end. Zero ImageMagick.

### Music
- R2 folder `music/<mood>/*.mp3`, 8–10 royalty-free tracks total to start.
- Mix at ~10–15 % volume under voice, 1.5 s fade-out at end, loop if short.
- `music_mood: none` → skip.

---

## 3. Data / API changes

Supabase `jobs`
- `status` gains `script_ready` (between `processing` and `preview_ready`).
- new: `visual_mode text default 'ai_images'` (`ai_images | stock`),
  `feedback_history jsonb default '[]'`, `regeneration_count int default 0`,
  `estimated_cost_usd numeric`.

Supabase `users`
- new: `default_visual_mode`, `default_caption_style`, `voice_settings jsonb`
  (stability / similarity / style).

Backend
- `POST /jobs` → runs script stage only, ends at `script_ready`.
- `POST /jobs/{id}/script` (PATCH semantics) → user edits narration / scene
  prompts inline.
- `POST /jobs/{id}/regenerate` `{feedback}` → new script from old + feedback.
- `POST /jobs/{id}/render` → voice + visuals + assemble → `preview_ready`.
- `GET /voices` → curated list + user's ElevenLabs library.

Frontend
- Job page shows a **Script Review** state: narration (editable), scene cards
  (prompt editable, caption editable), voice picker, music mood, "Regenerate
  with feedback" textbox, **Render video** button.
- Settings: voice sliders, default visual mode.

Env (Railway, both services): `FAL_KEY`. Music files uploaded to R2 once.

---

## 4. Build order

### Phase 1 — script quality + control (no visual change yet)
1. Rewrite script prompts for Shorts: hook in first 1.5 s, concrete > abstract,
   one idea per video, strong last line. `narration_style` becomes the primary
   voice instruction, with 5 named presets + free text.
   Two input modes:
   - `idea` (default): topic → Claude writes narration.
   - `text`: user pastes a paragraph/story/quote → used as narration verbatim
     (optional `condense_to_seconds`), Claude generates title, description,
     tags, scenes, visual prompts, music mood around it. UI shows estimated
     length (~2.5 words/s). Hard limit 60 s: text over ~150 words is rejected
     with a clear message ("~X s at speaking pace — Shorts max is 60 s, trim to
     about 150 words") both in the UI and at `POST /jobs`. No auto-condense.
     `jobs.input_mode`, `jobs.source_text` columns.
2. Emit schema v2 (visual_prompt, narration_excerpt, style_guide, music_mood)
   while assembly still uses `visual_query` → nothing breaks.
3. Script approval gate: `script_ready` status, Script Review UI, `/render`.
4. `regenerate_script(script, feedback)` + endpoint + UI textbox (Approach 3).
5. Voices: expand presets, paste-any-voice-ID, stability/style sliders.
Outcome: better scripts, user controls what gets rendered, feedback loop.

### Phase 2 — visuals, captions, music
6. `voiceover.py` → timestamps endpoint, save `words.json` next to mp3.
7. `visuals.py` with fal.ai Flux + Pexels fallback; generate larger-than-frame.
8. `video_creator.py` rewrite: image clips + motion, scene cuts on excerpt
   ends, captions overlay, music mix. Keep 720×1280 for Railway memory.
9. `captions.py` (Pillow) + bundled font.
10. `music.py` + upload starter tracks to R2.
11. Job-level `visual_mode` toggle (stock vs ai_images) for A/B comparison.
Outcome: visuals match the script, word captions, music. The product changes.

### Phase 3 — optional polish
12. Image-to-video for 1–2 hero scenes per Short (Kling / Runway / Veo via
    fal.ai), toggle per job, cost shown before render.
13. Per-scene "regenerate this image" button on the preview page.
14. Approach 1 (few-shot from approved scripts) once 10+ approvals exist.
15. Weekly schedule (existing task #14) — only after Phase 1 gate exists,
    since scheduled runs need a "no-review" mode.

---

## 5. Risks / notes
- Railway worker memory: images are lighter than stock video, but Pillow
  caption overlays × many words add clips. Group captions (2–3 words) and
  pre-render to a single overlay track per scene if needed.
- fal.ai / ElevenLabs timestamp API shapes: verify with one real call before
  writing parsers.
- Supabase free tier pauses after inactivity; a scheduled run will fail if the
  DB is asleep. Upgrade or add a keep-alive ping before enabling schedules.
- Visual consistency across scenes is the #1 quality lever; `style_guide` +
  repeated subject wording is the cheap fix. Seed pinning per job is a
  possible upgrade.
- Remove leftover R2 debug logging in `backend/storage.py`.
