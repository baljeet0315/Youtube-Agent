-- P1.3 / P1.4: script review gate + feedback loop. Run once in Supabase SQL Editor.
-- New job statuses: scripting, script_ready, rendering (status column is free text; no enum change).
alter table jobs add column if not exists auto_render        boolean not null default false;
alter table jobs add column if not exists feedback_history   jsonb   not null default '[]'::jsonb;
alter table jobs add column if not exists regeneration_count int     not null default 0;
