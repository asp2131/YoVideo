# OpusClip - AI-Powered Video Editor

OpusClip is an advanced video editing platform that leverages AI to help users create engaging video clips with ease. This project is structured as a modern microservices application with the following components:

1. **Frontend** (Next.js with Tailwind CSS)
2. **API Gateway** (Go with Fiber)
3. **Video Processor** (Go)
4. **AI Service** (Python with FastAPI)

## Project Structure

```
videothingy/
├── frontend/             # Next.js frontend application
├── api-gateway/          # Go API Gateway service
├── video-processor/      # Go Video Processing service
├── ai-service/           # Python AI service
└── docs/                 # Project documentation
```

## Frontend Features

The frontend application is built with Next.js and Tailwind CSS, providing a responsive and modern user interface for:

- Project management (create, list, delete)
- Video upload with drag-and-drop
- Video player with transcription display
- Clip editor with timeline
- Template selection and preview
- Captions editor with timestamps
- B-roll insertion
- Clip preview with aspect ratio selection
- Download interface for finished clips

## Getting Started

### Prerequisites

- Node.js (v18 or later)
- Go (v1.20 or later)
- Python (v3.10 or later)
- FFmpeg

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Open [http://localhost:3000](http://localhost:3000) in your browser.

## Development Guidelines

This project follows the KISS (Keep It Stupid Simple) and YAGNI (You Aren't Gonna Need It) principles:

- Favor clarity over cleverness
- Build only what's required in the current tasks
- Keep functions under 40 lines
- Maintain cyclomatic complexity ≤ 10
- Follow the Boy-Scout Rule: leave code cleaner than you found it

## Architecture

The application follows a microservices architecture:

```
┌─────────────────┐       ┌─────────────────┐
│    Frontend     │◄─────►│   API Gateway   │
│    (Next.js)    │       │      (Go)       │
└─────────────────┘       └────────┬────────┘
                                   │
                                   ▼
         ┌─────────────────────────────────────────┐
         │                                         │
┌────────▼─────────┐  ┌─────────────┐  ┌──────────▼────────┐
│  Video Processor │  │  AI Service │  │  Storage Manager  │
│       (Go)       │◄─►│  (Python)  │  │        (Go)       │
└──────────────────┘  └─────────────┘  └─────────────────────┘
         │                                         │
         ▼                                         ▼
┌─────────────────┐                     ┌─────────────────────┐
│    FFmpeg &     │                     │    Supabase         │
│ Media Libraries │                     │    (PostgreSQL/S3)  │
└─────────────────┘                     └─────────────────────┘
```

## Contributing

Please follow the commit etiquette defined in our documentation:

- Prefix with semantic tag: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`
- Limit body to 72 chars/line
- Reference task ID from task.md (e.g., `Relates to F-5`)
- Include progress updates (e.g., `Updates F-5 to 🟡`)

## License

This project is proprietary and confidential.
