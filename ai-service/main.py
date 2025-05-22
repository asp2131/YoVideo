from fastapi import FastAPI, File, UploadFile, HTTPException
import whisper
import os
import shutil
import tempfile
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="VideoThingy AI Service",
    description="Provides AI-powered functionalities like transcription, highlight detection, etc.",
    version="0.1.0",
)

@app.get("/")
async def root():
    return {"message": "Welcome to the VideoThingy AI Service!"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Load the Whisper model globally to avoid reloading it on every request.
# This can take a few seconds (or more for larger models) the first time it's run
# as it might download the model weights.
# Using "base" model as a starting point. Other options: "tiny", "small", "medium", "large"
try:
    logger.info("Loading Whisper model...")
    whisper_model = whisper.load_model("base")
    logger.info("Whisper model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load Whisper model: {e}")
    whisper_model = None # Set to None if loading fails

@app.post("/transcribe")
async def transcribe_audio(audio_file: UploadFile = File(...)):
    if whisper_model is None:
        raise HTTPException(status_code=500, detail="Whisper model is not available.")

    if not audio_file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    logger.info(f"Received file: {audio_file.filename}, content type: {audio_file.content_type}")

    # Create a temporary file to store the uploaded audio
    # Whisper needs a file path to process.
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio_file.filename)[1]) as tmp_audio_file:
            shutil.copyfileobj(audio_file.file, tmp_audio_file)
            tmp_audio_file_path = tmp_audio_file.name
        logger.info(f"Temporary audio file saved at: {tmp_audio_file_path}")

        # Transcribe the audio file
        logger.info(f"Starting transcription for {tmp_audio_file_path}...")
        result = whisper_model.transcribe(tmp_audio_file_path, fp16=False) # fp16=False for CPU, set to True if on GPU and supported
        transcription_text = result["text"]
        logger.info(f"Transcription successful.")

    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        raise HTTPException(status_code=500, detail=f"Error during transcription: {str(e)}")
    finally:
        # Clean up the temporary file
        if 'tmp_audio_file_path' in locals() and os.path.exists(tmp_audio_file_path):
            os.remove(tmp_audio_file_path)
            logger.info(f"Temporary audio file {tmp_audio_file_path} deleted.")
        # Ensure the uploaded file's resources are closed
        await audio_file.close()

    return {"filename": audio_file.filename, "transcription": transcription_text}

if __name__ == "__main__":
    import uvicorn
    # This is for direct execution (e.g., python main.py),
    # but uvicorn command is preferred for development/production.
    uvicorn.run(app, host="0.0.0.0", port=8001)
