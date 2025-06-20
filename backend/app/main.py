from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import endpoints

app = FastAPI(
    title="VideoThingy AI Service",
    description="Provides AI-powered video transcription and processing",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the API router
app.include_router(endpoints.router, prefix="/api/v1", tags=["Transcription"])

@app.get("/")
async def root():
    return {"message": "Welcome to the VideoThingy AI Service!"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
