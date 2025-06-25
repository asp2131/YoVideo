# backend/app/tasks/transcription.py (updated version)

import os
import tempfile
import logging
import subprocess
import json
from celery import current_task
from app.core.celery_app import celery_app
from app.services.supabase_client import supabase
from app.services.r2_client import get_r2_client
from app.services.caption_service import segments_to_ass
from app.services.enhanced_caption_service import create_professional_captions
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def transcribe_video_task(self, project_id: str, processing_options: dict = None):
    """
    Enhanced transcription task that can either:
    1. Just add captions to the full video
    2. Create intelligent highlights + add captions
    """
    logger.info(f"Starting transcription for project_id: {project_id}")
    
    # Default processing options
    if processing_options is None:
        processing_options = {
            'enable_intelligent_editing': False,
            'editing_style': 'engaging',
            'target_duration': 60,
            'content_type': 'general'
        }
    
    enable_editing = processing_options.get('enable_intelligent_editing', False)
    logger.info(f"Intelligent editing: {'enabled' if enable_editing else 'disabled'}")

    try:
        # 1. Get video path from the projects table
        project_response = supabase.table("projects").select("video_path").eq("id", project_id).execute()
        
        if not project_response.data or len(project_response.data) == 0:
            raise ValueError(f"No project found with id {project_id}")
            
        video_path = project_response.data[0].get("video_path")

        if not video_path:
            raise ValueError(f"No video_path found for project {project_id}")

        # 2. Download video from R2 Storage
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(video_path)[1]) as tmp_video_file:
            tmp_video_file_path = tmp_video_file.name
            
        logger.info(f"Downloading {video_path} from R2 Storage...")
        
        client = get_r2_client()
        if client is None:
            raise Exception("Failed to initialize R2 client")
            
        try:
            client.download_file(video_path, tmp_video_file_path)
            logger.info(f"Video downloaded to {tmp_video_file_path}")
        except Exception as e:
            logger.error(f"Failed to download video from R2: {str(e)}")
            raise Exception(f"Failed to download video: {str(e)}")
            
        # Validate video file
        file_size = os.path.getsize(tmp_video_file_path)
        logger.info(f"Video file size: {file_size} bytes")
        
        if file_size == 0:
            raise Exception("Downloaded video file is empty")

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
            segments = result.get("segments", [])
            
            logger.info("Transcription completed successfully")
        except Exception as transcription_error:
            logger.error(f"Whisper transcription failed: {str(transcription_error)}")
            raise transcription_error

        # 4. Save transcription to database
        if not segments and not transcription_text:
            logger.warning("Whisper produced no segments or text - likely no audible speech in video")
            # Create a minimal transcription entry
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
            
            # Update project status to completed
            supabase.table("projects").update({
                "status": "completed"
            }).eq("id", project_id).execute()
            
            return

        # Create ASS content for captions
        ass_content = create_professional_captions(segments)

        if not ass_content:
            logger.error("Failed to generate professional captions")
            raise Exception("Caption generation failed")

        logger.info(f"Generated professional captions with word-by-word timing")
        logger.info(f"Caption content length: {len(ass_content)} characters")
        
        # Save transcription data
        transcription_data = {
            "project_id": project_id,
            "transcription_data": {
                "text": transcription_text,
                "segments": result["segments"],
                "language": result.get("language", "en"),
                "word_level_timing": True,  # Flag to indicate enhanced timing
                "caption_style": "professional_shortform"
            },
            "srt_content": ass_content  # This is actually ASS content with professional timing
        }
        
        supabase.table("transcriptions").insert(transcription_data).execute()
        logger.info(f"Saved transcription to database for project {project_id}")

        # 5. Choose processing path based on options
        if enable_editing:
            # Intelligent editing + captions
            logger.info(f"Starting intelligent editing for project {project_id}")
            processed_video_path = asyncio.run(process_intelligent_editing(
                project_id, 
                tmp_video_file_path, 
                segments, 
                processing_options
            ))
        else:
            # Just add captions to full video
            logger.info(f"Starting caption overlay for project {project_id}")
            processed_video_path = generate_caption_overlay(
                project_id, 
                tmp_video_file_path, 
                ass_content
            )
        
        if processed_video_path:
            logger.info(f"Processing completed for project {project_id}")

        # 6. Update project status to completed
        supabase.table("projects").update({
            "status": "completed"
        }).eq("id", project_id).execute()

        # 7. Update processing job status to completed
        supabase.table("processing_jobs").update({
            "status": "completed"
        }).eq("project_id", project_id).execute()

        logger.info(f"Processing completed for project {project_id}")

    except Exception as e:
        error_message = str(e)
        logger.error(f"Processing failed for project {project_id}: {error_message}", exc_info=True)
        
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
        if 'tmp_video_file_path' in locals() and os.path.exists(tmp_video_file_path):
            os.unlink(tmp_video_file_path)


async def process_intelligent_editing(
    project_id: str, 
    input_video_path: str, 
    transcription_segments: list, 
    processing_options: dict
) -> str:
    """
    Process video with intelligent editing using the editing pipeline.
    """
    try:
        # Import the editing pipeline
        from app.editing.factory import create_enhanced_pipeline_for_project
        
        # Convert processing options to editing preferences
        editing_preferences = {
            'style': processing_options.get('editing_style', 'engaging'),
            'target_duration': processing_options.get('target_duration', 60),
            'content_type': processing_options.get('content_type', 'general'),
            'preserve_speech': True,
            'enhance_audio': True,
            'detect_faces': True
        }
        
        # Create enhanced pipeline
        pipeline = create_enhanced_pipeline_for_project(
            project_id=project_id,
            transcription=transcription_segments,
            editing_preferences=editing_preferences
        )
        
        # Create context for processing
        from app.editing.pipeline.core import Context
        context = Context(
            video_path=input_video_path,
            metadata={
                'project_id': project_id,
                'processing_options': processing_options
            }
        )
        
        # Add transcription to context
        context.transcription = transcription_segments
        
        # Run the pipeline
        logger.info("Running intelligent editing pipeline...")
        processed_context = pipeline.run(context)
        
        # Extract highlights
        highlights = getattr(processed_context, 'highlights', [])
        logger.info(f"Generated {len(highlights)} highlights")
        
        if not highlights:
            logger.warning("No highlights generated, falling back to caption overlay")
            return generate_caption_overlay(project_id, input_video_path, segments_to_ass(transcription_segments))
        
        # Create highlight video with captions
        highlight_video_path = await create_highlight_video_with_captions(
            project_id,
            input_video_path,
            highlights,
            transcription_segments
        )
        
        return highlight_video_path
        
    except Exception as e:
        logger.error(f"Intelligent editing failed for project {project_id}: {str(e)}")
        logger.info("Falling back to caption overlay")
        return generate_caption_overlay(project_id, input_video_path, segments_to_ass(transcription_segments))


async def create_highlight_video_with_captions(
    project_id: str,
    input_video_path: str,
    highlights: list,
    transcription_segments: list
) -> str:
    """
    Create a highlight video with captions burned in.
    """
    ass_file_path = None
    highlight_video_path = None
    output_video_path = None
    
    try:
        # Create segments for highlights
        highlight_segments = []
        for highlight in highlights:
            start = highlight.get('start', 0)
            end = highlight.get('end', 0)
            
            # Find matching transcription segments
            matching_segments = [
                seg for seg in transcription_segments
                if seg.get('start', 0) >= start and seg.get('end', 0) <= end
            ]
            
            highlight_segments.extend(matching_segments)
        
        # Create ASS content for highlights
        ass_content = segments_to_ass(highlight_segments)
        
        # Create temporary ASS file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False) as ass_file:
            ass_file.write(ass_content)
            ass_file.flush()
            ass_file_path = ass_file.name
        
        # Create highlight video (without captions first)
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as highlight_file:
            highlight_video_path = highlight_file.name
        
        # Extract highlights using ffmpeg
        from app.editing.utils.video_utils import extract_segments
        segments_for_extraction = [
            {'start': h.get('start', 0), 'end': h.get('end', 0)}
            for h in highlights
        ]
        
        extract_segments(
            input_path=input_video_path,
            segments=segments_for_extraction,
            output_path=highlight_video_path
        )
        
        # Add captions to highlight video
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as output_file:
            output_video_path = output_file.name
        
        # FFmpeg command to add captions
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', highlight_video_path,
            '-vf', f"ass={ass_file_path}",
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-y',
            output_video_path
        ]
        
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        
        # Upload to R2
        processed_filename = f"processed_{project_id}.mp4"
        client = get_r2_client()
        
        upload_result = client.upload_file(
            output_video_path,
            processed_filename,
            "video/mp4"
        )
        
        # Update project with processed video path
        supabase.table("projects").update({
            "processed_video_path": processed_filename
        }).eq("id", project_id).execute()
        
        logger.info(f"Highlight video with captions uploaded: {processed_filename}")
        return processed_filename
        
    except Exception as e:
        logger.error(f"Failed to create highlight video with captions: {str(e)}")
        raise
    finally:
        # Clean up temporary files
        for temp_file in [ass_file_path, highlight_video_path, output_video_path]:
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)

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

        # Upload processed video to R2 Storage
        processed_filename = f"processed_{project_id}.mp4"
        
        logger.info(f"Uploading processed video to R2: {processed_filename}")
        
        client = get_r2_client()
        if client is None:
            raise Exception("Failed to initialize R2 client for processed video upload")
        
        try:
            upload_result = client.upload_file(
                output_video_path, 
                processed_filename, 
                "video/mp4"
            )
            logger.info(f"Processed video uploaded to R2: {upload_result}")
        except Exception as upload_error:
            logger.error(f"Failed to upload processed video to R2: {str(upload_error)}")
            raise Exception(f"Failed to upload processed video: {str(upload_error)}")

        # Update project with processed video path
        supabase.table("projects").update({
            "processed_video_path": processed_filename
        }).eq("id", project_id).execute()

        logger.info(f"Processed video uploaded to R2 as {processed_filename}")
        
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