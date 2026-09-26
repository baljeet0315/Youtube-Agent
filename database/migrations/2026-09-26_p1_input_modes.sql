-- P1.1: idea/text input modes. Run once in Supabase SQL Editor.
alter table jobs add column if not exists input_mode text not null default 'idea';
alter table jobs add column if not exists source_text text;

-- Already applied manually earlier, kept here so schema history is complete:
alter table users alter column email drop not null;
