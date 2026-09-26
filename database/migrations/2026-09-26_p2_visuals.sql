-- Phase 2: per-job visual mode + user default. Run once in Supabase SQL Editor.
alter table jobs  add column if not exists visual_mode         text not null default 'ai_images'; -- 'ai_images' | 'stock'
alter table users add column if not exists default_visual_mode text;
