"""
main.py — FastAPI backend for YouTube Shorts Agent
"""
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
import os
import uuid
import json

from config import get_settings
from auth import get_current_user
from database import (
    create_job, get_job, get_user_jobs,
    update_user, get_user_logs, log_action
)
try:
    from tasks import (generate_script_task, regenerate_script_task, render_video_task,
                       generate_video_task, upload_to_platforms_task)
    CELERY_AVAILABLE = True
except Exception:
    CELERY_AVAILABLE = False
    generate_script_task = regenerate_script_task = render_video_task = None
    generate_video_task = upload_to_platforms_task = None

settings = get_settings()

app = FastAPI(title="YouTube Shorts Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_origin_regex=r"https://youtube-agent-frontend.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health Check ──────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}




# ── Users ─────────────────────────────────────────────────────

@app.get("/users/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current user profile."""
    # Don't expose encrypted tokens to frontend
    safe_user = {k: v for k, v in user.items()
                 if k not in ("youtube_token", "instagram_token")}
    safe_user["has_youtube"] = bool(user.get("youtube_token"))
    safe_user["has_instagram"] = bool(user.get("instagram_token"))
    return safe_user


class UpdatePreferencesRequest(BaseModel):
    default_voice_id: Optional[str] = None
    default_style: Optional[str] = None
    default_duration: Optional[int] = None
    name: Optional[str] = None


@app.patch("/users/me")
async def update_preferences(
    body: UpdatePreferencesRequest,
    user: dict = Depends(get_current_user)
):
    """Update user preferences."""
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = update_user(user["id"], data)
    return {"success": True, "user": updated}


@app.get("/users/me/logs")
async def get_logs(user: dict = Depends(get_current_user)):
    """Get activity log for current user."""
    return get_user_logs(user["id"])


# ── Jobs ──────────────────────────────────────────────────────

class CreateJobRequest(BaseModel):
    topic: str = ""
    style: str = "educational"
    narration_style: Optional[str] = None   # preset key or free text
    voice_id: Optional[str] = None
    duration: int = 45
    platform: list[str] = ["youtube"]
    privacy: str = "private"
    input_mode: str = "idea"                # "idea" | "text"
    source_text: Optional[str] = None       # used verbatim when input_mode == "text"
    auto_render: bool = False               # skip the script review gate (scheduled runs)
    visual_mode: Optional[str] = None       # "ai_images" | "stock" (default from user/env)
    language: str = "auto"                  # idea mode: narration language ("auto" = match request)
    tts_model: Optional[str] = None         # ElevenLabs model id (default from env)
    voice_settings: Optional[dict] = None   # {stability, similarity_boost, style, speed}


def _script_helpers():
    """Lazy import of the agent module (lives in /agent inside the container)."""
    import sys
    for p in ("/agent", os.path.join(os.path.dirname(__file__), "..")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from script_generator import validate_source_text, NARRATION_PRESETS, MAX_WORDS
    return validate_source_text, NARRATION_PRESETS, MAX_WORDS


@app.get("/script/presets")
async def script_presets():
    """Narration presets + length limits for the create form."""
    _, presets, max_words = _script_helpers()
    return {
        "presets": [{"key": k, "description": v} for k, v in presets.items()],
        "max_words": max_words,
        "words_per_second": 2.5,
        "max_seconds": 60,
    }


_voices_cache = {"at": 0.0, "data": None}


@app.get("/voices")
async def voices(user: dict = Depends(get_current_user)):
    """ElevenLabs voices available to this account (premade + anything added to My Voices),
    plus the TTS model options. Cached 10 minutes."""
    import time, sys
    for p in ("/agent", os.path.join(os.path.dirname(__file__), "..")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from voiceover import list_voices, TTS_MODELS, DEFAULT_VOICE_SETTINGS

    if not _voices_cache["data"] or time.time() - _voices_cache["at"] > 600:
        try:
            _voices_cache["data"] = list_voices()
            _voices_cache["at"] = time.time()
        except Exception as e:
            if not _voices_cache["data"]:
                raise HTTPException(status_code=502, detail=f"Could not load voices: {e}")
    return {
        "voices": _voices_cache["data"],
        "models": [{"id": k, "label": v[0], "notes": v[1]} for k, v in TTS_MODELS.items()],
        "default_model": os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
        "default_settings": DEFAULT_VOICE_SETTINGS,
    }


@app.post("/script/validate")
async def script_validate(body: dict):
    """Live check for pasted text length (no auth needed; nothing stored)."""
    validate_source_text, _, _ = _script_helpers()
    return validate_source_text(body.get("text", "") or "")


@app.post("/jobs")
async def create_job_endpoint(
    body: CreateJobRequest,
    user: dict = Depends(get_current_user)
):
    """
    Submit a new video generation job.
    Returns immediately with job ID — generation runs in background.
    """
    input_mode = body.input_mode if body.input_mode in ("idea", "text") else "idea"
    source_text = (body.source_text or "").strip()
    topic = body.topic.strip()

    if input_mode == "text":
        validate_source_text, _, _ = _script_helpers()
        check = validate_source_text(source_text)
        if not check["ok"]:
            raise HTTPException(status_code=400, detail=check["message"])
        if not topic:
            topic = source_text[:80]          # display label for the job list
        duration = check["est_seconds"]
    else:
        if not topic:
            raise HTTPException(status_code=400, detail="Topic cannot be empty")
        if body.duration < 15 or body.duration > 60:
            raise HTTPException(status_code=400, detail="Duration must be between 15 and 60 seconds")
        duration = body.duration

    params = {
        "topic": topic,
        "style": body.style,
        "narration_style": body.narration_style or "",
        "voice_id": (body.voice_id or user.get("default_voice_id") or "").strip() or None,
        "tts_model": body.tts_model or None,
        "voice_settings": body.voice_settings or None,
        "duration": duration,
        "platform": body.platform,
        "privacy": body.privacy,
        "input_mode": input_mode,
        "source_text": source_text if input_mode == "text" else None,
        "language": (body.language or "auto").strip().lower()[:8],
        "auto_render": bool(body.auto_render),
        "visual_mode": (body.visual_mode if body.visual_mode in ("ai_images", "stock")
                        else user.get("default_visual_mode") or os.getenv("DEFAULT_VISUAL_MODE", "ai_images")),
        "status": "pending",
        "progress": 0,
        "current_step": "Queued...",
    }

    job = create_job(user["id"], params)

    # Stage 1 only: write the script, then wait for review (unless auto_render)
    if CELERY_AVAILABLE:
        generate_script_task.delay(job["id"], user["id"], params)

    log_action(user["id"], "job_queued", job_id=job["id"],
               message=f"Job queued: {topic[:50]}")

    return {
        "job_id": job["id"],
        "status": "pending",
        "message": "Writing script",
    }


def _owned_job(job_id: str, user: dict) -> dict:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return job


class ScriptEditRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    narration: Optional[str] = None
    music_mood: Optional[str] = None
    scenes: Optional[list[dict]] = None     # [{id, visual_prompt?, caption?, motion?}]


@app.patch("/jobs/{job_id}/script")
async def edit_script(job_id: str, body: ScriptEditRequest, user: dict = Depends(get_current_user)):
    """Save the user's manual edits from the Script Review screen."""
    from database import update_job
    job = _owned_job(job_id, user)
    if job["status"] != "script_ready":
        raise HTTPException(status_code=400, detail=f"Script can't be edited in status '{job['status']}'")

    import sys
    for p in ("/agent", os.path.join(os.path.dirname(__file__), "..")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from script_generator import apply_script_edits, MAX_WORDS

    edits = {k: v for k, v in body.model_dump().items() if v is not None}
    if "narration" in edits and len(edits["narration"].split()) > MAX_WORDS:
        raise HTTPException(status_code=400, detail=f"Narration is over {MAX_WORDS} words — too long for a Short.")

    try:
        new_script = apply_script_edits(job["script"], edits)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    update_job(job_id, {"script": new_script})
    log_action(user["id"], "script_edited", job_id=job_id, message=", ".join(edits.keys()))
    return {"success": True, "script": new_script}


class RegenerateRequest(BaseModel):
    feedback: str


@app.post("/jobs/{job_id}/regenerate")
async def regenerate_job_script(job_id: str, body: RegenerateRequest, user: dict = Depends(get_current_user)):
    """Rewrite the script from free-text feedback; job returns to script_ready."""
    from database import update_job
    job = _owned_job(job_id, user)
    if job["status"] not in ("script_ready", "failed", "rejected"):
        raise HTTPException(status_code=400, detail=f"Can't regenerate in status '{job['status']}'")
    if not job.get("script"):
        raise HTTPException(status_code=400, detail="No script to regenerate yet")
    feedback = body.feedback.strip()
    if len(feedback) < 3:
        raise HTTPException(status_code=400, detail="Tell me what to change.")

    update_job(job_id, {"status": "scripting", "progress": 10,
                        "current_step": "Rewriting script from your feedback..."})
    if CELERY_AVAILABLE:
        regenerate_script_task.delay(job_id, user["id"], feedback)
    return {"success": True, "message": "Rewriting script"}


@app.post("/jobs/{job_id}/render")
async def render_job(job_id: str, user: dict = Depends(get_current_user)):
    """User approved the script — render voice + video."""
    from database import update_job
    job = _owned_job(job_id, user)
    if job["status"] not in ("script_ready", "failed", "preview_ready", "rejected"):
        raise HTTPException(status_code=400, detail=f"Can't render in status '{job['status']}'")
    if not job.get("script"):
        raise HTTPException(status_code=400, detail="No script to render yet")

    update_job(job_id, {"status": "rendering", "progress": 35,
                        "current_step": "Starting render...", "error_message": None})
    if CELERY_AVAILABLE:
        render_video_task.delay(job_id, user["id"])
    log_action(user["id"], "render_started", job_id=job_id)
    return {"success": True, "message": "Rendering"}


@app.get("/jobs")
async def list_jobs(user: dict = Depends(get_current_user)):
    """Get all jobs for current user."""
    return get_user_jobs(user["id"])


@app.get("/jobs/{job_id}")
async def get_job_endpoint(job_id: str, user: dict = Depends(get_current_user)):
    """Get a single job with status and video info."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return job


class ApproveJobRequest(BaseModel):
    platforms: list[str] = ["youtube"]


@app.post("/jobs/{job_id}/approve")
async def approve_job(
    job_id: str,
    body: ApproveJobRequest,
    user: dict = Depends(get_current_user)
):
    """
    User approves the preview — triggers upload to YouTube/Instagram.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    if job["status"] in ("uploading", "done"):
        return {"success": True, "message": "Already uploaded", "status": job["status"]}
    if job["status"] != "preview_ready":
        raise HTTPException(status_code=400,
                            detail=f"Job is not ready for approval (status: {job['status']})")

    videos = job.get("videos", [])
    if not videos:
        raise HTTPException(status_code=400, detail="No video found for this job")

    video_id = videos[0]["id"]

    # Get user's YouTube token if needed
    youtube_token = user.get("youtube_token") if "youtube" in body.platforms else None

    # Kick off upload task
    if CELERY_AVAILABLE:
        upload_to_platforms_task.delay(
            job_id, user["id"], video_id,
            body.platforms, youtube_token
        )

    log_action(user["id"], "upload_approved", job_id=job_id,
               message=f"Upload approved for: {', '.join(body.platforms)}")

    return {"success": True, "message": "Upload started"}


class RejectRequest(BaseModel):
    reason: Optional[str] = None


@app.post("/jobs/{job_id}/reject")
async def reject_job(job_id: str, body: RejectRequest, user: dict = Depends(get_current_user)):
    """
    User rejects the rendered preview. Deletes the video/audio from R2, clears the
    video URLs, marks the job `rejected`. The script, logs and the reason are kept —
    the user can rewrite the script or re-render from here.
    """
    from database import update_job, update_video
    from storage import delete_job_files
    job = _owned_job(job_id, user)
    if job["status"] != "preview_ready":
        raise HTTPException(status_code=400, detail=f"Nothing to reject in status '{job['status']}'")

    delete_job_files(user["id"], job_id)

    for v in job.get("videos") or []:
        update_video(v["id"], {"video_url": None, "audio_url": None})

    reason = (body.reason or "").strip()
    history = list(job.get("feedback_history") or [])
    history.append({"rejected": True, "feedback": reason or "(no reason given)",
                    "title_before": (job.get("script") or {}).get("title")})

    update_job(job_id, {
        "status": "rejected",
        "current_step": "Preview rejected",
        "feedback_history": history,
        "progress": 30,
    })
    log_action(user["id"], "preview_rejected", job_id=job_id, message=reason or "no reason")
    return {"success": True, "status": "rejected"}


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, user: dict = Depends(get_current_user)):
    """Cancel a pending or failed job."""
    from database import update_job
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    update_job(job_id, {"status": "cancelled"})
    log_action(user["id"], "job_cancelled", job_id=job_id)
    return {"success": True}


# ── YouTube OAuth ─────────────────────────────────────────────

@app.get("/auth/youtube/connect")
async def youtube_connect_direct(user_id: str):
    """
    Direct connect endpoint — no Clerk auth needed.
    Visit /auth/youtube/connect?user_id=YOUR_USER_ID in browser.
    Builds auth URL manually (no google_auth_oauthlib) to avoid PKCE being added.
    """
    import urllib.parse
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube.upload",
        "access_type": "offline",
        "prompt": "consent",
        "state": user_id,
    }
    auth_url = "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(params)
    return RedirectResponse(auth_url)


@app.get("/auth/youtube/url")
async def youtube_auth_url(user: dict = Depends(get_current_user)):
    """Return the Google OAuth URL for the frontend to redirect to.
    Builds auth URL manually (no google_auth_oauthlib) to avoid PKCE being added.
    """
    import urllib.parse
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube.upload",
        "access_type": "offline",
        "prompt": "consent",
        "state": user["id"],
    }
    auth_url = "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(params)
    return {"url": auth_url}


@app.get("/auth/youtube/callback")
async def youtube_callback(request: Request):
    """Handle Google OAuth callback, store token in user record."""
    from database import update_user
    import requests as http_requests

    code = request.query_params.get("code")
    state = request.query_params.get("state")  # this is the user_id we passed

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    # Exchange code for token directly — avoids PKCE mismatch from recreating Flow
    token_response = http_requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        }
    )
    token_result = token_response.json()

    if "error" in token_result:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_result}")

    # Store token as JSON in user record (include expiry so refresh works correctly)
    import datetime
    expires_in = token_result.get("expires_in", 3600)
    expiry = (datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)).isoformat() + "Z"
    token_data = json.dumps({
        "token": token_result.get("access_token"),
        "refresh_token": token_result.get("refresh_token"),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "scopes": token_result.get("scope", "").split(),
        "expiry": expiry,
    })

    update_user(state, {"youtube_token": token_data})
    log_action(state, "youtube_connected", message="YouTube account connected")

    # Redirect back to frontend
    return RedirectResponse(f"{settings.frontend_url}/dashboard?youtube=connected")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
