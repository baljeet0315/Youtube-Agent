# YouTube Shorts Agent — Setup Guide

## Overview

This agent takes a topic idea and automatically:
1. **Generates a script** (Claude AI)
2. **Creates a voiceover** (ElevenLabs TTS)
3. **Assembles a vertical video** (Pexels stock footage + captions via MoviePy)
4. **Uploads to YouTube** (YouTube Data API v3)

---

## Step 1 — Install Dependencies

You need Python 3.9+ and FFmpeg.

**Install FFmpeg (required for video rendering):**
- macOS: `brew install ffmpeg`
- Windows: Download from https://ffmpeg.org/download.html and add to PATH
- Ubuntu: `sudo apt install ffmpeg`

**Install Python packages:**
```bash
cd youtube-agent
pip install -r requirements.txt
```

---

## Step 2 — Get Your API Keys

### A. Anthropic API Key (Script Generation)
1. Go to https://console.anthropic.com/keys
2. Click **Create Key**
3. Copy the key → paste into `.env` as `ANTHROPIC_API_KEY`

### B. ElevenLabs API Key (Voiceover)
1. Go to https://elevenlabs.io — sign up (free tier: 10,000 chars/month)
2. Click your avatar → **Profile Settings** → **API Keys**
3. Copy the key → paste into `.env` as `ELEVENLABS_API_KEY`
4. (Optional) To change the voice:
   - Run `python main.py --list-voices` to see available voices
   - Copy the voice ID → paste into `.env` as `ELEVENLABS_VOICE_ID`

### C. Pexels API Key (Stock Footage)
1. Go to https://www.pexels.com/api/ — sign up (free, no limits for personal use)
2. Click **Your API Key** → copy
3. Paste into `.env` as `PEXELS_API_KEY`

### D. YouTube API + OAuth2 (Upload)
1. Go to https://console.cloud.google.com/
2. Create a new project (or select an existing one)
3. Enable the **YouTube Data API v3**:
   - APIs & Services → Library → search "YouTube Data API v3" → Enable
4. Create OAuth2 credentials:
   - APIs & Services → Credentials → **Create Credentials** → OAuth client ID
   - Application type: **Desktop app**
   - Click **Create** → **Download JSON**
5. Rename the downloaded file to `client_secrets.json`
6. Place it inside the `youtube-agent/` folder
7. Set OAuth consent screen:
   - APIs & Services → OAuth consent screen
   - User type: **External**
   - Add your Google account email under **Test users**

---

## Step 3 — Configure Your .env File

```bash
cp .env.template .env
```

Open `.env` and fill in all values:
```
ANTHROPIC_API_KEY=sk-ant-...
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB
PEXELS_API_KEY=...
YOUTUBE_CLIENT_SECRETS_FILE=client_secrets.json
```

---

## Step 4 — Run Your First Video

### Interactive mode (recommended for first run):
```bash
python main.py
```
You'll be prompted for a topic and style. The video will be uploaded as **private** so you can review it first.

### Direct mode:
```bash
# Create video and upload as private
python main.py --topic "Why the sky is blue" --style educational

# Create video only (no upload)
python main.py --topic "5 morning habits" --style motivational --no-upload

# Upload as public immediately
python main.py --topic "Quick history of the internet" --privacy public

# 60-second video
python main.py --topic "How black holes work" --duration 60
```

### First YouTube upload:
- A browser window will open for Google authorization
- Log in and allow access
- The token is saved to `youtube_token.pickle` — future uploads won't need the browser

---

## Step 5 — Schedule Weekly Uploads

To upload automatically every week, tell Claude:
> "Schedule the YouTube agent to run every Monday at 9am"

Or use cron (macOS/Linux):
```bash
# Edit crontab
crontab -e

# Add this line (runs every Monday at 9:00 AM)
0 9 * * 1 cd /path/to/youtube-agent && python main.py --topic "YOUR TOPIC" --privacy public
```

---

## File Structure

```
youtube-agent/
├── main.py               # Main orchestrator + CLI
├── script_generator.py   # Claude script generation
├── voiceover.py          # ElevenLabs TTS
├── video_creator.py      # Pexels footage + MoviePy assembly
├── youtube_uploader.py   # YouTube Data API upload
├── config.py             # Config + env loading
├── requirements.txt      # Python dependencies
├── .env.template         # Copy to .env and fill in keys
├── .env                  # Your API keys (DO NOT commit to git!)
├── client_secrets.json   # YouTube OAuth2 (DO NOT commit to git!)
├── youtube_token.pickle  # Auto-generated after first auth
└── output/
    ├── audio/            # Generated MP3 voiceovers
    ├── footage/          # Downloaded stock clips (cached)
    └── videos/           # Final rendered videos
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ffmpeg not found` | Install FFmpeg and add to PATH |
| `ElevenLabs 401 error` | Check your API key in .env |
| `Pexels 403 error` | Check your Pexels API key |
| `client_secrets.json not found` | Download from Google Cloud Console (see Step 2D) |
| `YouTube quota exceeded` | Default quota is 10,000 units/day; each upload costs ~1,600 units |
| `TextClip error / ImageMagick` | Install ImageMagick: `brew install imagemagick` (macOS) |
| Video renders but has no audio | Check that FFmpeg has AAC codec support |

---

## Tips for Better Videos

- **Hooks matter**: The first 3 seconds determine if people keep watching
- **Keep it under 60s**: YouTube Shorts are most promoted when under 60 seconds
- **Upload as private first**: Review the video before making it public
- **Add #Shorts**: The agent does this automatically
- **Batch ideas**: Run the agent multiple times with different topics and schedule the uploads

---

*Built with Claude AI, ElevenLabs, Pexels, and MoviePy*
