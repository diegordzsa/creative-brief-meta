-- Run this in Supabase SQL Editor (Dashboard > SQL Editor > New query)

-- 1. Create the sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    username        TEXT NOT NULL,
    source_name     TEXT NOT NULL,
    video_url       TEXT NOT NULL DEFAULT '',
    formato_detectado TEXT NOT NULL DEFAULT '',
    header_data     JSONB NOT NULL DEFAULT '{}',
    briefs_json     JSONB NOT NULL DEFAULT '[]',
    pdf_storage_path TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sessions_username_created
    ON sessions (username, created_at DESC);

-- 2. Create the "pdfs" storage bucket (private)
-- Go to Supabase Dashboard > Storage > Create a new bucket
--   Name: pdfs
--   Public: OFF (private)
--
-- Or run this via SQL (requires storage schema access):
INSERT INTO storage.buckets (id, name, public)
VALUES ('pdfs', 'pdfs', false)
ON CONFLICT (id) DO NOTHING;
