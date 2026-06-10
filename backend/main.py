"""
main.py — FastAPI backend for YouTube Shorts Agent
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid

from config import get_settings
from auth import get_current_user
from database import (
    create_job, get_job, get_user_jobs,
    update_user, get_user_logs, log_action
)
try:
    from tasks import generate_video_task, upload_to_platforms_task
    CELERY_AVAILABLE = True
except Exception:
    CELERY_AVAILABLE = False
    generate_video_task = None
    upload_to_platforms_task = None

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
    topic: str
    style: str = "educational"
    narration_style: Optional[str] = None   # e.g. "David Attenborough", "energetic host"
    voice_id: Optional[str] = None
    duration: int = 45
    platform: list[str] = ["youtube"]
    privacy: str = "private"


@app.post("/jobs")
async def create_job_endpoint(
    body: CreateJobRequest,
    user: dict = Depends(get_current_user)
):
    """
    Submit a new video generation job.
    Returns immediately with job ID — generation runs in background.
    """
    if not body.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be empty")

    if body.duration < 15 or body.duration > 60:
        raise HTTPException(status_code=400, detail="Duration must be between 15 and 60 seconds")

    params = {
        "topic": body.topic.strip(),
        "style": body.style,
        "narration_style": body.narration_style or "",
        "voice_id": body.voice_id or user.get("default_voice_id"),
        "duration": body.duration,
        "platform": body.platform,
        "privacy": body.privacy,
        "status": "pending",
        "progress": 0,
        "current_step": "Queued...",
    }

    job = create_job(user["id"], params)

    # Kick off background task
    if CELERY_AVAILABLE:
        generate_video_task.delay(job["id"], user["id"], params)

    log_action(user["id"], "job_queued", job_id=job["id"],
               message=f"Job queued: {body.topic[:50]}")

    return {
        "job_id": job["id"],
        "status": "pending",
        "message": "Video generation started",
    }


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
