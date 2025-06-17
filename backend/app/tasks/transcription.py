import os
import tempfile
import logging
import subprocess
import json
from celery import current_task
from app.core.celery_app import celery_app
from app.services.supabase_client import supabase
from app.services.caption_service import segments_to_ass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_whisper_subprocess(video_path):
    """Run whisper via subprocess to avoid memory issues."""
    try:
        # Set up environment with virtual environment PATH
        env = os.environ.copy()
        venv_bin = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.venv', 'bin')
        env['PATH'] = f"{venv_bin}:{env.get('PATH', '')}"
        
        # Use whisper CLI with JSON output
        cmd = [
            'whisper', video_path,
            '--model', 'tiny',
            '--output_format', 'json',
            '--output_dir', '/tmp',
            '--fp16', 'False',
            '--verbose', 'False'
        ]
        
        logger.info(f"Running whisper command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        
        if result.returncode != 0:
            logger.error(f"Whisper subprocess failed: {result.stderr}")
            raise Exception(f"Whisper failed: {result.stderr}")
        
        # Read the JSON output
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        json_path = f"/tmp/{video_name}.json"
        
        if not os.path.exists(json_path):
            raise Exception(f"Whisper output file not found: {json_path}")
        
        with open(json_path, 'r') as f:
            json_content = f.read()
            logger.info(f"Raw JSON content from Whisper: {json_content[:500]}...")
            whisper_result = json.loads(json_content)
        
        logger.info(f"Parsed Whisper result keys: {list(whisper_result.keys())}")
        logger.info(f"Whisper segments count: {len(whisper_result.get('segments', []))}")
        
        # Clean up the JSON file
        os.remove(json_path)
        
        return whisper_result
        
    except subprocess.TimeoutExpired:
        logger.error("Whisper subprocess timed out")
        raise Exception("Transcription timed out")
    except Exception as e:
        logger.error(f"Whisper subprocess error: {str(e)}")
        raise

@celery_app.task(bind=True)
def transcribe_video_task(self, project_id: str):
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
            
            # Validate video file
            file_size = os.path.getsize(tmp_video_file_path)
            logger.info(f"Video file size: {file_size} bytes")
            
            if file_size == 0:
                raise Exception("Downloaded video file is empty")
            
            # Check if file has audio using ffprobe
            try:
                ffprobe_cmd = [
                    'ffprobe', '-v', 'quiet', '-select_streams', 'a:0', 
                    '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', 
                    tmp_video_file_path
                ]
                result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, timeout=30)
                has_audio = result.stdout.strip() == 'audio'
                logger.info(f"Video has audio track: {has_audio}")
                
                if not has_audio:
                    logger.warning("Video file has no audio track - transcription will be empty")
                    # Still proceed but with a warning
                    
            except Exception as probe_error:
                logger.warning(f"Could not probe video file: {probe_error}")
                # Continue anyway

        # 3. Transcribe the video file
        logger.info(f"Starting transcription for {tmp_video_file_path}...")
        
        # Update project status to processing
        supabase.table("projects").update({
            "status": "processing"
        }).eq("id", project_id).execute()
        
        try:
            # Run whisper via subprocess
            result = run_whisper_subprocess(tmp_video_file_path)
            
            # Extract transcription text and segments
            transcription_text = result["text"]
            
            logger.info("Transcription completed successfully")
        except Exception as transcription_error:
            logger.error(f"Whisper transcription failed: {str(transcription_error)}")
            raise transcription_error

        # 4. Save transcription to database
        logger.info(f"Transcription result keys: {list(result.keys())}")
        logger.info(f"Full transcription result: {result}")
        logger.info(f"Number of segments: {len(result.get('segments', []))}")
        if result.get('segments'):
            logger.info(f"First segment: {result['segments'][0]}")
        
        segments = result.get("segments", [])
        transcription_text = result.get("text", "").strip()
        
        if not segments and not transcription_text:
            logger.warning("Whisper produced no segments or text - likely no audible speech in video")
            # Create a minimal transcription entry to avoid breaking the workflow
            transcription_data = {
                "project_id": project_id,
                "transcription_data": {
                    "text": "",
                    "segments": [],
                    "language": result.get("language", "en")
                },
                "srt_content": ""
            }
            
            supabase.table("transcriptions").insert(transcription_data).execute()
            logger.info(f"Saved empty transcription to database for project {project_id}")
            
            # Update project status to completed (no caption overlay needed)
            supabase.table("projects").update({
                "status": "completed"
            }).eq("id", project_id).execute()
            
            # Update processing job status to completed
            supabase.table("processing_jobs").update({
                "status": "completed"
            }).eq("project_id", project_id).execute()
            
            logger.info(f"Transcription completed for project {project_id} (no speech detected)")
            return
        
        if not segments:
            logger.error("No segments found in transcription result")
            logger.error(f"Full result structure: {json.dumps(result, indent=2)}")
            raise Exception("Transcription produced no segments")
        
        # Use ASS format for better animation capabilities
        ass_content = segments_to_ass(segments)
        logger.info(f"Generated ASS content length: {len(ass_content)}")
        if len(ass_content) == 0:
            logger.error("ASS content is empty despite having segments")
            logger.error(f"Segments data: {segments[:3]}")  # Log first 3 segments for debugging
            raise Exception("Generated ASS content is empty")
        logger.info(f"ASS content preview: {ass_content[:400]}...")
        
        transcription_data = {
            "project_id": project_id,
            "transcription_data": {
                "text": transcription_text,
                "segments": result["segments"],
                "language": result.get("language", "en")
            },
            "srt_content": ass_content
        }
        
        supabase.table("transcriptions").insert(transcription_data).execute()
        logger.info(f"Saved transcription to database for project {project_id}")

        # 5. Generate video with caption overlay
        logger.info(f"Starting caption overlay for project {project_id}")
        processed_video_path = generate_caption_overlay(project_id, tmp_video_file.name, ass_content)
        
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


def generate_caption_overlay(project_id: str, input_video_path: str, ass_content: str) -> str:
    """Generate a video with caption overlay using FFmpeg."""
    ass_file_path = None
    output_video_path = None
    
    try:
        # Create temporary ASS file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False) as ass_file:
            ass_file.write(ass_content)
            ass_file.flush()  # Ensure content is written
            ass_file_path = ass_file.name

        # Verify ASS file exists and is readable
        if not os.path.exists(ass_file_path):
            raise Exception(f"ASS file was not created: {ass_file_path}")
        
        with open(ass_file_path, 'r') as f:
            ass_check = f.read()
            if not ass_check.strip():
                raise Exception("ASS file is empty")
        
        logger.info(f"Created ASS file: {ass_file_path} ({len(ass_content)} chars)")

        # Create output video file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as output_file:
            output_video_path = output_file.name

        # FFmpeg command to overlay captions using ASS format for animations
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', input_video_path,
            '-vf', f"ass={ass_file_path}",
            '-c:a', 'copy',  # Copy audio without re-encoding
            '-c:v', 'libx264',  # Use H.264 for video
            '-preset', 'medium',  # Balance between speed and quality
            '-crf', '23',  # Good quality setting
            '-y',  # Overwrite output file
            output_video_path
        ]

        logger.info(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")
        
        # Update project status to indicate caption overlay is starting
        supabase.table("projects").update({
            "status": "adding_captions"
        }).eq("id", project_id).execute()
        
        # Run FFmpeg with progress monitoring
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            universal_newlines=True
        )
        
        # Capture all output
        stdout, stderr = process.communicate()
        
        logger.info(f"FFmpeg stdout: {stdout}")
        logger.info(f"FFmpeg stderr: {stderr}")
        
        if process.returncode != 0:
            logger.error(f"FFmpeg failed with return code {process.returncode}")
            logger.error(f"FFmpeg stdout: {stdout}")
            logger.error(f"FFmpeg stderr: {stderr}")
            raise Exception(f"FFmpeg processing failed: {stderr}")
        
        logger.info("FFmpeg processing completed successfully")

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
        if 'ass_file_path' in locals() and os.path.exists(ass_file_path):
            os.unlink(ass_file_path)
        if 'output_video_path' in locals() and output_video_path and os.path.exists(output_video_path):
            os.unlink(output_video_path)
