-- Create storage buckets

-- 1. Videos bucket (private)
-- For raw video uploads from users.
-- - Private access
-- - 2GB file size limit
-- - Allowed types: MP4, MOV, AVI, WebM
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('videos', 'videos', false, 2147483648, ARRAY['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm']);

-- 2. Exports bucket (public)
-- For processed videos ready for download.
-- - Public access for easy download via CDN
INSERT INTO storage.buckets (id, name, public)
VALUES ('exports', 'exports', true);

-- RLS Policies for Storage

-- Policy: Authenticated users can upload to the 'videos' bucket
CREATE POLICY "Allow authenticated uploads to videos bucket"
ON storage.objects FOR INSERT TO authenticated
WITH CHECK (bucket_id = 'videos');

-- Policy: Users can view their own files in the 'videos' bucket
CREATE POLICY "Allow individual user access to their own videos"
ON storage.objects FOR SELECT TO authenticated
USING (bucket_id = 'videos' AND owner_id = auth.uid()::text);

-- Policy: Users can delete their own files in the 'videos' bucket
CREATE POLICY "Allow individual user to delete their own videos"
ON storage.objects FOR DELETE TO authenticated
USING (bucket_id = 'videos' AND owner_id = auth.uid()::text);

-- Note: The 'exports' bucket is public, so SELECT access is granted by default.
-- We don't need insert/update/delete policies for users on the 'exports' bucket
-- as files will be placed there by the backend service.
