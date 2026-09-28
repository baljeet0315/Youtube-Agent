# Video Agent — faceless YouTube Shorts, end to end

Type an idea (or paste your own text), approve the script, get a finished vertical
video with AI-generated visuals, word-level captions, music and a voiceover — then
post it to YouTube in one tap. Multi-user: each person signs in with Google and
connects their own channel.

**Live app:** https://youtube-agent-frontend-ivory.vercel.app
**Getting-started guide for new users:** `docs/getting-started-guide.png` — one image, six steps with screenshots

---

## How it works

```
 idea / pasted text
        │
        ▼
  ┌─────────────┐   Claude writes narration, title, scene list,
  │ Script      │   per-scene visual prompts, music mood
  └─────────────┘
        │  status: script_ready  ──►  user reviews / edits / "rewrite it" with feedback
        ▼
  ┌─────────────┐   ElevenLabs TTS + per-word timestamps
  │ Voice       │
  └─────────────┘
        │
  ┌─────────────┐   fal.ai Flux: one image per scene (stable seed), Pexels fallback
  │ Visuals     │
  └─────────────┘
        │
  ┌─────────────┐   Pillow-rendered pop captions, mood-matched music track
  │ Captions    │
  │ Music       │
  └─────────────┘
        │
  ┌─────────────┐   Ken Burns motion, cuts on sentence ends, 2 s tail + fade,
  │ Assemble    │   720×1280 mp4 → Cloudflare R2
  └─────────────┘
        │  status: preview_ready  ──►  user watches preview
        ▼
  ┌─────────────┐   YouTube Data API v3 (user's own OAuth token)
  │ Upload      │
  └─────────────┘
```

Job statuses: `pending → scripting → script_ready → rendering → preview_ready → uploading → done` (or `failed`).

One reasoning agent (script) and five deterministic tool-agents, orchestrated by
three Celery tasks (`generate_script_task → render_video_task → upload_to_platforms_task`).

---

## Stack

| Layer | Tech | Hosted on |
|---|---|---|
| Frontend | Next.js 14 (App Router), Tailwind, Clerk auth | Vercel |
| API | FastAPI, Celery producer | Railway — `web` service |
| Worker | Celery + Redis, MoviePy/FFmpeg, Pillow | Railway — `worker` service (same image, different start command) |
| Database | Supabase Postgres (PostgREST) | Supabase |
| Object storage | Cloudflare R2 (S3 API) | Cloudflare |
| LLM | Anthropic Claude (`claude-opus-4-6`) | — |
| TTS | ElevenLabs (`eleven_multilingual_v2` default) | — |
| Images | fal.ai Flux schnell | — |
| Stock fallback | Pexels | — |

---

## Repo layout

```
youtube-agent/
├── script_generator.py     Script agent: idea/text modes, presets, schema v2, rewrite-with-feedback
├── voiceover.py            ElevenLabs TTS (+ /with-timestamps), voice list, tuning
├── visuals.py              fal.ai image per scene, ImageProvider interface, Pexels fallback
├── captions.py             Word-group captions rendered with Pillow (script-aware fonts)
├── music.py                Mood → track (assets/music/<mood>/ or R2 music/<mood>/)
├── video_creator.py        Assembly: Ken Burns, timestamp cuts, captions, music, tail
├── youtube_uploader.py     YouTube Data API upload with stored OAuth token
├── config.py               Agent config from env (copied into the image as agent_config.py)
├── assets/music/<mood>/    Drop royalty-free mp3s here (see assets/music/README.md)
│
├── backend/
│   ├── main.py             FastAPI routes (jobs, script review, render, regenerate, voices, OAuth)
│   ├── tasks.py            Celery tasks (script / regenerate / render / upload)
│   ├── auth.py             Clerk JWT verification → get_or_create_user
│   ├── database.py         Supabase helpers
│   ├── storage.py          R2 upload
│   ├── config.py           Backend settings (pydantic-settings)
│   └── Dockerfile          Shared image for web + worker
│
├── frontend/
│   └── src/app/dashboard/  Create page, job page (review → preview → post), videos, settings
│
├── database/
│   ├── schema.sql          Full schema (reference)
│   └── migrations/         Dated SQL to run in Supabase SQL Editor, in order
│
├── PHASE2_PLAN.md          Architecture decisions + roadmap
├── SETUP_GUIDE.md          Legacy: running the original CLI pipeline locally
└── CHECKLIST.md            Legacy deployment checklist
```

---

## Environment variables

Set in **Railway → Variables** on *both* services (web and worker), and in Vercel for the frontend.
Never commit real values; `.env` is gitignored and only used for local runs.

**Backend / worker**

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Script generation |
| `ELEVENLABS_API_KEY` | Voiceover |
| `ELEVENLABS_MODEL` | Default TTS model (`eleven_multilingual_v2`) |
| `FAL_KEY` | Scene image generation (without it → stock footage) |
| `PEXELS_API_KEY` | Stock footage fallback |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Database |
| `CLERK_SECRET_KEY` | Verify frontend JWTs |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET_NAME`, `R2_PUBLIC_URL` | Video/preview storage. Endpoint has **no** bucket suffix. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | YouTube OAuth (Web application client) |
| `REDIS_URL` | Celery broker |
| `FRONTEND_URL` | CORS + OAuth redirect target |
| `DEFAULT_VISUAL_MODE` | `ai_images` (default) or `stock` |
| `TAIL_SECONDS`, `MUSIC_VOLUME`, `CAPTIONS_ENABLED`, `VIDEO_WIDTH/HEIGHT/FPS` | Render tuning (optional) |

**Frontend (Vercel)**

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Railway web service URL |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` | Clerk |

Clerk needs a JWT template named **`Youtube-agent-emailID`** with claims
`{"email": "{{user.primary_email_address.email_address}}", "name": "{{user.full_name}}", "image_url": "{{user.image_url}}"}`.

---

## Deploying changes

```bash
git add -A
git commit -m "..."
git push
```

- **Frontend** → Vercel auto-deploys from `main` (root directory `frontend`).
- **Backend** → redeploy the Railway service(s) that changed:
  `backend/main.py` → web; anything in the agent modules or `tasks.py` → worker;
  `Dockerfile` → both.
- **Schema** → run the newest file in `database/migrations/` in Supabase → SQL Editor.

Free tiers pause when idle (Railway, Supabase). First request after a break may fail once — retry.

---

## Local development

```bash
# Backend
cd backend && pip install -r requirements.txt   # or mirror the Dockerfile pip installs
cp ../.env.template ../.env                      # fill in keys
uvicorn main:app --reload --port 8000
celery -A tasks worker --loglevel=info           # separate terminal, needs Redis

# Frontend
cd frontend && npm install && npm run dev
```

Agent modules can be exercised alone:
`python script_generator.py "why cats purr"` · `python script_generator.py --text "Your paragraph…"` ·
`python video_creator.py script.json voice.mp3 words.json`.

---

## Roadmap

Done: Phase 1 (script modes, review gate, feedback rewrite, voice picker) and
Phase 2 (AI images + motion, word captions, music, timestamp cuts), mobile UI.

Next (see `PHASE2_PLAN.md` §4 Phase 3):
1. Few-shot learning from approved scripts (needs ~10 approvals first)
2. Per-scene "regenerate this image"
3. Image-to-video for 1–2 hero scenes per Short
4. Weekly scheduled posting (needs a no-review mode)
5. Remove R2 debug logging in `backend/storage.py`

---

## Security notes

- Secrets live only in Railway/Vercel variables and local `.env`. Never in chat, commits, or docs.
- Each user's YouTube token is stored per user in Supabase (`users.youtube_token`) and refreshed
  before every upload. Users can re-authorise from Settings → Reconnect.
- The Google OAuth app is published (production) so any Google account can connect.
