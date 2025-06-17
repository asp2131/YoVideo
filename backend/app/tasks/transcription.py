import os
import tempfile
import logging
import subprocess
import whisper
from celery import current_task
from app.core.celery_app import celery_app
from app.services.supabase_client import supabase
from app.services.caption_service import format_srt_time, break_text_into_lines

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

        # 4. Save transcription to database
        transcription_text = result["text"]
        srt_content = format_srt_time(result["segments"])
        transcription_data = {
            "project_id": project_id,
            "transcription_text": transcription_text,
            "srt_content": srt_content,
            "language": "en"  # Default to English for now
        }
        
        supabase.table("transcriptions").insert(transcription_data).execute()
        logger.info(f"Saved transcription to database for project {project_id}")

        # 5. Generate video with caption overlay
        logger.info(f"Starting caption overlay for project {project_id}")
        processed_video_path = generate_caption_overlay(project_id, tmp_video_file.name, srt_content)
        
        if processed_video_path:
            logger.info(f"Caption overlay completed for project {project_id}")
        
        # 6. Update project status to completed
        supabase.table("projects").update({
            "status": "completed"
        }).eq("id", project_id).execute()

        # 7. Update processing job status to completed
        supabase.table("processing_jobs").update({
            "status": "completed"
        }).eq("project_id", project_id).execute()

        logger.info(f"Transcription and caption overlay completed for project {project_id}")

    except Exception as e:
        error_message = str(e)
        logger.error(f"Transcription failed for project {project_id}: {error_message}", exc_info=True)
        
        # Update processing job status to failed
        supabase.table("processing_jobs").update({
            "status": "failed",
            "error_message": error_message
        }).eq("project_id", project_id).execute()
        
        # Update project status to failed
        supabase.table("projects").update({
            "status": "failed"
        }).eq("id", project_id).execute()

    finally:
        # Clean up temporary video file
        if 'tmp_video_file' in locals() and os.path.exists(tmp_video_file.name):
            os.unlink(tmp_video_file.name)


def generate_caption_overlay(project_id: str, input_video_path: str, srt_content: str) -> str:
    """Generate a video with caption overlay using FFmpeg."""
    try:
        # Create temporary SRT file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as srt_file:
            srt_file.write(srt_content)
            srt_file_path = srt_file.name

        # Create output video file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as output_file:
            output_video_path = output_file.name

        # FFmpeg command to overlay captions
        # Using a simple white text with black outline for good visibility
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', input_video_path,
            '-vf', f"subtitles={srt_file_path}:force_style='FontSize=24,PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=2,Alignment=2'",
            '-c:a', 'copy',  # Copy audio without re-encoding
            '-c:v', 'libx264',  # Use H.264 for video
            '-preset', 'medium',  # Balance between speed and quality
            '-crf', '23',  # Good quality setting
            '-y',  # Overwrite output file
            output_video_path
        ]

        logger.info(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")
        
        # Run FFmpeg
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg failed: {result.stderr}")
            raise Exception(f"FFmpeg processing failed: {result.stderr}")

        # Upload processed video to Supabase Storage
        processed_filename = f"processed_{project_id}.mp4"
        
        with open(output_video_path, 'rb') as video_file:
            video_data = video_file.read()
            
        storage_response = supabase.storage.from_("videos").upload(
            processed_filename,
            video_data,
            file_options={"content-type": "video/mp4"}
        )

        if hasattr(storage_response, 'error') and storage_response.error:
            logger.error(f"Failed to upload processed video: {storage_response.error}")
            raise Exception(f"Failed to upload processed video: {storage_response.error}")

        # Update project with processed video path
        supabase.table("projects").update({
            "processed_video_path": processed_filename
        }).eq("id", project_id).execute()

        logger.info(f"Processed video uploaded as {processed_filename}")
        
        return processed_filename

    except Exception as e:
        logger.error(f"Caption overlay failed for project {project_id}: {str(e)}")
        raise e
    
    finally:
        # Clean up temporary files
        if 'srt_file_path' in locals() and os.path.exists(srt_file_path):
            os.unlink(srt_file_path)
        if 'output_video_path' in locals() and os.path.exists(output_video_path):
            os.unlink(output_video_path)
