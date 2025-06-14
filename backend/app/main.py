from fastapi import FastAPI
from app.api import endpoints

app = FastAPI(
    title="VideoThingy AI Service",
    description="Provides AI-powered video transcription and processing",
    version="1.0.0",
)

# Include the API router
app.include_router(endpoints.router, prefix="/api/v1", tags=["Transcription"])

@app.get("/")
async def root():
    return {"message": "Welcome to the VideoThingy AI Service!"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
