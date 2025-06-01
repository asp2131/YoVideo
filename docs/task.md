# 📹 Video Transcription & Caption Overlay System - Refactoring Plan

## 🎯 New Project Direction
Pivot from clip creation to a focused video transcription and caption overlay system that can handle large video files (1GB+).

### Core Features
1. **Video Upload** - Support for large files (up to 1GB)
2. **Automatic Transcription** - Using Whisper AI
3. **Caption Overlay** - Embed captions directly into uploaded videos
4. **Download** - Get the video with embedded captions

---

## 🔍 Current System Analysis

### Existing Components
1. **Frontend (Next.js)**
   - ✅ Video upload interface
   - ✅ Project management
   - ❌ Clip editor (to be removed)
   - ❌ B-roll features (to be removed)
   - ✅ Video player with transcription display

2. **API Gateway (Go)**
   - ✅ Video upload endpoints
   - ✅ Transcription trigger
   - ✅ Project management
   - ❌ Clip generation endpoints (to be removed)
   - ❌ Caption CRUD (to be simplified)

3. **Video Processor (Go)**
   - ✅ FFmpeg wrapper
   - ✅ Caption overlay functionality
   - ❌ Clip extraction (to be removed)
   - ✅ Video metadata extraction

4. **AI Service (Python)**
   - ✅ Whisper transcription
   - ✅ Highlight detection (REMOVED)
   - ✅ gRPC communication

5. **Database (Supabase)**
   - Tables: projects, videos, clips, captions, video_job_statuses
   - Need to simplify schema

---

## 📋 Refactoring Tasks

### Phase 1: Database Schema Simplification
| Task | Status | Description |
|------|--------|-------------|
| Remove clips table | 🔵 | No longer needed |
| Simplify captions table | 🔵 | Only store full video captions |
| Update videos table | 🔵 | Add caption_file_url, processed_video_url fields |
| Create migration script | 🔵 | Migrate existing data if needed |

### Phase 2: Backend Refactoring
| Task | Status | Description |
|------|--------|-------------|
| Remove clip-related endpoints | 🔵 | Clean up API Gateway |
| Update video upload handler | 🔵 | Support 1GB file uploads |
| Simplify transcription workflow | 🔵 | Direct video → transcription → overlay |
| Remove highlight detection | ✅ | From AI service |
| Update job processing | 🔵 | Single job type: transcribe & overlay |
| Add progress tracking | 🔵 | For large file processing |

### Phase 3: Frontend Simplification
| Task | Status | Description |
|------|--------|-------------|
| Remove clip editor UI | 🔵 | Not needed anymore |
| Remove B-roll components | 🔵 | Not needed |
| Remove template selector | 🔵 | Not needed |
| Update video page | 🔵 | Show transcription & download |
| Add upload progress | 🔵 | For large files |
| Simplify navigation | 🔵 | Remove unused sections |

### Phase 4: Processing Pipeline
| Task | Status | Description |
|------|--------|-------------|
| Implement chunked upload | 🔵 | For 1GB files |
| Add video queue system | 🔵 | Handle multiple uploads |
| Optimize FFmpeg settings | 🔵 | For large file processing |
| Add SRT generation | 🔵 | From transcription data |
| Implement caption styling | 🔵 | Basic subtitle styling |

### Phase 5: Testing & Optimization
| Task | Status | Description |
|------|--------|-------------|
| Test with 1GB files | 🔵 | Ensure system handles large files |
| Add error recovery | 🔵 | Resume failed uploads |
| Optimize memory usage | 🔵 | For video processing |
| Add processing timeouts | 🔵 | Prevent stuck jobs |
| Performance monitoring | 🔵 | Track processing times |

---

## 🏗️ New Architecture

```
┌─────────────────┐       ┌─────────────────┐
│    Frontend     │◄─────►│   API Gateway   │
│   (Next.js)     │       │      (Go)       │
└─────────────────┘       └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │ Video Processor │
                          │      (Go)       │
                          └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │   AI Service    │
                          │   (Python)      │
                          └────────┬────────┘
                                   │
                          ┌────────▼────────┐
                          │    Supabase     │
                          │  (Storage/DB)   │
                          └─────────────────┘
```

## 📊 Simplified Data Flow

1. **Upload**: User uploads video (up to 1GB)
2. **Store**: Video stored in Supabase Storage
3. **Transcribe**: AI Service processes with Whisper
4. **Generate**: Create SRT file from transcription
5. **Overlay**: FFmpeg adds captions to video
6. **Complete**: User downloads captioned video

---

## 🗑️ Components to Remove

### Frontend
- [x] `/components/ui/ClipEditor.tsx` (Renamed to .deprecated.tsx)
- [x] `/components/ui/BRollSelector.tsx` (Renamed to .deprecated.tsx)
- [x] `/components/ui/TemplateSelector.tsx` (Renamed to .deprecated.tsx)
- [x] `/components/ui/AspectRatioPreview.tsx` (Renamed to .deprecated.tsx)
- [~] Clip-related pages and routes (Removed /templates link, API functions for highlights. Further cleanup might be needed within existing project pages)

### Backend
- [~] Clip management endpoints (Partially removed: routes commented, job submission removed)
- [✅] Highlight detection logic
- [ ] B-roll processing
- [ ] Template application
- [ ] Complex caption CRUD

### Database
- `clips` table
- `templates` table (if exists)
- Complex relationships

---

## 🚀 Implementation Priority

1. **Week 1**: Database schema migration & backend cleanup
2. **Week 2**: Update processing pipeline for large files
3. **Week 3**: Frontend simplification & UI updates
4. **Week 4**: Testing, optimization & deployment

---

## 📈 Success Metrics

- Support 1GB video uploads
- Process video in < 10 minutes
- 95% transcription accuracy
- Clean, embedded captions
- Simple user workflow

---

## 🔧 Technical Considerations

### Large File Handling
- Implement multipart upload
- Use streaming for video processing
- Add progress indicators
- Handle network interruptions

### Performance
- Queue system for concurrent processing
- Optimize FFmpeg commands
- Cache transcription results
- CDN for processed videos

### Error Handling
- Graceful failure recovery
- Clear error messages
- Retry mechanisms
- Job status tracking

---

> Last Updated: 2025-05-31
> Status: Planning Phase