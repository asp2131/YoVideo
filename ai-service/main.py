from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
import whisper
import os
import shutil
import tempfile
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Pydantic Models for Transcription ---
class TranscriptSegment(BaseModel):
    text: str
    start_time: float
    end_time: float

class TranscriptionResponse(BaseModel):
    filename: str
    segments: list[TranscriptSegment]

# --- Pydantic Models for Caption Formatting ---
class CaptionFormatRequest(BaseModel):
    segments: list[TranscriptSegment]
    max_chars_per_line: int = 40
    max_lines_per_caption: int = 2

class CaptionFormatResponse(BaseModel):
    srt_content: str

app = FastAPI(
    title="VideoThingy AI Service",
    description="Provides AI-powered video transcription and caption formatting",
    version="0.2.0",
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

@app.post("/transcribe", response_model=TranscriptionResponse)
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
        logger.info(f"Transcription successful. Processing segments...")

        processed_segments = []
        for seg in result.get("segments", []):
            processed_segments.append(
                TranscriptSegment(text=seg.get("text", ""), 
                                  start_time=seg.get("start", 0.0),
                                  end_time=seg.get("end", 0.0))
            )
        logger.info(f"Processed {len(processed_segments)} segments.")

    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        raise HTTPException(status_code=500, detail=f"Error during transcription: {str(e)}")
    finally:
        # Clean up the temporary file
        if 'tmp_audio_file_path' in locals() and os.path.exists(tmp_audio_file_path):
            os.remove(tmp_audio_file_path)
            logger.info(f"Temporary audio file {tmp_audio_file_path} deleted.")

    return TranscriptionResponse(
        filename=audio_file.filename,
        segments=processed_segments
    )

# --- Caption Formatting Functions ---
def format_srt_time(seconds: float) -> str:
    """Converts seconds to SRT time format HH:MM:SS,mmm."""
    millis = int(round(seconds * 1000))
    ss, millis = divmod(millis, 1000)
    mm, ss = divmod(ss, 60)
    hh, mm = divmod(mm, 60)
    return f"{hh:02d}:{mm:02d}:{ss:02d},{millis:03d}"

def break_text_into_lines(text: str, max_chars: int, max_lines: int) -> list[str]:
    """Breaks text into lines with max_chars and max_lines constraints."""
    words = text.strip().split()
    lines = []
    current_line = ""
    if not words:
        return []

    for word in words:
        if not current_line:
            current_line = word
        elif len(current_line) + 1 + len(word) <= max_chars:
            current_line += " " + word
        else:
            if len(lines) < max_lines -1: # -1 because we are about to add current_line
                lines.append(current_line)
                current_line = word
            else: # Max lines reached, append rest to current_line (it might get long)
                current_line += " " + word # Or decide to truncate/discard
    
    if current_line: # Add the last line being built
        lines.append(current_line)
    
    return lines[:max_lines] # Ensure we don't exceed max_lines due to final append

@app.post("/format-captions", response_model=CaptionFormatResponse)
async def format_captions_endpoint(request: CaptionFormatRequest):
    """Format transcript segments into SRT format for video captions."""
    srt_blocks = []
    for i, segment in enumerate(request.segments):
        start_srt_time = format_srt_time(segment.start_time)
        end_srt_time = format_srt_time(segment.end_time)
        
        caption_lines = break_text_into_lines(
            segment.text,
            request.max_chars_per_line,
            request.max_lines_per_caption
        )
        
        if not caption_lines: # Skip empty segments if any
            continue
            
        srt_block = f"{i+1}\n"
        srt_block += f"{start_srt_time} --> {end_srt_time}\n"
        srt_block += "\n".join(caption_lines)
        srt_block += "\n\n" # Two newlines to separate blocks
        srt_blocks.append(srt_block)
        
    return CaptionFormatResponse(srt_content="".join(srt_blocks).strip())


if __name__ == "__main__":
    import uvicorn
    # This is for direct execution (e.g., python main.py),
    # but uvicorn command is preferred for development/production.
    uvicorn.run(app, host="0.0.0.0", port=8001)
