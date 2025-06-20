from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import Response
from pydantic import BaseModel
from app.schemas.transcription import TranscriptionRequest
from app.tasks.transcription import transcribe_video_task
from app.services.supabase_client import supabase
import logging
import uuid
import os
import tempfile
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class TranscriptionRequest(BaseModel):
    project_id: str

@router.post("/transcribe")
async def start_transcription(request: TranscriptionRequest):
    """
    Starts a video transcription task for a given project_id.
    This endpoint creates a job record and queues the background task.
    """
    project_id = request.project_id
    logger.info(f"Received transcription request for project_id: {project_id}")

    try:
        # 1. Check if the project exists
        project_response = supabase.table("projects").select("id").eq("id", project_id).single().execute()
        if not project_response.data:
            raise HTTPException(status_code=404, detail=f"Project with id {project_id} not found.")

        # 2. Create a new processing job in the database
        job_response = supabase.table("processing_jobs").insert({
            "project_id": project_id,
            "job_type": "transcription",
            "status": "pending"
        }).execute()
        
        if not job_response.data or len(job_response.data) == 0:
            raise HTTPException(status_code=500, detail="Failed to create processing job.")
        
        job_id = job_response.data[0].get("id")
        if not job_id:
            raise HTTPException(status_code=500, detail="Failed to create processing job.")

        # 3. Queue the background task
        transcribe_video_task.delay(project_id)
        logger.info(f"Queued transcription task for project_id: {project_id}, job_id: {job_id}")

        return {"message": "Transcription task started", "job_id": job_id}

    except Exception as e:
        logger.error(f"Failed to start transcription for project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start transcription task: {str(e)}")

# Chunk size for file uploads (5MB chunks)
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB

async def upload_to_supabase_with_timeout(file_path: str, storage_filename: str, content_type: str, timeout: int = 300):
    """Upload file to Supabase with timeout handling."""
    def sync_upload():
        with open(file_path, 'rb') as f:
            return supabase.storage.from_("videos").upload(
                path=storage_filename,
                file=f,
                file_options={"content-type": content_type}
            )
    
    # Run the sync upload in a thread pool with timeout
    try:
        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, sync_upload),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408,
            detail=f"Upload timed out after {timeout} seconds"
        )

@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    project_name: str = Form(...)
):
    """
    Upload a video file and create a new project.
    Uses chunked uploads for better reliability with large files.
    """
    try:
        # Validate file type
        allowed_extensions = {'.mp4', '.mov', '.avi', '.webm', '.mkv'}
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        storage_filename = f"{file_id}{file_extension}"
        
        # Map file extensions to MIME types
        mime_map = {
            '.mp4': 'video/mp4',
            '.mov': 'video/quicktime',
            '.avi': 'video/x-msvideo',
            '.webm': 'video/webm',
            '.mkv': 'video/x-matroska'
        }
        
        # Get MIME type from file extension
        content_type = mime_map.get(file_extension.lower(), 'application/octet-stream')
        
        # Create a temporary file for chunked upload
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            try:
                # Read and write the file in chunks
                total_size = 0
                chunk_number = 0
                
                while True:
                    chunk = await file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    temp_file.write(chunk)
                    chunk_number += 1
                    total_size += len(chunk)
                    logger.debug(f"Read chunk {chunk_number}: {len(chunk)} bytes (total: {total_size} bytes)")
                
                temp_file_path = temp_file.name
                logger.info(f"Successfully saved {total_size} bytes to temporary file: {temp_file_path}")
                
                # Upload to Supabase Storage with retry logic
                max_retries = 3
                last_error = None
                
                for attempt in range(max_retries):
                    try:
                        logger.info(f"Starting upload attempt {attempt + 1} of {max_retries}")
                        
                        # Upload to Supabase with timeout
                        logger.info(f"Starting Supabase upload for file: {storage_filename} ({total_size} bytes)")
                        storage_response = await upload_to_supabase_with_timeout(
                            temp_file_path, 
                            storage_filename, 
                            content_type,
                            timeout=300  # 5 minutes
                        )
                        logger.info(f"Supabase upload response: {storage_response}")
                            
                        # If we get here, upload was successful
                        logger.info(f"Successfully uploaded file to storage: {storage_filename}")
                        break
                            
                    except Exception as upload_error:
                        last_error = upload_error
                        logger.error(f"Upload attempt {attempt + 1} failed: {str(upload_error)}")
                        if attempt < max_retries - 1:  # Don't sleep on the last attempt
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    # This runs if the loop completes without breaking (all retries failed)
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to upload file after {max_retries} attempts: {str(last_error)}"
                    )
                
                # Create project record in database
                project_data = {
                    "id": file_id,
                    "name": project_name,
                    "original_filename": file.filename,
                    "file_path": storage_filename,
                    "file_size": total_size,
                    "status": "uploaded"
                }
                
                db_response = supabase.table("projects").insert(project_data).execute()
                
                if not db_response.data:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to create project record in database"
                    )
                
                return {"id": file_id, "status": "uploaded", "filename": storage_filename}
                
            except Exception as e:
                logger.error(f"Error during file upload: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to process file upload: {str(e)}"
                )
            finally:
                # Clean up the temporary file
                try:
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                        logger.info(f"Cleaned up temporary file: {temp_file_path}")
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up temporary file: {str(cleanup_error)}")
                    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in upload_video: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during file upload: {str(e)}"
        )

@router.get("/projects")
async def list_projects():
    """List all projects."""
    try:
        response = supabase.table("projects").select("*").order("created_at", desc=True).execute()
        return {"projects": response.data}
    except Exception as e:
        logger.error(f"Failed to list projects: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")

@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get a specific project with its transcription and processing jobs."""
    try:
        # Get project details
        project_response = supabase.table("projects").select("*").eq("id", project_id).execute()
        
        if not project_response.data or len(project_response.data) == 0:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project = project_response.data[0]
        
        # Get transcription if exists
        transcription_response = supabase.table("transcriptions").select("*").eq("project_id", project_id).execute()
        transcription = transcription_response.data[0] if transcription_response.data else None
        
        # Get processing jobs
        jobs_response = supabase.table("processing_jobs").select("*").eq("project_id", project_id).order("created_at", desc=True).execute()
        
        return {
            "project": project,
            "transcription": transcription,
            "processing_jobs": jobs_response.data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get project: {str(e)}")

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and its associated data."""
    try:
        # Get project to find video file
        project_response = supabase.table("projects").select("video_path").eq("id", project_id).execute()
        
        if not project_response.data or len(project_response.data) == 0:
            raise HTTPException(status_code=404, detail="Project not found")
        
        video_path = project_response.data[0]["video_path"]
        
        # Delete from storage (ignore errors if file doesn't exist)
        try:
            supabase.storage.from_("videos").remove([video_path])
        except:
            pass  # File might not exist, continue with database cleanup
        
        # Delete project (cascading deletes will handle related records)
        supabase.table("projects").delete().eq("id", project_id).execute()
        
        return {"message": "Project deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")

@router.get("/projects/{project_id}/download/srt")
async def download_srt(project_id: str):
    """Download the SRT file for a project."""
    try:
        # Get transcription data
        transcription_response = supabase.table("transcriptions").select("srt_content").eq("project_id", project_id).execute()
        
        if not transcription_response.data or len(transcription_response.data) == 0:
            raise HTTPException(status_code=404, detail="Transcription not found")
        
        srt_content = transcription_response.data[0]["srt_content"]
        
        if not srt_content:
            raise HTTPException(status_code=404, detail="SRT content not available")
        
        # Get project name for filename
        project_response = supabase.table("projects").select("name").eq("id", project_id).execute()
        project_name = project_response.data[0]["name"] if project_response.data else "video"
        
        # Clean filename
        safe_filename = "".join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_filename}.srt"
        
        return Response(
            content=srt_content,
            media_type="application/x-subrip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download SRT for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download SRT: {str(e)}")

@router.get("/projects/{project_id}/download/video")
async def download_video(project_id: str, processed: bool = False):
    """Download the original or processed video file."""
    try:
        # Get project details
        project_response = supabase.table("projects").select("name, video_path, processed_video_path").eq("id", project_id).execute()
        
        if not project_response.data or len(project_response.data) == 0:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project = project_response.data[0]
        
        # Choose which video to download
        if processed:
            video_path = project.get("processed_video_path")
            if not video_path:
                raise HTTPException(status_code=404, detail="Processed video not available. Please wait for processing to complete.")
            filename_suffix = "_with_captions"
        else:
            video_path = project["video_path"]
            filename_suffix = "_original"
        
        # Download from Supabase Storage
        video_data = supabase.storage.from_("videos").download(video_path)
        
        # Get file extension for proper content type
        file_extension = os.path.splitext(video_path)[1].lower()
        content_type_map = {
            '.mp4': 'video/mp4',
            '.mov': 'video/quicktime',
            '.avi': 'video/x-msvideo',
            '.webm': 'video/webm'
        }
        content_type = content_type_map.get(file_extension, 'video/mp4')
        
        # Clean filename
        project_name = project["name"]
        safe_filename = "".join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_filename}{filename_suffix}{file_extension}"
        
        return Response(
            content=video_data,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download video for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download video: {str(e)}")
