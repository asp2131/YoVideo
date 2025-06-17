# MVP Checklist

## Phase 1: Core Functionality (Months 1-2)

### 1. Video Upload & Management
- [x] **File Upload**: Support for MP4, MOV, AVI, WebM formats.
- [x] **File Size Limits**: Handle up to 2GB per video.
- [x] **Project Management**: Basic UI to list and manage video projects.
- [x] **Progress Tracking**: Display real-time status (e.g., "Uploading", "Transcribing", "Processing", "Complete").

### 2. Automatic Transcription
- [x] **Speech-to-Text**: Integrate Whisper for transcription.
- [x] **Timestamp Generation**: Ensure accurate timestamps for captions.
- [ ] **Multi-language Support**: Initial support for English.

### 3. Caption Generation & Editing
- [x] **Auto-Caption Creation**: Generate captions from the transcription.
- [ ] **Caption Editor**: Simple web-based editor to correct transcription text.
- [ ] **Styling Options**: Basic options for font, size, and color.
- [x] **Format Export**: Allow downloading captions as SRT files.

### 4. Video Processing & Editing
- [x] **Caption Overlay**: Burn captions onto the video.
- [ ] **Platform Optimization**:
    - [ ] YouTube (16:9)
    - [ ] Instagram (1:1, 9:16)
    - [ ] TikTok (9:16)
- [ ] **Basic Editing**: Implement video trimming.
- [x] **Output Quality**: Provide 720p and 1080p output options.

## Phase 2: User & System Foundation (Month 3)

### 5. User Management
- [ ] **Authentication**: User sign-up and login.
- [ ] **Project History**: Associate uploaded videos with user accounts.

### 6. Technical Infrastructure
- [x] **Database Schema**: Implement core tables (`users`, `projects`, `transcriptions`).
- [x] **File Storage**: Set up Supabase Storage for video uploads.
- [x] **Processing Service**: Create a basic Python service for transcription and video processing.
- [x] **Task Queue**: Integrate a task queue (Celery/Redis) for handling video jobs.
- [x] **API Gateway**: Set up a simple API gateway to handle requests from the frontend.

## Launch Criteria Checklist
- [ ] 95%+ transcription accuracy for clear English audio.
- [ ] <30 minutes average processing time for a 10-minute video.
- [ ] 99.5% system uptime.
- [ ] Complete user authentication and project management.
- [ ] Support for YouTube, Instagram, and TikTok formats.
- [ ] Download functionality for all supported formats.

## Progress Notes
- Backend infrastructure complete: FastAPI + Celery + Redis + Supabase
- Transcription workflow validated (API endpoint working)
- Missing: Video upload endpoint, caption overlay, frontend UI
- Missing: Authentication system integration
- Missing: Real video file testing

## Essential Backend APIs Ready for Frontend:
1. `POST /api/v1/upload` - Upload videos and create projects
2. `GET /api/v1/projects` - List all projects
3. `GET /api/v1/projects/{id}` - Get project details with transcription status
4. `POST /api/v1/transcribe` - Start transcription and caption overlay
5. `GET /api/v1/projects/{id}/download/srt` - Download SRT file
6. `GET /api/v1/projects/{id}/download/video?processed=true` - Download video with captions
7. `DELETE /api/v1/projects/{id}` - Delete project
