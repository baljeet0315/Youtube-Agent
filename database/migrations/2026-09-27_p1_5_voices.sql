-- P1.5: per-job TTS model + voice tuning. Run once in Supabase SQL Editor.
alter table jobs add column if not exists tts_model      text;
alter table jobs add column if not exists voice_settings jsonb;
