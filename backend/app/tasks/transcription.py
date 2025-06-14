import os
import tempfile
import logging
import whisper
from app.core.celery_app import celery_app
from app.services.supabase_client import supabase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Whisper model once when the worker starts
try:
    logger.info("Loading Whisper model...")
    whisper_model = whisper.load_model("base")
    logger.info("Whisper model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load Whisper model: {e}")
    whisper_model = None

@celery_app.task(bind=True)
def transcribe_video_task(self, project_id: str):
    if whisper_model is None:
        logger.error("Whisper model is not available. Aborting task.")
        # Update job status to 'failed'
        supabase.table("processing_jobs").update({
            "status": "failed",
            "error_message": "Whisper model not loaded"
        }).eq("project_id", project_id).execute()
        return

    logger.info(f"Starting transcription for project_id: {project_id}")

    try:
        # 1. Get video path from the projects table
        project_response = supabase.table("projects").select("video_path").eq("id", project_id).execute()
        
        if not project_response.data or len(project_response.data) == 0:
            raise ValueError(f"No project found with id {project_id}")
            
        video_path = project_response.data[0].get("video_path")

        if not video_path:
            raise ValueError(f"No video_path found for project {project_id}")

        # 2. Download video from Supabase Storage
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(video_path)[1]) as tmp_video_file:
            logger.info(f"Downloading {video_path} from Supabase Storage...")
            video_data = supabase.storage.from_("videos").download(video_path)
            tmp_video_file.write(video_data)
            tmp_video_file_path = tmp_video_file.name
            logger.info(f"Video downloaded to {tmp_video_file_path}")

        # 3. Transcribe the video file
        logger.info(f"Starting transcription for {tmp_video_file_path}...")
        result = whisper_model.transcribe(tmp_video_file_path, fp16=False) # fp16=False for CPU

        # 4. Save transcription to the database
        logger.info("Saving transcription data to the database...")
        supabase.table("transcriptions").insert({
            "project_id": project_id,
            "transcription_data": result
        }).execute()

        # 5. Update project and job status to 'completed'
        supabase.table("projects").update({"status": "transcribed"}).eq("id", project_id).execute()
        supabase.table("processing_jobs").update({"status": "completed"}).eq("project_id", project_id).execute()

        logger.info(f"Transcription for project {project_id} completed successfully.")

    except Exception as e:
        logger.error(f"Error during transcription for project {project_id}: {e}", exc_info=True)
        # Update job status to 'failed'
        supabase.table("processing_jobs").update({
            "status": "failed",
            "error_message": str(e)
        }).eq("project_id", project_id).execute()
    finally:
        # Clean up the temporary file
        if 'tmp_video_file_path' in locals() and os.path.exists(tmp_video_file_path):
            os.remove(tmp_video_file_path)
            logger.info(f"Temporary video file {tmp_video_file_path} deleted.")
