# Video Transcription Backend

A FastAPI-based backend service for video transcription and caption overlay. This service handles video uploads, transcription using Whisper, and caption overlay using FFmpeg.

## Prerequisites

- Python 3.8+
- FFmpeg
- Redis (for Celery task queue)
- Supabase account (for storage and database)

## Setup

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone <repository-url>
   cd videothingy/backend
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Create a `.env` file in the backend directory with the following variables:
   ```
   # Supabase
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   
   # Redis (for Celery)
   REDIS_URL=redis://localhost:6379/0
   
   # App settings
   ENVIRONMENT=development
   DEBUG=True
   ```

## Running the Application

### Development Mode

1. **Start Redis**:
   Make sure Redis is running locally:
   ```bash
   redis-server
   ```

2. **Start the FastAPI server** (in one terminal):
   ```bash
   uvicorn app.main:app --reload
   ```

3. **Start the Celery worker** (in a second terminal):
   ```bash
   celery -A app.worker.celery_app worker --loglevel=info
   ```

4. **Access the API documentation**:
   Open your browser to: http://127.0.0.1:8000/docs

### Production Mode

For production, use a process manager like Gunicorn with Uvicorn workers:

```bash
gunicorn -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000 app.main:app
```

## API Endpoints

- `POST /api/v1/upload` - Upload a video file
- `GET /api/v1/projects` - List all projects
- `GET /api/v1/projects/{id}` - Get project details
- `POST /api/v1/transcribe` - Start transcription
- `GET /api/v1/projects/{id}/download/srt` - Download SRT file
- `GET /api/v1/projects/{id}/download/video?processed=true` - Download video with captions
- `DELETE /api/v1/projects/{id}` - Delete a project

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `SUPABASE_URL` | Your Supabase project URL | Yes | - |
| `SUPABASE_KEY` | Your Supabase anon/public key | Yes | - |
| `REDIS_URL` | Redis connection URL | No | `redis://localhost:6379/0` |
| `ENVIRONMENT` | Runtime environment | No | `development` |
| `DEBUG` | Enable debug mode | No | `False` |

## Directory Structure

```
backend/
├── app/
│   ├── api/              # API routes
│   ├── core/             # Core configurations
│   ├── db/               # Database models and session
│   ├── services/         # Business logic
│   ├── tasks/            # Celery tasks
│   ├── worker/           # Celery app configuration
│   └── main.py           # FastAPI app entry point
├── tests/                # Test files
├── .env.example         # Example environment variables
└── requirements.txt     # Python dependencies
```

## Testing

To run tests:

```bash
pytest
```

## License

[Your License Here]
