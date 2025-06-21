# backend/app/api/chunked_upload.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import tempfile
import os
import json
import uuid
from pathlib import Path
from typing import List, Optional
import asyncio
from app.services.supabase_client import supabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory store for active uploads (use Redis in production)
active_uploads = {}

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

@router.post("/upload/init")
async def initialize_upload(request: UploadInitRequest):
    """Initialize a chunked upload session."""
    try:
        # Validate file type
        allowed_types = {'video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm'}
        if request.fileType not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {request.fileType}"
            )
        
        # Check file size (2GB limit)
        max_size = 2 * 1024 * 1024 * 1024  # 2GB
        if request.fileSize > max_size:
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum size is 2GB"
            )
        
        # Create project record
        dummy_user_id = "00000000-0000-0000-0000-000000000001"
        
        project_response = supabase.table("projects").insert({
            "user_id": dummy_user_id,
            "name": request.projectName,
            "status": "uploading"
        }).execute()
        
        if not project_response.data:
            raise HTTPException(status_code=500, detail="Failed to create project")
        
        project_id = project_response.data[0]["id"]
        
        # Store upload session info
        active_uploads[request.uploadId] = {
            "project_id": project_id,
            "file_name": request.fileName,
            "file_size": request.fileSize,
            "file_type": request.fileType,
            "total_chunks": request.totalChunks,
            "uploaded_chunks": {},
            "temp_dir": None
        }
        
        logger.info(f"Initialized upload {request.uploadId} for project {project_id}")
        
        return {
            "uploadId": request.uploadId,
            "projectId": project_id,
            "message": "Upload initialized successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to initialize upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload initialization failed: {str(e)}")

@router.post("/upload/chunk")
async def upload_chunk(
    chunk: UploadFile = File(...),
    metadata: str = Form(...)
):
    """Upload a single chunk of the file."""
    try:
        # Parse metadata
        chunk_meta = ChunkMetadata(**json.loads(metadata))
        
        # Verify upload session exists
        if chunk_meta.uploadId not in active_uploads:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        upload_session = active_uploads[chunk_meta.uploadId]
        
        # Create temp directory if not exists
        if upload_session["temp_dir"] is None:
            temp_dir = tempfile.mkdtemp(prefix=f"upload_{chunk_meta.uploadId}_")
            upload_session["temp_dir"] = temp_dir
            logger.info(f"Created temp directory: {temp_dir}")
        
        # Save chunk to temporary file
        chunk_path = os.path.join(
            upload_session["temp_dir"], 
            f"chunk_{chunk_meta.chunkIndex:06d}"
        )
        
        with open(chunk_path, "wb") as f:
            content = await chunk.read()
            f.write(content)
        
        # Generate ETag for chunk (simple hash of chunk index for demo)
        etag = f"chunk-{chunk_meta.chunkIndex}-{len(content)}"
        
        # Store chunk info
        upload_session["uploaded_chunks"][chunk_meta.chunkIndex] = {
            "path": chunk_path,
            "size": len(content),
            "etag": etag
        }
        
        logger.info(f"Uploaded chunk {chunk_meta.chunkIndex}/{chunk_meta.totalChunks} for upload {chunk_meta.uploadId}")
        
        return {
            "chunkIndex": chunk_meta.chunkIndex,
            "etag": etag,
            "message": "Chunk uploaded successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to upload chunk: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chunk upload failed: {str(e)}")

@router.post("/upload/complete")
async def complete_upload(request: UploadCompleteRequest):
    """Complete the chunked upload by assembling all chunks."""
    try:
        # Verify upload session exists
        if request.uploadId not in active_uploads:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        upload_session = active_uploads[request.uploadId]
        project_id = request.projectId
        
        # Verify all chunks are uploaded
        expected_chunks = upload_session["total_chunks"]
        uploaded_chunks = upload_session["uploaded_chunks"]
        
        if len(uploaded_chunks) != expected_chunks:
            raise HTTPException(
                status_code=400,
                detail=f"Missing chunks. Expected {expected_chunks}, got {len(uploaded_chunks)}"
            )
        
        # Assemble file from chunks
        file_extension = os.path.splitext(upload_session["file_name"])[1]
        final_filename = f"{project_id}{file_extension}"
        
        # Create temporary assembled file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_final_path = temp_file.name
            
            # Write chunks in order
            for chunk_index in range(expected_chunks):
                if chunk_index not in uploaded_chunks:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Missing chunk {chunk_index}"
                    )
                
                chunk_info = uploaded_chunks[chunk_index]
                with open(chunk_info["path"], "rb") as chunk_file:
                    temp_file.write(chunk_file.read())
        
        # Upload assembled file to Supabase Storage
        with open(temp_final_path, "rb") as final_file:
            file_data = final_file.read()
            
            storage_response = supabase.storage.from_("videos").upload(
                final_filename,
                file_data,
                file_options={"content-type": upload_session["file_type"]}
            )
            
            if hasattr(storage_response, 'error') and storage_response.error:
                raise Exception(f"Storage upload failed: {storage_response.error}")
        
        # Update project with video path
        supabase.table("projects").update({
            "video_path": final_filename,
            "status": "uploaded"
        }).eq("id", project_id).execute()
        
        # Cleanup temporary files
        cleanup_upload_session(request.uploadId)
        
        # Remove from active uploads
        del active_uploads[request.uploadId]
        
        logger.info(f"Completed upload {request.uploadId} for project {project_id}")
        
        return {
            "projectId": project_id,
            "fileName": final_filename,
            "message": "Upload completed successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to complete upload: {str(e)}")
        # Cleanup on error
        if request.uploadId in active_uploads:
            cleanup_upload_session(request.uploadId)
            del active_uploads[request.uploadId]
        raise HTTPException(status_code=500, detail=f"Upload completion failed: {str(e)}")

def cleanup_upload_session(upload_id: str):
    """Clean up temporary files for an upload session."""
    if upload_id not in active_uploads:
        return
    
    upload_session = active_uploads[upload_id]
    temp_dir = upload_session.get("temp_dir")
    
    if temp_dir and os.path.exists(temp_dir):
        try:
            import shutil
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temp directory: {temp_dir}")
        except Exception as e: