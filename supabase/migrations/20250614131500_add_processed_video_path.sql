-- Add processed_video_path column to projects table
-- This will store the path to the video with captions burned in

ALTER TABLE projects ADD COLUMN processed_video_path TEXT;

-- Add comment to document the column
COMMENT ON COLUMN projects.processed_video_path IS 'Path to the processed video file with captions overlaid';
