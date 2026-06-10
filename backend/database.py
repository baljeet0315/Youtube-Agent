"""
database.py — Supabase client and helper functions
"""
from supabase import create_client, Client
from config import get_settings

settings = get_settings()


def get_supabase() -> Client:
    """Get Supabase client with service role key (bypasses RLS)."""
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )


# ── Users ──────────────────────────────────────────────────────

def get_or_create_user(clerk_id: str, email: str, name: str = None, avatar_url: str = None) -> dict:
    """Get existing user or create new one from Clerk auth data."""
    sb = get_supabase()

    result = sb.table("users").select("*").eq("clerk_id", clerk_id).execute()

    if result.data:
        return result.data[0]

    new_user = sb.table("users").insert({
        "clerk_id": clerk_id,
        "email": email,
        "name": name,
        "avatar_url": avatar_url,
    }).execute()

    log_action(new_user.data[0]["id"], "user_created", message=f"New user: {email}")
    return new_user.data[0]


def get_user_by_clerk_id(clerk_id: str) -> dict | None:
    sb = get_supabase()
    result = sb.table("users").select("*").eq("clerk_id", clerk_id).execute()
    return result.data[0] if result.data else None


def update_user(user_id: str, data: dict) -> dict:
    sb = get_supabase()
    result = sb.table("users").update(data).eq("id", user_id).execute()
    return result.data[0]


# ── Jobs ───────────────────────────────────────────────────────

def create_job(user_id: str, params: dict) -> dict:
    sb = get_supabase()
    job = sb.table("jobs").insert({
        "user_id": user_id,
        **params,
    }).execute()
    log_action(user_id, "job_created", job_id=job.data[0]["id"],
               message=f"Job created: {params.get('topic', '')[:50]}")
    return job.data[0]


def get_job(job_id: str) -> dict | None:
    sb = get_supabase()
    result = sb.table("jobs").select("*, videos(*)").eq("id", job_id).execute()
    return result.data[0] if result.data else None


def get_user_jobs(user_id: str, limit: int = 20) -> list:
    sb = get_supabase()
    result = (sb.table("jobs")
              .select("*, videos(*)")
              .eq("user_id", user_id)
              .order("created_at", desc=True)
              .limit(limit)
              .execute())
    return result.data


def update_job(job_id: str, data: dict) -> dict:
    sb = get_supabase()
    result = sb.table("jobs").update(data).eq("id", job_id).execute()
    return result.data[0]


# ── Videos ─────────────────────────────────────────────────────

def create_video(job_id: str, user_id: str, data: dict) -> dict:
    sb = get_supabase()
    video = sb.table("videos").insert({
        "job_id": job_id,
        "user_id": user_id,
        **data,
    }).execute()
    return video.data[0]


def update_video(video_id: str, data: dict) -> dict:
    sb = get_supabase()
    result = sb.table("videos").update(data).eq("id", video_id).execute()
    return result.data[0]


# ── Logs ───────────────────────────────────────────────────────

def log_action(user_id: str, action: str, job_id: str = None,
               level: str = "info", message: str = None, metadata: dict = None):
    """Write an activity log entry."""
    try:
        sb = get_supabase()
        sb.table("logs").insert({
            "user_id": user_id,
            "job_id": job_id,
            "action": action,
            "level": level,
            "message": message,
            "metadata": metadata or {},
        }).execute()
    except Exception as e:
        print(f"⚠️  Log write failed: {e}")


def get_user_logs(user_id: str, limit: int = 50) -> list:
    sb = get_supabase()
    result = (sb.table("logs")
              .select("*")
              .eq("user_id", user_id)
              .order("created_at", desc=True)
              .limit(limit)
              .execute())
    return result.data
