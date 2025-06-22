"""Celery tasks for video editing operations."""
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import tempfile
import shutil

from celery import shared_task
from celery.utils.log import get_task_logger

from app.core.config import settings
from app.services.storage import get_storage_client
from app.editing.factory import get_default_pipeline
from app.editing.core.processor import VideoEditingError

logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=3)
def process_video_editing(
    self,
    project_id: str,
    input_video_path: str,
    output_video_path: str,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process a video with the specified editing pipeline.
    
    Args:
        project_id: ID of the project
        input_video_path: Path to the input video in storage
        output_video_path: Path where the processed video should be saved
        config: Optional configuration for the editing pipeline
        
    Returns:
        Dict containing processing results
    """
    logger.info(f"Starting video editing for project {project_id}")
    
    storage = get_storage_client()
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Download the input video
        local_input_path = temp_dir / "input_video.mp4"
        logger.info(f"Downloading video from {input_video_path} to {local_input_path}")
        
        if not storage.download_file(input_video_path, local_input_path):
            error_msg = f"Failed to download video from {input_video_path}"
            logger.error(error_msg)
            raise VideoEditingError(error_msg)
        
        # Create output directory
        local_output_path = temp_dir / "output_video.mp4"
        
        # Get the editing pipeline
        pipeline = get_default_pipeline()
        
        # Process the video
        logger.info("Starting video processing pipeline")
        results = pipeline.run(
            input_path=local_input_path,
            output_path=local_output_path,
            project_id=project_id
        )
        
        # Upload the processed video
        if local_output_path.exists():
            logger.info(f"Uploading processed video to {output_video_path}")
            if not storage.upload_file(local_output_path, output_video_path):
                error_msg = f"Failed to upload processed video to {output_video_path}"
                logger.error(error_msg)
                raise VideoEditingError(error_msg)
            
            # Update the project with the processed video path
            from app.db.database import get_db
            from app.crud import project as project_crud
            
            db = next(get_db())
            project_crud.update_project(
                db=db,
                project_id=project_id,
                project_update={"processed_video_path": output_video_path}
            )
            
            logger.info(f"Successfully processed video for project {project_id}")
            return {
                'status': 'completed',
                'project_id': project_id,
                'processed_video_path': output_video_path,
                'processing_details': results
            }
        else:
            error_msg = "Processing completed but output file not found"
            logger.error(error_msg)
            raise VideoEditingError(error_msg)
            
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}", exc_info=True)
        
        # Retry on certain exceptions
        if self.request.retries < self.max_retries and not isinstance(e, VideoEditingError):
            retry_delay = 60 * (2 ** self.request.retries)  # Exponential backoff
            logger.info(f"Retrying task in {retry_delay} seconds (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=retry_delay)
        
        # Update project status on failure
        try:
            from app.db.database import get_db
            from app.crud import project as project_crud
            from app.schemas.project import ProjectUpdate
            
            db = next(get_db())
            project_crud.update_project(
                db=db,
                project_id=project_id,
                project_update={"status": "failed", "error": str(e)}
            )
        except Exception as update_error:
            logger.error(f"Failed to update project status: {update_error}", exc_info=True)
        
        raise
        
    finally:
        # Clean up temporary files
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
