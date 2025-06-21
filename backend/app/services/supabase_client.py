# backend/app/services/optimized_supabase_client.py
import os
from supabase import create_client, Client
from dotenv import load_dotenv
import httpx
import asyncio
from typing import Optional
import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)

# Force reload environment variables
load_dotenv(override=True)

def retry_on_failure(max_retries=3, delay=1, backoff=2):
    """Decorator for retrying failed operations with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Operation failed after {max_retries} retries: {str(e)}")
                        raise e
                    
                    wait_time = delay * (backoff ** (retries - 1))
                    logger.warning(f"Operation failed, retrying in {wait_time}s (attempt {retries}/{max_retries}): {str(e)}")
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator

class OptimizedSupabaseClient:
    """
    Optimized Supabase client with better error handling, connection pooling,
    and timeout management for large file operations.
    """
    
    def __init__(self):
        self.url = "https://ghkowjxqwxsikrdivwxl.supabase.co"
        self.key = os.environ.get("SUPABASE_ANON_KEY")
        
        if not self.url or not self.key:
            raise EnvironmentError("Supabase URL and Key must be set")
        
        # Configure HTTP client with optimized settings for large uploads
        self.http_client = httpx.Client(
            timeout=httpx.Timeout(
                connect=60.0,      # 60 seconds to establish connection
                read=1200.0,       # 20 minutes for read operations
                write=1200.0,      # 20 minutes for write operations
                pool=60.0          # 60 seconds for connection pool
            ),
            limits=httpx.Limits(
                max_keepalive_connections=50,  # Increased from 20
                max_connections=200,           # Increased from 100
                keepalive_expiry=60.0          # Increased from 30.0
            ),
            http2=False,  # Disable HTTP/2 which can cause issues with large uploads
            follow_redirects=True,  # Follow redirects
            max_redirects=5,        # Maximum number of redirects to follow
            verify=True,           # Verify SSL certificates
            trust_env=False        # Don't read proxy settings from environment
        )
        
        # Configure retry strategy
        self.max_retries = 5
        self.retry_delay = 5  # Initial delay in seconds
        self.max_retry_delay = 60  # Maximum delay in seconds
        
        # Create Supabase client
        self.client = create_client(self.url, self.key)
        
        # Override the internal HTTP client
        self.client._session = self.http_client
        
        logger.info(f"Initialized optimized Supabase client for {self.url}")
    
    @retry_on_failure(max_retries=3)
    def upload_file_chunk(self, bucket: str, path: str, file_data: bytes, 
                         content_type: str = "application/octet-stream") -> dict:
        """Upload a file chunk with retry logic."""
        try:
            response = self.client.storage.from_(bucket).upload(
                path, 
                file_data,
                file_options={
                    "content-type": content_type,
                    "x-upsert": "true",
                    "cache-control": "3600"
                }
            )
            
            if hasattr(response, 'error') and response.error:
                raise Exception(f"Upload failed: {response.error}")
            
            return {"success": True, "path": path}
            
        except Exception as e:
            logger.error(f"Failed to upload chunk to {bucket}/{path}: {str(e)}")
            raise
    
    @retry_on_failure(max_retries=3)
    def download_file(self, bucket: str, path: str) -> bytes:
        """Download a file with retry logic."""
        try:
            file_data = self.client.storage.from_(bucket).download(path)
            return file_data
        except Exception as e:
            logger.error(f"Failed to download {bucket}/{path}: {str(e)}")
            raise
    
    @retry_on_failure(max_retries=3)
    def insert_record(self, table: str, data: dict) -> dict:
        """Insert a record with retry logic."""
        try:
            response = self.client.table(table).insert(data).execute()
            if not response.data:
                raise Exception("Insert returned no data")
            return response.data[0]
        except Exception as e:
            logger.error(f"Failed to insert into {table}: {str(e)}")
            raise
    
    @retry_on_failure(max_retries=3)
    def update_record(self, table: str, data: dict, conditions: dict) -> dict:
        """Update a record with retry logic."""
        try:
            query = self.client.table(table).update(data)
            for key, value in conditions.items():
                query = query.eq(key, value)
            
            response = query.execute()
            if not response.data:
                raise Exception("Update returned no data")
            return response.data[0]
        except Exception as e:
            logger.error(f"Failed to update {table}: {str(e)}")
            raise
    
    @retry_on_failure(max_retries=3)
    def select_records(self, table: str, columns: str = "*", conditions: dict = None) -> list:
        """Select records with retry logic."""
        try:
            query = self.client.table(table).select(columns)
            
            if conditions:
                for key, value in conditions.items():
                    query = query.eq(key, value)
            
            response = query.execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to select from {table}: {str(e)}")
            raise
    
    @retry_on_failure(max_retries=3)
    def delete_record(self, table: str, conditions: dict) -> bool:
        """Delete a record with retry logic."""
        try:
            query = self.client.table(table).delete()
            for key, value in conditions.items():
                query = query.eq(key, value)
            
            response = query.execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete from {table}: {str(e)}")
            raise
    
    @retry_on_failure(max_retries=3)
    def delete_file(self, bucket: str, path: str) -> bool:
        """Delete a file with retry logic."""
        try:
            response = self.client.storage.from_(bucket).remove([path])
            return True
        except Exception as e:
            logger.error(f"Failed to delete {bucket}/{path}: {str(e)}")
            # Don't raise for file deletion failures
            return False
    
    def get_file_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        """Get a signed URL for a file."""
        try:
            response = self.client.storage.from_(bucket).create_signed_url(path, expires_in)
            if 'error' in response:
                raise Exception(f"Failed to create signed URL: {response['error']}")
            return response['signedURL']
        except Exception as e:
            logger.error(f"Failed to get URL for {bucket}/{path}: {str(e)}")
            raise
    
    def health_check(self) -> dict:
        """Check if the Supabase connection is healthy."""
        try:
            # Try a simple query to check connectivity
            response = self.client.table("projects").select("id").limit(1).execute()
            
            return {
                "status": "healthy",
                "url": self.url,
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "url": self.url,
                "timestamp": time.time()
            }
    
    def __del__(self):
        """Clean up HTTP client on destruction."""
        try:
            if hasattr(self, 'http_client'):
                self.http_client.close()
        except:
            pass

# Create optimized client instance
optimized_supabase = OptimizedSupabaseClient()

# Backward compatibility - expose the client
supabase = optimized_supabase.client

# Health check endpoint for monitoring
def get_supabase_health():
    return optimized_supabase.health_check()

# Utility functions using the optimized client
async def upload_large_file(bucket: str, file_path: str, file_data: bytes, 
                           content_type: str, chunk_size: int = 5 * 1024 * 1024) -> bool:
    """
    Upload a large file in chunks for better reliability.
    """
    try:
        total_size = len(file_data)
        
        if total_size <= chunk_size:
            # File is small enough to upload in one piece
            optimized_supabase.upload_file_chunk(bucket, file_path, file_data, content_type)
            return True
        
        # For large files, we could implement multipart upload here
        # For now, just upload as single file with retries
        optimized_supabase.upload_file_chunk(bucket, file_path, file_data, content_type)
        return True
        
    except Exception as e:
        logger.error(f"Failed to upload large file {file_path}: {str(e)}")
        return False

# Connection pool monitoring
def get_connection_stats():
    """Get HTTP connection pool statistics."""
    if hasattr(optimized_supabase, 'http_client'):
        return {
            "pool_connections": len(optimized_supabase.http_client._pool._pool),
            "active_connections": optimized_supabase.http_client._pool._pool_size,
        }
    return {"error": "HTTP client not available"}