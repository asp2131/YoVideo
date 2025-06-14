-- Temporary policy to allow backend service to read projects for transcription
-- This allows the anon role to read projects, which enables our transcription task to work
-- In production, we would use the service_role key instead

CREATE POLICY "Allow backend service to read projects for transcription" 
ON projects FOR SELECT
TO anon
USING (true);

-- Also allow backend service to read and write to processing_jobs
CREATE POLICY "Allow backend service to manage processing jobs" 
ON processing_jobs FOR ALL
TO anon
USING (true);

-- Allow backend service to write transcriptions
CREATE POLICY "Allow backend service to write transcriptions" 
ON transcriptions FOR INSERT
TO anon
WITH CHECK (true);
