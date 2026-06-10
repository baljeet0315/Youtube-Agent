-- ============================================================
-- YouTube Shorts Agent — Database Schema
-- Run this in Supabase SQL Editor
-- ============================================================

-- Enable UUID generation
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";


-- ── USERS ────────────────────────────────────────────────────
-- Stores each user's profile and encrypted platform credentials
create table if not exists users (
  id              uuid primary key default uuid_generate_v4(),
  clerk_id        text unique not null,        -- Clerk auth user ID
  email           text unique not null,
  name            text,
  avatar_url      text,

  -- YouTube credentials (encrypted)
  youtube_token   text,                        -- encrypted OAuth token JSON
  youtube_channel_id    text,
  youtube_channel_name  text,

  -- Instagram credentials (encrypted)
  instagram_token       text,                  -- encrypted access token
  instagram_account_id  text,
  instagram_username    text,

  -- Default preferences
  default_voice_id      text default 'pNInz6obpgDQGcFmaJgB',
  default_style         text default 'educational',
  default_duration      int  default 45,

  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);


-- ── JOBS ─────────────────────────────────────────────────────
-- Each video generation request submitted by a user
create table if not exists jobs (
  id              uuid primary key default uuid_generate_v4(),
  user_id         uuid references users(id) on delete cascade,

  -- Input parameters
  topic           text not null,
  style           text not null default 'educational',
  narration_style text,                        -- e.g. "David Attenborough", "energetic"
  voice_id        text,                        -- ElevenLabs voice ID
  duration        int  not null default 45,
  platform        text[] default array['youtube'],  -- ['youtube', 'instagram']
  privacy         text default 'private',

  -- Status tracking
  status          text not null default 'pending',
  -- pending → processing → preview_ready → approved → uploading → done → failed
  progress        int  default 0,              -- 0-100
  error_message   text,
  current_step    text,                        -- e.g. "Generating script..."

  -- Generated content
  script          jsonb,                       -- full script JSON from Claude

  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);


-- ── VIDEOS ───────────────────────────────────────────────────
-- Finished videos with storage URLs and upload status
create table if not exists videos (
  id              uuid primary key default uuid_generate_v4(),
  job_id          uuid references jobs(id) on delete cascade,
  user_id         uuid references users(id) on delete cascade,

  -- Generated metadata
  title           text,
  description     text,
  tags            text[],

  -- Storage (Cloudflare R2)
  audio_url       text,                        -- voiceover MP3
  video_url       text,                        -- final MP4 (preview)
  thumbnail_url   text,

  -- YouTube upload
  youtube_video_id    text,
  youtube_url         text,
  youtube_status      text,                    -- private, unlisted, public
  youtube_uploaded_at timestamptz,

  -- Instagram upload
  instagram_media_id  text,
  instagram_url       text,
  instagram_uploaded_at timestamptz,

  -- File metadata
  duration_seconds    int,
  file_size_bytes     bigint,

  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);


-- ── LOGS ─────────────────────────────────────────────────────
-- Activity trail — every action per user, timestamped
create table if not exists logs (
  id              uuid primary key default uuid_generate_v4(),
  user_id         uuid references users(id) on delete cascade,
  job_id          uuid references jobs(id) on delete set null,

  action          text not null,
  -- Examples:
  -- 'job_created', 'script_generated', 'voiceover_generated',
  -- 'video_assembled', 'preview_ready', 'upload_approved',
  -- 'youtube_uploaded', 'instagram_uploaded', 'job_failed'

  level           text default 'info',         -- info, warning, error
  message         text,
  metadata        jsonb,                       -- any extra data (file sizes, durations, etc.)

  created_at      timestamptz default now()
);


-- ── INDEXES ──────────────────────────────────────────────────
create index if not exists jobs_user_id_idx    on jobs(user_id);
create index if not exists jobs_status_idx     on jobs(status);
create index if not exists videos_user_id_idx  on videos(user_id);
create index if not exists videos_job_id_idx   on videos(job_id);
create index if not exists logs_user_id_idx    on logs(user_id);
create index if not exists logs_job_id_idx     on logs(job_id);
create index if not exists logs_created_at_idx on logs(created_at desc);


-- ── AUTO-UPDATE updated_at ───────────────────────────────────
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger users_updated_at before update on users
  for each row execute function update_updated_at();

create trigger jobs_updated_at before update on jobs
  for each row execute function update_updated_at();

create trigger videos_updated_at before update on videos
  for each row execute function update_updated_at();


-- ── ROW LEVEL SECURITY ───────────────────────────────────────
-- Users can only see their own data
alter table users  enable row level security;
alter table jobs   enable row level security;
alter table videos enable row level security;
alter table logs   enable row level security;

-- Policies are applied via the backend using service role key
-- (bypasses RLS for server-side operations)
