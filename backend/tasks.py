"""
tasks.py — Celery background tasks for video generation pipeline
"""
import os
import sys
import json
from celery import Celery
from config import get_settings
from database import update_job, create_video, log_action
from storage import upload_file

settings = get_settings()

# Add agent directory to path
sys.path.insert(0, "/agent")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

celery_app = Celery(
    "youtube_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
)


def set_progress(job_id: str, user_id: str, progress: int, step: str, status: str = "processing"):
    """Update job progress in DB."""
    update_job(job_id, {
        "status": status,
        "progress": progress,
        "current_step": step,
    })
    log_action(user_id, "job_progress", job_id=job_id,
               message=step, metadata={"progress": progress})


def _fail(self, job_id: str, user_id: str, e: Exception, action: str):
    error_msg = str(e)
    update_job(job_id, {"status": "failed", "error_message": error_msg, "current_step": "Failed"})
    log_action(user_id, action, job_id=job_id, level="error", message=error_msg)
    raise self.retry(exc=e, countdown=10)


# ── Stage 1: script only → script_ready ─────────────────────────────────────

@celery_app.task(bind=True, max_retries=1)
def generate_script_task(self, job_id: str, user_id: str, params: dict):
    """Generate the script and stop for user review (script_ready)."""
    try:
        from script_generator import generate_script

        input_mode = params.get("input_mode", "idea")
        set_progress(job_id, user_id, 15,
                     "Building script around your text..." if input_mode == "text"
                     else "Writing script...", status="scripting")

        script = generate_script(
            params.get("topic", ""),
            style=params.get("style", "educational"),
            duration_seconds=params.get("duration", 45),
            narration_style=params.get("narration_style", ""),
            input_mode=input_mode,
            source_text=params.get("source_text") or "",
        )

        update_job(job_id, {
            "script": script,
            "status": "script_ready",
            "progress": 30,
            "current_step": "Script ready — review before rendering",
        })
        log_action(user_id, "script_ready", job_id=job_id,
                   message=f"Script: {script.get('title', '')}")

        if params.get("auto_render"):
            render_video_task.delay(job_id, user_id)

    except Exception as e:
        _fail(self, job_id, user_id, e, "script_failed")


# ── Stage 1b: regenerate script from feedback → script_ready ────────────────

@celery_app.task(bind=True, max_retries=1)
def regenerate_script_task(self, job_id: str, user_id: str, feedback: str):
    try:
        from database import get_job
        from script_generator import regenerate_script

        job = get_job(job_id)
        if not job or not job.get("script"):
            raise ValueError("No script to regenerate")

        set_progress(job_id, user_id, 15, "Rewriting script from your feedback...", status="scripting")
        new_script = regenerate_script(job["script"], feedback)

        history = list(job.get("feedback_history") or [])
        history.append({"feedback": feedback, "title_before": job["script"].get("title")})

        update_job(job_id, {
            "script": new_script,
            "status": "script_ready",
            "progress": 30,
            "current_step": "Revised script ready — review before rendering",
            "feedback_history": history,
            "regeneration_count": int(job.get("regeneration_count") or 0) + 1,
        })
        log_action(user_id, "script_regenerated", job_id=job_id, message=feedback[:200])

    except Exception as e:
        _fail(self, job_id, user_id, e, "regenerate_failed")


# ── Stage 2: voice → footage → assemble → R2 → preview_ready ────────────────

@celery_app.task(bind=True, max_retries=2)
def render_video_task(self, job_id: str, user_id: str):
    """Render the approved script into a video."""
    import tempfile

    try:
        from database import get_job
        from voiceover import generate_voiceover
        from video_creator import create_video as assemble_video
        import agent_config

        job = get_job(job_id)
        if not job or not job.get("script"):
            raise ValueError("Job has no script to render")
        script = job["script"]
        voice_id = job.get("voice_id") or agent_config.ELEVENLABS_VOICE_ID

        with tempfile.TemporaryDirectory() as tmpdir:
            # ── Step 2: Voiceover ────────────────────────────────
            set_progress(job_id, user_id, 40, "Generating voiceover...", status="rendering")
            audio_path = os.path.join(tmpdir, "voice.mp3")

            # Temporarily override voice ID if user selected one
            original_voice = agent_config.ELEVENLABS_VOICE_ID
            agent_config.ELEVENLABS_VOICE_ID = voice_id
            generate_voiceover(script["narration"], output_filename="voice.mp3")
            agent_config.ELEVENLABS_VOICE_ID = original_voice

            # The voiceover module saves to OUTPUT_DIR/audio/
            import shutil
            src_audio = os.path.join(agent_config.OUTPUT_DIR, "audio", "voice.mp3")
            shutil.copy(src_audio, audio_path)
            log_action(user_id, "voiceover_generated", job_id=job_id)

            # ── Step 3 + 4: Footage + Assembly ──────────────────
            set_progress(job_id, user_id, 55, "Fetching footage and assembling video...")
            video_filename = f"{job_id}.mp4"
            assemble_video(script, audio_path, output_filename=video_filename)
            local_video_path = os.path.join(agent_config.OUTPUT_DIR, "videos", video_filename)
            log_action(user_id, "video_assembled", job_id=job_id)

            # ── Step 5: Upload to R2 ─────────────────────────────
            set_progress(job_id, user_id, 80, "Uploading preview to cloud...")
            video_key = f"videos/{user_id}/{job_id}.mp4"
            audio_key = f"audio/{user_id}/{job_id}.mp3"

            video_url = upload_file(local_video_path, video_key, "video/mp4")
            audio_url = upload_file(audio_path, audio_key, "audio/mpeg")

            # ── Save video record (update if this is a re-render) ─
            video_data = {
                "title": script.get("title"),
                "description": script.get("description"),
                "tags": script.get("tags", []),
                "video_url": video_url,
                "audio_url": audio_url,
                "youtube_url": None,
                "youtube_status": None,
            }
            existing = job.get("videos") or []
            if existing:
                from database import update_video
                update_video(existing[0]["id"], video_data)
            else:
                create_video(job_id, user_id, video_data)

            # ── Mark job as preview_ready ────────────────────────
            update_job(job_id, {
                "status": "preview_ready",
                "progress": 100,
                "current_step": "Preview ready — awaiting approval",
                "error_message": None,
            })
            log_action(user_id, "preview_ready", job_id=job_id,
                       message="Video ready for preview and approval")

    except Exception as e:
        _fail(self, job_id, user_id, e, "render_failed")


# ── Legacy one-shot pipeline (kept for auto_render / scheduled runs) ────────

@celery_app.task(bind=True, max_retries=1)
def generate_video_task(self, job_id: str, user_id: str, params: dict):
    params = dict(params, auto_render=True)
    generate_script_task.apply(args=(job_id, user_id, params))


@celery_app.task(bind=True, max_retries=2)
def upload_to_platforms_task(self, job_id: str, user_id: str, video_id: str,
                              platforms: list, user_youtube_token: str = None):
    """Upload approved video to YouTube and/or Instagram."""
    try:
        from database import get_job, update_video, get_supabase
        import storage

        update_job(job_id, {"status": "uploading", "current_step": "Uploading to platforms..."})

        job = get_job(job_id)
        script = job.get("script", {})
        videos = job.get("videos", [])
        if not videos:
            raise ValueError("No video found for this job")

        video = videos[0]
        video_url = video.get("video_url")

        # Download video from R2 for upload
        import tempfile, requests
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            r = requests.get(video_url, stream=True)
            for chunk in r.iter_content(1024 * 64):
                tmp.write(chunk)
            local_path = tmp.name

        update_data = {}

        if "youtube" in platforms and user_youtube_token:
            log_action(user_id, "youtube_upload_started", job_id=job_id)
            # YouTube upload using existing uploader
            from youtube_uploader import upload_video_with_token
            yt_url = upload_video_with_token(local_path, script, user_youtube_token,
                                             privacy=job.get("privacy", "private"))
            update_data.update({
                "youtube_url": yt_url,
                "youtube_status": job.get("privacy", "private"),
            })
            log_action(user_id, "youtube_uploaded", job_id=job_id,
                       message=yt_url, metadata={"url": yt_url})

        # Only update video record if there's something to update
        if update_data:
            update_video(video_id, update_data)

        update_job(job_id, {
            "status": "done",
            "current_step": "Uploaded successfully",
            "progress": 100,
        })
        log_action(user_id, "job_done", job_id=job_id, message="All uploads complete")

        os.unlink(local_path)

    except Exception as e:
        error_msg = str(e)
        update_job(job_id, {"status": "failed", "error_message": error_msg})
        log_action(user_id, "upload_failed", job_id=job_id, level="error", message=error_msg)
        raise self.retry(exc=e, countdown=15)
