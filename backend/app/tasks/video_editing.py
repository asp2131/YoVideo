# backend/app/tasks/video_editing.py (updated)

"""Celery tasks for video editing operations."""
import logging
import tempfile
import shutil
import os
from pathlib import Path
from typing import Dict, Any, Optional

from celery import shared_task
from celery.utils.log import get_task_logger

from app.services.supabase_client import supabase
from app.services.r2_client import get_r2_client
from app.editing.factory import create_enhanced_pipeline_for_project
from app.editing.pipeline.core import Context
from app.editing.utils.video_utils import create_highlight_video
from app.services.caption_service import segments_to_ass

logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=3)
def process_video_editing_task(
    self,
    project_id: str,
    processing_options: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process a video with intelligent editing based on processing options.
    
    Args:
        project_id: ID of the project
        processing_options: Processing configuration
        
    Returns:
        Dict containing processing results
    """
    logger.info(f"Starting intelligent editing for project {project_id}")
    
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Get project and transcription data
        project_response = supabase.table("projects").select("*").eq("id", project_id).single().execute()
        if not project_response.data:
            raise Exception(f"Project {project_id} not found")
        
        project = project_response.data
        video_path = project.get("video_path")
        
        if not video_path:
            raise Exception(f"No video path found for project {project_id}")
        
        # Get transcription
        transcription_response = supabase.table("transcriptions").select("*").eq("project_id", project_id).single().execute()
        transcription_data = transcription_response.data if transcription_response.data else None
        
        # Download the video
        local_input_path = temp_dir / "input_video.mp4"
        logger.info(f"Downloading video from {video_path}")
        
        client = get_r2_client()
        if not client:
            raise Exception("Failed to initialize R2 client")
        
        client.download_file(video_path, str(local_input_path))
        logger.info(f"Video downloaded to {local_input_path}")
        
        # Create editing preferences from processing options
        editing_preferences = {
            'style': processing_options.get('editing_style', 'engaging'),
            'target_duration': processing_options.get('target_duration', 60),
            'content_type': processing_options.get('content_type', 'general'),
            'preserve_speech': True,
            'enhance_audio': True,
            'detect_faces': processing_options.get('editing_style') in ['engaging', 'social_media']
        }
        
        # Extract transcription segments
        transcription_segments = []
        if transcription_data and transcription_data.get('transcription_data'):
            transcription_segments = transcription_data['transcription_data'].get('segments', [])
        
        # Create enhanced pipeline
        logger.info("Creating enhanced editing pipeline")
        pipeline = create_enhanced_pipeline_for_project(
            project_id=project_id,
            transcription=transcription_segments,
            editing_preferences=editing_preferences
        )
        
        # Create processing context
        context = Context(
            video_path=str(local_input_path),
            output_dir=str(temp_dir),
            metadata={
                'project_id': project_id,
                'processing_options': processing_options,
                'original_filename': project.get('original_filename', 'video.mp4')
            }
        )
        
        # Add transcription to context
        if transcription_segments:
            context.transcription = transcription_segments
        
        # Run the pipeline
        logger.info("Running intelligent editing pipeline")
        try:
            processed_context = pipeline.run(context)
        except Exception as pipeline_error:
            logger.error(f"Pipeline processing failed: {str(pipeline_error)}")
            # Fall back to simple caption overlay
            return await fallback_to_captions(project_id, local_input_path, transcription_data)
        
        # Extract highlights
        highlights = getattr(processed_context, 'highlights', [])
        logger.info(f"Generated {len(highlights)} highlights")
        
        if not highlights:
            logger.warning("No highlights generated, falling back to caption overlay")
            return await fallback_to_captions(project_id, local_input_path, transcription_data)
        
        # Create highlight video
        local_output_path = temp_dir / "highlights.mp4"
        
        try:
            result_path = create_highlight_video(
                input_path=local_input_path,
                highlights=highlights,
                output_path=local_output_path,
                temp_dir=temp_dir / "segments",
                keep_temp=False
            )
            
            if not result_path or not result_path.exists():
                raise Exception("Failed to create highlight video")
                
        except Exception as highlight_error:
            logger.error(f"Highlight video creation failed: {str(highlight_error)}")
            return await fallback_to_captions(project_id, local_input_path, transcription_data)
        
        # Add captions to highlight video if transcription is available
        if transcription_segments:
            local_output_with_captions = temp_dir / "highlights_with_captions.mp4"
            
            try:
                await add_captions_to_video(
                    str(local_output_path),
                    str(local_output_with_captions),
                    transcription_segments,
                    highlights
                )
                local_output_path = local_output_with_captions
            except Exception as caption_error:
                logger.warning(f"Failed to add captions to highlights: {str(caption_error)}")
                # Continue with highlights without captions
        
        # Upload processed video
        processed_filename = f"processed_{project_id}.mp4"
        logger.info(f"Uploading processed video to {processed_filename}")
        
        upload_result = client.upload_file(
            str(local_output_path),
            processed_filename,
            "video/mp4"
        )
        
        if not upload_result.get('success'):
            raise Exception(f"Failed to upload processed video: {upload_result}")
        
        # Update project with processed video path
        supabase.table("projects").update({
            "processed_video_path": processed_filename,
            "status": "completed"
        }).eq("id", project_id).execute()
        
        # Update processing job
        supabase.table("processing_jobs").update({
            "status": "completed"
        }).eq("project_id", project_id).execute()
        
        logger.info(f"Successfully processed video for project {project_id}")
        
        return {
            'status': 'completed',
            'project_id': project_id,
            'processed_video_path': processed_filename,
            'highlights_count': len(highlights),
            'total_highlight_duration': sum(h.get('duration', 0) for h in highlights),
            'processing_details': {
                'editing_style': editing_preferences['style'],
                'target_duration': editing_preferences['target_duration'],
                'content_type': editing_preferences['content_type']
            }
        }
        
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}", exc_info=True)
        
        # Update project and job status on failure
        try:
            supabase.table("projects").update({
                "status": "failed"
            }).eq("id", project_id).execute()
            
            supabase.table("processing_jobs").update({
                "status": "failed",
                "error_message": str(e)
            }).eq("project_id", project_id).execute()
        except Exception as update_error:
            logger.error(f"Failed to update status: {update_error}")
        
        # Retry on certain exceptions
        if self.request.retries < self.max_retries:
            retry_delay = 60 * (2 ** self.request.retries)  # Exponential backoff
            logger.info(f"Retrying task in {retry_delay} seconds (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=retry_delay)
        
        raise
        
    finally:
        # Clean up temporary files
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


async def add_captions_to_video(
    input_video_path: str,
    output_video_path: str,
    transcription_segments: list,
    highlights: list
) -> None:
    """Add captions to a video using ASS format."""
    import subprocess
    
    # Filter transcription segments to only include those in highlights
    highlight_segments = []
    for highlight in highlights:
        start = highlight.get('start', 0)
        end = highlight.get('end', 0)
        
        # Find matching transcription segments
        for seg in transcription_segments:
            seg_start = seg.get('start', 0)
            seg_end = seg.get('end', 0)
            
            # Check if segment overlaps with highlight
            if seg_start < end and seg_end > start:
                # Adjust segment timing to be relative to highlight
                adjusted_segment = seg.copy()
                adjusted_segment['start'] = max(0, seg_start - start)
                adjusted_segment['end'] = min(end - start, seg_end - start)
                highlight_segments.append(adjusted_segment)
    
    # Create ASS content
    ass_content = segments_to_ass(highlight_segments)
    
    # Create temporary ASS file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False) as ass_file:
        ass_file.write(ass_content)
        ass_file.flush()
        ass_file_path = ass_file.name
    
    try:
        # FFmpeg command to add captions
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', input_video_path,
            '-vf', f"ass={ass_file_path}",
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-y',
            output_video_path
        ]
        
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)
        logger.info("Successfully added captions to video")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed: {e.stderr}")
        raise Exception(f"Failed to add captions: {e.stderr}")
    finally:
        # Clean up ASS file
        if os.path.exists(ass_file_path):
            os.unlink(ass_file_path)


async def fallback_to_captions(
    project_id: str,
    input_video_path: Path,
    transcription_data: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Fallback to simple caption overlay when intelligent editing fails.
    """
    import subprocess
    
    logger.info(f"Falling back to caption overlay for project {project_id}")
    
    if not transcription_data or not transcription_data.get('srt_content'):
        logger.warning("No transcription data available for caption overlay")
        # Just mark as completed without processing
        supabase.table("projects").update({
            "status": "completed"
        }).eq("id", project_id).execute()
        
        return {
            'status': 'completed',
            'project_id': project_id,
            'message': 'No captions available'
        }
    
    try:
        # Create temporary ASS file
        ass_content = transcription_data['srt_content']
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False) as ass_file:
            ass_file.write(ass_content)
            ass_file.flush()
            ass_file_path = ass_file.name
        
        # Create output video with captions
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as output_file:
            output_video_path = output_file.name
        
        # FFmpeg command to overlay captions
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', str(input_video_path),
            '-vf', f"ass={ass_file_path}",
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-y',
            output_video_path
        ]
        
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
        
        # Upload processed video
        client = get_r2_client()
        processed_filename = f"processed_{project_id}.mp4"
        
        upload_result = client.upload_file(
            output_video_path,
            processed_filename,
            "video/mp4"
        )
        
        if upload_result.get('success'):
            # Update project
            supabase.table("projects").update({
                "processed_video_path": processed_filename,
                "status": "completed"
            }).eq("id", project_id).execute()
            
            logger.info(f"Caption overlay completed for project {project_id}")
            
            return {
                'status': 'completed',
                'project_id': project_id,
                'processed_video_path': processed_filename,
                'message': 'Caption overlay completed'
            }
        else:
            raise Exception("Failed to upload processed video")
            
    except Exception as e:
        logger.error(f"Caption overlay fallback failed: {str(e)}")
        raise
    finally:
        # Clean up temporary files
        if 'ass_file_path' in locals() and os.path.exists(ass_file_path):
            os.unlink(ass_file_path)
        if 'output_video_path' in locals() and os.path.exists(output_video_path):
            os.unlink(output_video_path)


@shared_task(bind=True)
def process_existing_video_editing(
    self,
    project_id: str,
    processing_options: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply intelligent editing to an existing transcribed video.
    
    This is useful when a user wants to re-process a video with different settings
    or apply intelligent editing to a video that was originally processed with
    captions only.
    """
    logger.info(f"Processing existing video with intelligent editing: {project_id}")
    
    try:
        # Check if intelligent editing is enabled
        if not processing_options.get('enable_intelligent_editing', False):
            logger.info("Intelligent editing not enabled, skipping")
            return {'status': 'skipped', 'message': 'Intelligent editing not enabled'}
        
        # Update project status
        supabase.table("projects").update({
            "status": "processing",
            "processing_options": processing_options
        }).eq("id", project_id).execute()
        
        # Call the main processing task
        return process_video_editing_task(project_id, processing_options)
        
    except Exception as e:
        logger.error(f"Failed to process existing video: {str(e)}", exc_info=True)
        
        # Update project status
        supabase.table("projects").update({
            "status": "failed"
        }).eq("id", project_id).execute()
        
        raise