-- Initial Schema for VideoThingy

-- Create projects table
CREATE TABLE projects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES auth.users(id) NOT NULL,
    name TEXT NOT NULL,
    video_path TEXT,
    status TEXT NOT NULL DEFAULT 'uploaded',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create transcriptions table
CREATE TABLE transcriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE NOT NULL,
    transcription_data JSONB,
    srt_content TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create processing_jobs table
CREATE TABLE processing_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE NOT NULL,
    job_type TEXT NOT NULL, -- e.g., 'transcription', 'video_processing'
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create export_formats table
CREATE TABLE export_formats (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE NOT NULL,
    platform TEXT NOT NULL, -- e.g., 'youtube', 'instagram_square', 'tiktok'
    resolution TEXT NOT NULL,
    aspect_ratio TEXT NOT NULL,
    output_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enable Row Level Security (RLS) for all tables
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE export_formats ENABLE ROW LEVEL SECURITY;

-- RLS Policies for projects
CREATE POLICY "Users can only see their own projects." 
ON projects FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own projects." 
ON projects FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own projects." 
ON projects FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own projects." 
ON projects FOR DELETE
USING (auth.uid() = user_id);

-- RLS Policies for related tables (transcriptions, jobs, exports)
CREATE POLICY "Users can manage items related to their own projects." 
ON transcriptions FOR ALL
USING (auth.uid() = (SELECT user_id FROM projects WHERE id = project_id));

CREATE POLICY "Users can manage items related to their own projects." 
ON processing_jobs FOR ALL
USING (auth.uid() = (SELECT user_id FROM projects WHERE id = project_id));

CREATE POLICY "Users can manage items related to their own projects." 
ON export_formats FOR ALL
USING (auth.uid() = (SELECT user_id FROM projects WHERE id = project_id));
