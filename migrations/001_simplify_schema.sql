-- Migration: Simplify schema for video transcription focus
-- Remove clip-related tables and add caption overlay fields to source_videos

-- Step 1: Add new columns to source_videos table
ALTER TABLE source_videos 
ADD COLUMN IF NOT EXISTS caption_file_url TEXT,
ADD COLUMN IF NOT EXISTS processed_video_url TEXT,
ADD COLUMN IF NOT EXISTS processing_status TEXT DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS processing_completed_at TIMESTAMP WITH TIME ZONE;

-- Step 2: Create a new simplified captions table for full video captions
CREATE TABLE IF NOT EXISTS video_captions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID NOT NULL REFERENCES source_videos(id) ON DELETE CASCADE,
    caption_format TEXT NOT NULL DEFAULT 'srt', -- srt, vtt, etc.
    caption_data JSONB NOT NULL, -- Full transcription with timestamps
    caption_file_url TEXT, -- URL to the generated caption file
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Step 3: Migrate existing caption data (if needed)
-- This will consolidate clip captions back to their source videos
INSERT INTO video_captions (video_id, caption_data, created_at, updated_at)
SELECT DISTINCT 
    c.source_video_id as video_id,
    jsonb_build_object(
        'segments', 
        jsonb_agg(
            jsonb_build_object(
                'start_time', cap.start_time,
                'end_time', cap.end_time,
                'text', cap.text,
                'speaker', cap.speaker
            ) ORDER BY cap.start_time
        )
    ) as caption_data,
    MIN(cap.created_at) as created_at,
    MAX(cap.updated_at) as updated_at
FROM clips c
JOIN captions cap ON cap.clip_id = c.id
GROUP BY c.source_video_id
ON CONFLICT DO NOTHING;

-- Step 4: Drop foreign key constraints
ALTER TABLE captions DROP CONSTRAINT IF EXISTS captions_clip_id_fkey;
ALTER TABLE clips DROP CONSTRAINT IF EXISTS clips_source_video_id_fkey;
ALTER TABLE clips DROP CONSTRAINT IF EXISTS clips_project_id_fkey;
ALTER TABLE clips DROP CONSTRAINT IF EXISTS clips_template_id_fkey;

-- Step 5: Drop the old tables
DROP TABLE IF EXISTS captions CASCADE;
DROP TABLE IF EXISTS clips CASCADE;
DROP TABLE IF EXISTS templates CASCADE;

-- Step 6: Update video_job_statuses to support new job types
ALTER TABLE video_job_statuses
ADD COLUMN IF NOT EXISTS video_id UUID REFERENCES source_videos(id);

-- Step 7: Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_video_captions_video_id ON video_captions(video_id);
CREATE INDEX IF NOT EXISTS idx_source_videos_processing_status ON source_videos(processing_status);
CREATE INDEX IF NOT EXISTS idx_source_videos_project_id ON source_videos(project_id);

-- Step 8: Add comments for documentation
COMMENT ON COLUMN source_videos.caption_file_url IS 'URL to the generated SRT/VTT caption file';
COMMENT ON COLUMN source_videos.processed_video_url IS 'URL to the video with embedded captions';
COMMENT ON COLUMN source_videos.processing_status IS 'Status of video processing: pending, transcribing, captioning, completed, failed';
COMMENT ON TABLE video_captions IS 'Stores full video transcription data and caption files';
