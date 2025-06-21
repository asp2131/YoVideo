from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import Response
from pydantic import BaseModel
from app.schemas.transcription import TranscriptionRequest
from app.tasks.transcription import transcribe_video_task
from app.services.supabase_client import supabase
from app.services.r2_client import get_r2_client
import logging
import uuid
import os
import tempfile
import asyncio
import json
from pathlib import Path
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define upload directory
UPLOAD_TEMP_DIR = Path(__file__).parent.parent / "temp_uploads"
UPLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"Using upload temp directory: {UPLOAD_TEMP_DIR}")

router = APIRouter()

class TranscriptionRequest(BaseModel):
    project_id: str

class UploadInitRequest(BaseModel):
    fileName: str
    fileSize: int
    fileType: str
    projectName: str
    totalChunks: int
    uploadId: str

class ChunkMetadata(BaseModel):
    chunkIndex: int
    chunkSize: int
    totalChunks: int
    totalSize: int
    fileName: str
    fileType: str
    uploadId: str
    projectId: str

class UploadCompleteRequest(BaseModel):
    uploadId: str
    projectId: str
    chunks: List[str]

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

# In-memory storage for upload sessions
upload_sessions: Dict[str, Dict] = {}

class UploadSession:
    def __init__(self, upload_id: str, project_id: str, file_name: str, file_size: int, 
                 file_type: str, total_chunks: int, temp_dir: str):
        self.upload_id = upload_id
        self.project_id = project_id
        self.file_name = file_name
        self.file_size = file_size
        self.file_type = file_type
        self.total_chunks = total_chunks
        self.temp_dir = temp_dir
        self.uploaded_chunks: Dict[int, str] = {}  # chunk_index -> file_path
        self.completed = False
        
    def add_chunk(self, chunk_index: int, file_path: str):
        self.uploaded_chunks[chunk_index] = file_path
        
    def is_complete(self) -> bool:
        return len(self.uploaded_chunks) == self.total_chunks
        
    def get_chunk_paths(self) -> List[str]:
        """Get chunk file paths in order"""
        paths = []
        for i in range(self.total_chunks):
            if i in self.uploaded_chunks:
                paths.append(self.uploaded_chunks[i])
            else:
                raise ValueError(f"Missing chunk {i}")
        return paths

async def upload_to_r2_with_timeout(file_path: str, storage_filename: str, content_type: str, timeout: int = 300):
    """Upload file to Cloudflare R2 with timeout handling."""
    def sync_upload():
        client = get_r2_client()
        if client is None:
            raise Exception("Failed to initialize R2 client. Check R2 credentials.")
        return client.upload_file(file_path, storage_filename, content_type)
    
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
                        
                        # Upload to R2 with timeout
                        logger.info(f"Starting R2 upload for file: {storage_filename} ({total_size} bytes)")
                        storage_response = await upload_to_r2_with_timeout(
                            temp_file_path, 
                            storage_filename, 
                            content_type,
                            timeout=600  # 10 minutes for R2
                        )
                        logger.info(f"R2 upload response: {storage_response}")
                            
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
                    "video_path": storage_filename,
                    "file_size": total_size,
                    "status": "uploaded"
                }
                
                db_response = supabase.table("projects").insert(project_data).execute()
                
                if not db_response.data:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to create project record in database"
                    )
                
                # Automatically start transcription task
                try:
                    task = transcribe_video_task.delay(file_id)
                    logger.info(f"Started transcription task {task.id} for project {file_id}")
                except Exception as e:
                    logger.error(f"Failed to start transcription task for project {file_id}: {e}", exc_info=True)
                
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

@router.post("/upload/init")
async def init_chunked_upload(request: UploadInitRequest):
    """
    Initialize a chunked upload session.
    Creates a project record and sets up temporary storage for chunks.
    """
    try:
        # Validate file type
        allowed_extensions = {'.mp4', '.mov', '.avi', '.webm', '.mkv'}
        file_extension = os.path.splitext(request.fileName)[1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Generate unique project ID
        project_id = str(uuid.uuid4())
        
        # Create temporary directory for this upload session
        temp_dir = UPLOAD_TEMP_DIR / f"upload_{request.uploadId}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = str(temp_dir)  # Convert to string for compatibility
        
        # Create upload session
        session = UploadSession(
            upload_id=request.uploadId,
            project_id=project_id,
            file_name=request.fileName,
            file_size=request.fileSize,
            file_type=request.fileType,
            total_chunks=request.totalChunks,
            temp_dir=temp_dir
        )
        
        # Store session
        upload_sessions[request.uploadId] = session
        
        # Create project record in database
        project_data = {
            "id": project_id,
            "user_id": "00000000-0000-0000-0000-000000000001",  # Default user ID
            "name": request.projectName,
            "original_filename": request.fileName,
            "video_path": "",  # Will be set when upload completes
            "file_size": request.fileSize,
            "status": "uploading"
        }
        
        db_response = supabase.table("projects").insert(project_data).execute()
        
        if not db_response.data:
            # Clean up temp directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            del upload_sessions[request.uploadId]
            raise HTTPException(
                status_code=500,
                detail="Failed to create project record in database"
            )
        
        logger.info(f"Initialized chunked upload for project {project_id}: {request.fileName} ({request.fileSize} bytes, {request.totalChunks} chunks)")
        
        return {
            "projectId": project_id,
            "uploadId": request.uploadId,
            "message": "Upload session initialized"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initialize chunked upload: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize upload: {str(e)}"
        )

@router.post("/upload/chunk")
async def upload_chunk(
    chunk: UploadFile = File(...),
    metadata: str = Form(...)
):
    """
    Upload a single chunk of a file.
    """
    try:
        # Parse metadata
        chunk_metadata = ChunkMetadata.model_validate_json(metadata)
        
        # Get upload session
        if chunk_metadata.uploadId not in upload_sessions:
            raise HTTPException(
                status_code=404,
                detail="Upload session not found"
            )
        
        session = upload_sessions[chunk_metadata.uploadId]
        
        # Validate chunk index
        if chunk_metadata.chunkIndex >= session.total_chunks:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid chunk index {chunk_metadata.chunkIndex}"
            )
        
        # Save chunk to temporary file
        chunk_filename = f"chunk_{chunk_metadata.chunkIndex:06d}"
        chunk_path = os.path.join(session.temp_dir, chunk_filename)
        
        with open(chunk_path, "wb") as f:
            chunk_content = await chunk.read()
            f.write(chunk_content)
        
        # Add chunk to session
        session.add_chunk(chunk_metadata.chunkIndex, chunk_path)
        
        logger.info(f"Uploaded chunk {chunk_metadata.chunkIndex + 1}/{session.total_chunks} for upload {chunk_metadata.uploadId}")
        
        return {
            "chunkIndex": chunk_metadata.chunkIndex,
            "etag": f"chunk_{chunk_metadata.chunkIndex}",
            "uploaded": len(session.uploaded_chunks),
            "total": session.total_chunks,
            "message": f"Chunk {chunk_metadata.chunkIndex} uploaded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload chunk: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload chunk: {str(e)}"
        )

@router.post("/upload/complete")
async def complete_chunked_upload(request: UploadCompleteRequest):
    """
    Complete a chunked upload by assembling chunks and uploading to Supabase.
    """
    try:
        # Get upload session
        if request.uploadId not in upload_sessions:
            raise HTTPException(
                status_code=404,
                detail="Upload session not found"
            )
        
        session = upload_sessions[request.uploadId]
        
        # Check if all chunks are uploaded
        if not session.is_complete():
            raise HTTPException(
                status_code=400,
                detail=f"Missing chunks. Have {len(session.uploaded_chunks)}/{session.total_chunks}"
            )
        
        # Assemble chunks into final file
        final_file_path = os.path.join(session.temp_dir, "assembled_file")
        
        try:
            with open(final_file_path, "wb") as final_file:
                chunk_paths = session.get_chunk_paths()
                total_written = 0
                
                for i, chunk_path in enumerate(chunk_paths):
                    with open(chunk_path, "rb") as chunk_file:
                        chunk_data = chunk_file.read()
                        final_file.write(chunk_data)
                        total_written += len(chunk_data)
                        logger.debug(f"Assembled chunk {i}: {len(chunk_data)} bytes")
            
            logger.info(f"Assembled {len(chunk_paths)} chunks into {total_written} bytes for upload {request.uploadId}")
            
            # Verify file size
            if total_written != session.file_size:
                raise Exception(f"File size mismatch: expected {session.file_size}, got {total_written}")
            
            # Generate storage filename
            file_extension = os.path.splitext(session.file_name)[1].lower()
            storage_filename = f"{session.project_id}{file_extension}"
            
            # Map file extensions to MIME types
            mime_map = {
                '.mp4': 'video/mp4',
                '.mov': 'video/quicktime',
                '.avi': 'video/x-msvideo',
                '.webm': 'video/webm',
                '.mkv': 'video/x-matroska'
            }
            content_type = mime_map.get(file_extension.lower(), 'application/octet-stream')
            
            # Upload to Cloudflare R2 with extended timeout for large files
            logger.info(f"Starting R2 upload for assembled file: {storage_filename} ({total_written} bytes)")
            
            # R2 is much more reliable, use generous timeout for large files
            timeout_minutes = max(10, total_written // (1024 * 1024 * 2))  # 2MB per minute (very conservative)
            timeout_seconds = min(timeout_minutes * 60, 1800)  # Cap at 30 minutes
            
            logger.info(f"Using {timeout_seconds // 60} minute timeout for {total_written // (1024 * 1024)}MB file")
            
            try:
                storage_response = await upload_to_r2_with_timeout(
                    final_file_path,
                    storage_filename,
                    content_type,
                    timeout=timeout_seconds
                )
                logger.info(f"R2 upload completed successfully: {storage_response}")
                
            except asyncio.TimeoutError:
                logger.error(f"Upload timed out after {timeout_seconds} seconds")
                raise HTTPException(
                    status_code=408,
                    detail=f"File upload timed out. This is unusual for R2 - please check your connection."
                )
            except Exception as upload_error:
                logger.error(f"R2 upload failed: {str(upload_error)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload file to R2 storage: {str(upload_error)}"
                )
            
            # Update project record with video path
            update_data = {
                "video_path": storage_filename,
                "status": "uploaded"
            }
            
            db_response = supabase.table("projects").update(update_data).eq("id", session.project_id).execute()
            
            if not db_response.data:
                raise Exception("Failed to update project record")
            
            # Mark session as completed
            session.completed = True
            
            logger.info(f"Completed chunked upload for project {session.project_id}: {storage_filename}")
            
            # Automatically start transcription task
            try:
                task = transcribe_video_task.delay(session.project_id)
                logger.info(f"Started transcription task {task.id} for project {session.project_id}")
            except Exception as e:
                logger.error(f"Failed to start transcription task for project {session.project_id}: {e}", exc_info=True)
            
            return {
                "projectId": session.project_id,
                "filename": storage_filename,
                "status": "uploaded",
                "message": "Upload completed successfully - transcription started"
            }
            
        finally:
            # Clean up temporary files
            try:
                import shutil
                shutil.rmtree(session.temp_dir, ignore_errors=True)
                del upload_sessions[request.uploadId]
                logger.info(f"Cleaned up upload session {request.uploadId}")
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up upload session: {str(cleanup_error)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete chunked upload: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete upload: {str(e)}"
        )

@router.get("/upload/{upload_id}/status")
async def get_upload_status(upload_id: str):
    """
    Get the status of a chunked upload session.
    """
    if upload_id not in upload_sessions:
        raise HTTPException(
            status_code=404,
            detail="Upload session not found"
        )
    
    session = upload_sessions[upload_id]
    
    return {
        "uploadId": upload_id,
        "projectId": session.project_id,
        "fileName": session.file_name,
        "fileSize": session.file_size,
        "totalChunks": session.total_chunks,
        "uploadedChunks": len(session.uploaded_chunks),
        "completed": session.completed,
        "isComplete": session.is_complete(),
        "progress": (len(session.uploaded_chunks) / session.total_chunks) * 100
    }

@router.delete("/upload/{upload_id}")
async def cancel_chunked_upload(upload_id: str):
    """
    Cancel a chunked upload and clean up resources.
    """
    try:
        if upload_id not in upload_sessions:
            raise HTTPException(
                status_code=404,
                detail="Upload session not found"
            )
        
        session = upload_sessions[upload_id]
        
        # Clean up temporary files
        try:
            import shutil
            shutil.rmtree(session.temp_dir, ignore_errors=True)
        except Exception as cleanup_error:
            logger.error(f"Error cleaning up temp directory: {str(cleanup_error)}")
        
        # Remove project from database if not completed
        if not session.completed:
            try:
                supabase.table("projects").delete().eq("id", session.project_id).execute()
            except Exception as db_error:
                logger.error(f"Error removing project from database: {str(db_error)}")
        
        # Remove session
        del upload_sessions[upload_id]
        
        logger.info(f"Cancelled upload session {upload_id}")
        
        return {"message": "Upload cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel upload: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel upload: {str(e)}"
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
        
        try:
            # Download from R2 Storage
            client = get_r2_client()
            if client is None:
                raise HTTPException(status_code=503, detail="Failed to initialize R2 storage client")
                
            # Generate a presigned URL for download
            download_url = client.get_file_url(video_path, expires_in=3600)
                
            # Return redirect to presigned URL for direct download
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=download_url, status_code=302)
        except Exception as e:
            logger.error(f"Failed to generate download URL for {video_path}: {str(e)}")
            raise HTTPException(status_code=404, detail="Video file not found or cannot be accessed")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download video for project {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download video: {str(e)}")
