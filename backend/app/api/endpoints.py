from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import Response
from pydantic import BaseModel
from app.schemas.transcription import TranscriptionRequest
from app.tasks.transcription import transcribe_video_task
from app.services.supabase_client import supabase
import logging
import uuid
import os

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

@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    project_name: str = Form(...)
):
    """Upload a video file and create a new project."""
    try:
        # Validate file type
        allowed_extensions = {'.mp4', '.mov', '.avi', '.webm'}
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        storage_filename = f"{file_id}{file_extension}"
        
        # Read file content
        file_content = await file.read()
        
        # Upload to Supabase Storage
        storage_response = supabase.storage.from_("videos").upload(
            storage_filename, 
            file_content,
            file_options={"content-type": file.content_type}
        )
        
        if hasattr(storage_response, 'error') and storage_response.error:
            raise HTTPException(status_code=500, detail=f"Failed to upload file: {storage_response.error}")
        
        # Create project record
        # For now, using a dummy user_id - will integrate auth later
        dummy_user_id = "00000000-0000-0000-0000-000000000001"
        
        project_response = supabase.table("projects").insert({
            "user_id": dummy_user_id,
            "name": project_name,
            "video_path": storage_filename,
            "status": "uploaded"
        }).execute()
        
        if not project_response.data or len(project_response.data) == 0:
            raise HTTPException(status_code=500, detail="Failed to create project record.")
        
        project = project_response.data[0]
        logger.info(f"Created project {project['id']} with video {storage_filename}")
        
        return {
            "message": "Video uploaded successfully",
            "project_id": project["id"],
            "project_name": project["name"],
            "video_path": storage_filename,
            "status": project["status"]
        }
        
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

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
