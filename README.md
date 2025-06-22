# VideoThingy - Video Transcription & Captioning Tool

VideoThingy is a streamlined video processing platform that provides automatic transcription and caption overlay functionality. It's designed to handle large video files (up to 1GB) with a focus on simplicity and reliability.

## Key Features

- **Video Upload**: Supports large file uploads with chunked transfer
- **Automatic Transcription**: Powered by Whisper AI for accurate speech-to-text
- **Caption Overlay**: Burn subtitles directly onto videos using FFmpeg
- **Project Management**: Track and manage your video projects
- **Responsive Web Interface**: Modern UI built with Next.js and Tailwind CSS

## Architecture

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    Frontend     │◄─────►│    Backend      │◄─────►│   Cloudflare R2  │
│   (Next.js)     │       │   (FastAPI)     │       │   (Object Storage)│
└─────────────────┘       └────────┬────────┘       └─────────────────┘
                                   │
                            ┌──────┴──────┐
                            ▼               ▼
                    ┌─────────────┐  ┌─────────────┐
                    │  Supabase   │  │  FFmpeg     │
                    │ (PostgreSQL)│  │ (Processing) │
                    └─────────────┘  └─────────────┘
```

## Getting Started

### Prerequisites

- Node.js (v18 or later)
- Python (v3.10 or later)
- FFmpeg
- Cloudflare R2 credentials
- Supabase project

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your credentials:
   ```bash
   # Supabase
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_anon_key
   
   # Cloudflare R2
   CLOUDFLARE_ACCOUNT_ID=your_account_id
   R2_ACCESS_KEY_ID=your_access_key
   R2_SECRET_ACCESS_KEY=your_secret_key
   R2_BUCKET_NAME=your_bucket_name
   
   # App Settings
   UPLOAD_TEMP_DIR=./temp_uploads
   MAX_UPLOAD_SIZE=1073741824  # 1GB
   ```

5. Start the FastAPI server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Create a `.env.local` file with your backend URL:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

4. Start the development server:
   ```bash
   npm run dev
   ```

5. Open [http://localhost:3000](http://localhost:3000) in your browser.

## API Endpoints

- `POST /api/v1/upload` - Upload a new video
- `GET /api/v1/projects` - List all projects
- `GET /api/v1/projects/{id}` - Get project details
- `POST /api/v1/transcribe` - Start transcription
- `GET /api/v1/projects/{id}/download/srt` - Download SRT file
- `GET /api/v1/projects/{id}/download/video?processed=true` - Download video with captions
- `DELETE /api/v1/projects/{id}` - Delete a project

## Development Guidelines

- Follow PEP 8 and Google Python Style Guide
- Keep functions focused and under 50 lines
- Write clear docstrings for all public functions
- Include type hints for better code clarity
- Write tests for new features
- Update documentation when making changes

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

- Prefix with semantic tag: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`
- Limit body to 72 chars/line
- Reference task ID from task.md (e.g., `Relates to F-5`)
- Include progress updates (e.g., `Updates F-5 to 🟡`)

## License

This project is proprietary and confidential.
