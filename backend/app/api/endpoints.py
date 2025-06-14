from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from app.tasks.transcription import transcribe_video_task
from app.services.supabase_client import supabase
import logging

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
        }).select("id").single().execute()
        
        job_id = job_response.data.get("id")
        if not job_id:
            raise HTTPException(status_code=500, detail="Failed to create processing job.")

        # 3. Queue the background task
        transcribe_video_task.delay(project_id)
        logger.info(f"Queued transcription task for project_id: {project_id}, job_id: {job_id}")

        return {"message": "Transcription task started", "job_id": job_id}

    except Exception as e:
        logger.error(f"Failed to start transcription for project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start transcription task: {str(e)}")
