# YouTube Shorts Agent — Project Checklist

---

## ✅ Phase 1 — Local Agent (Done)

### Setup
- [x] Project folder created (`youtube-agent/`)
- [x] `requirements.txt` with all dependencies
- [x] `.env.template` and `.env` with API keys
- [x] `.gitignore` (secrets excluded from git)
- [x] Pushed to GitHub (`baljeetsbal/Youtube-Agent`)

### API Keys
- [x] Anthropic API key (script generation)
- [x] ElevenLabs API key (voiceover)
- [x] Pexels API key (stock footage) — verified
- [x] YouTube OAuth credentials (`client_secrets.json`)
- [x] YouTube test user added

### Pipeline Modules
- [x] `script_generator.py` — Claude AI, Attenborough style
- [x] `voiceover.py` — ElevenLabs TTS
- [x] `video_creator.py` — Pexels + MoviePy + FFmpeg
- [x] `youtube_uploader.py` — YouTube Data API v3
- [x] `main.py` — full orchestrator + CLI
- [x] End-to-end pipeline runs successfully

---

## 🔧 Phase 2 — Quality Improvements (Pending)

### Voice
- [ ] Switch to ElevenLabs "Daniel" voice (British, deep, calm)
- [ ] Add per-video voice selection in CLI
- [ ] Tune voice settings (stability, speed, style)

### Video
- [ ] Confirm Pexels stock footage working (post-verification)
- [ ] Add background music (Suno AI or Epidemic Sound)
- [ ] Improve text captions (font, position, animation)
- [ ] Add intro/outro frames

### Script
- [ ] Fine-tune Attenborough/Nolan prompt further
- [ ] Add more style options (dark, cosmic, intimate)
- [ ] Allow script preview/edit before voiceover

---

## 🌐 Phase 3 — Web Platform (Future)

### Frontend
- [ ] React / Next.js web app
- [ ] User login (Clerk or Auth0)
- [ ] Input form: topic, voice, style, duration
- [ ] Video preview player before upload
- [ ] Upload approval button

### Backend
- [ ] FastAPI backend (Python)
- [ ] PostgreSQL database (Supabase or Railway)
- [ ] Celery + Redis job queue for async video generation
- [ ] Cloudflare R2 / S3 for video storage
- [ ] Per-user encrypted credential storage

### Per-user Credentials
- [ ] Each user connects their own YouTube account
- [ ] Each user connects their own Instagram account
- [ ] Admin panel to manage users

### Social Publishing
- [ ] YouTube Data API v3 (per user channel)
- [ ] Instagram Reels via Meta Graph API
- [ ] Scheduled weekly uploads

### Deployment
- [ ] Backend deployed on Railway or Render
- [ ] Frontend deployed on Vercel
- [ ] Redis deployed on Railway
- [ ] Domain + SSL configured

---

## 🚀 Phase 4 — Upgrades (Optional)

### Better Tools
- [ ] Runway Gen-3 for AI-generated video (replace stock footage)
- [ ] Cartesia or PlayHT as ElevenLabs alternatives
- [ ] Storyblocks for premium stock footage
- [ ] Epidemic Sound for background music
- [ ] Suno AI for custom AI-generated music

### Analytics
- [ ] Track views, likes, retention per video
- [ ] A/B test different voice/style combos
- [ ] Weekly performance report

---

## 📋 Quick Reference — Run Commands

```bash
# Create video (interactive)
python main.py

# Create video (direct, no upload)
python main.py --topic "your idea here" --no-upload

# Create and upload as private
python main.py --topic "your idea here"

# Create and upload as public
python main.py --topic "your idea here" --privacy public
```
