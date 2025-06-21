import os
import boto3
import logging
import ssl
import urllib3
import certifi
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config
from dotenv import load_dotenv
from typing import Optional
import time

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)

class R2Client:
    """
    Cloudflare R2 storage client using S3-compatible API.
    Provides reliable file upload/download with built-in retries.
    """
    
    def __init__(self):
        # R2 credentials from environment
        self.account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        self.access_key = os.environ.get("R2_ACCESS_KEY_ID") 
        self.secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
        self.bucket_name = os.environ.get("R2_BUCKET_NAME", "videos")
        
        if not all([self.account_id, self.access_key, self.secret_key]):
            raise EnvironmentError(
                "Missing R2 credentials. Please set CLOUDFLARE_ACCOUNT_ID, "
                "R2_ACCESS_KEY_ID, and R2_SECRET_ACCESS_KEY environment variables."
            )
        
        logger.info(f"R2 Configuration:")
        logger.info(f"  Account ID: {self.account_id}")
        logger.info(f"  Access Key: {self.access_key[:8]}...")
        logger.info(f"  Bucket: {self.bucket_name}")
        
        # R2 endpoint URL
        self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"
        
        # Configure boto3 client with optimized settings for large uploads
        config = Config(
            region_name='auto',  # R2 uses 'auto' region
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            max_pool_connections=50,
            # Timeouts in seconds
            connect_timeout=60,
            read_timeout=900,  # 15 minutes
            parameter_validation=False,
            tcp_keepalive=True,
            # Use S3v4 signature for better compatibility
            signature_version='s3v4'
        )
        
        # Create S3 client configured for R2
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=config,
            verify=certifi.where()  # Use proper certificate bundle for SSL verification
        )
        
        logger.info(f"Initialized R2 client for bucket '{self.bucket_name}' on account {self.account_id}")
    
    def upload_file(self, file_path: str, object_key: str, content_type: str = "application/octet-stream") -> dict:
        """
        Upload a file to R2 storage with automatic retry logic.
        
        Args:
            file_path: Local path to the file to upload
            object_key: Key/name for the object in R2 storage
            content_type: MIME type of the file
            
        Returns:
            dict: Upload result with success status and metadata
        """
        try:
            file_size = os.path.getsize(file_path)
            logger.info(f"Starting upload: {object_key} ({file_size} bytes)")
            
            start_time = time.time()
            
            # Upload with metadata
            extra_args = {
                'ContentType': content_type,
                'Metadata': {
                    'uploaded_at': str(int(time.time())),
                    'original_filename': os.path.basename(file_path)
                }
            }
            
            # Use multipart upload for files larger than 100MB
            if file_size > 100 * 1024 * 1024:
                logger.info(f"Using multipart upload for large file ({file_size // (1024*1024)}MB)")
                # boto3 automatically handles multipart uploads for large files
            
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                object_key,
                ExtraArgs=extra_args
            )
            
            upload_time = time.time() - start_time
            upload_speed = file_size / upload_time / (1024 * 1024)  # MB/s
            
            logger.info(f"Upload completed: {object_key} in {upload_time:.1f}s ({upload_speed:.1f} MB/s)")
            
            return {
                "success": True,
                "object_key": object_key,
                "file_size": file_size,
                "upload_time": upload_time,
                "upload_speed_mbps": upload_speed
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"R2 upload failed with code {error_code}: {str(e)}")
            raise Exception(f"R2 upload failed: {error_code} - {str(e)}")
        except NoCredentialsError:
            logger.error("R2 credentials not found or invalid")
            raise Exception("R2 credentials not found or invalid")
        except Exception as e:
            logger.error(f"Unexpected error during upload: {str(e)}")
            raise Exception(f"Upload failed: {str(e)}")
    
    def download_file(self, object_key: str, file_path: str) -> bool:
        """
        Download a file from R2 storage.
        
        Args:
            object_key: Key/name of the object in R2 storage
            file_path: Local path where the file should be saved
            
        Returns:
            bool: True if download succeeded
        """
        try:
            logger.info(f"Starting download: {object_key} to {file_path}")
            
            self.s3_client.download_file(
                self.bucket_name,
                object_key,
                file_path
            )
            
            logger.info(f"Download completed: {object_key}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.error(f"File not found in R2: {object_key}")
                raise Exception(f"File not found: {object_key}")
            else:
                logger.error(f"R2 download failed with code {error_code}: {str(e)}")
                raise Exception(f"R2 download failed: {error_code} - {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during download: {str(e)}")
            raise Exception(f"Download failed: {str(e)}")
    
    def delete_file(self, object_key: str) -> bool:
        """
        Delete a file from R2 storage.
        
        Args:
            object_key: Key/name of the object to delete
            
        Returns:
            bool: True if deletion succeeded
        """
        try:
            logger.info(f"Deleting file: {object_key}")
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            
            logger.info(f"File deleted: {object_key}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"R2 delete failed with code {error_code}: {str(e)}")
            # Don't raise exception for delete failures - just log and return False
            return False
        except Exception as e:
            logger.error(f"Unexpected error during delete: {str(e)}")
            return False
    
    def get_file_url(self, object_key: str, expires_in: int = 3600) -> str:
        """
        Generate a presigned URL for accessing a file.
        
        Args:
            object_key: Key/name of the object
            expires_in: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            str: Presigned URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_key},
                ExpiresIn=expires_in
            )
            
            logger.info(f"Generated presigned URL for {object_key} (expires in {expires_in}s)")
            return url
            
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            raise Exception(f"Failed to generate URL: {str(e)}")
    
    def file_exists(self, object_key: str) -> bool:
        """
        Check if a file exists in R2 storage.
        
        Args:
            object_key: Key/name of the object to check
            
        Returns:
            bool: True if file exists
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                # Re-raise other errors
                raise
    
    def get_file_info(self, object_key: str) -> Optional[dict]:
        """
        Get metadata information about a file.
        
        Args:
            object_key: Key/name of the object
            
        Returns:
            dict: File metadata or None if file doesn't exist
        """
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=object_key)
            
            return {
                "object_key": object_key,
                "size": response['ContentLength'],
                "last_modified": response['LastModified'],
                "content_type": response.get('ContentType', 'unknown'),
                "metadata": response.get('Metadata', {})
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            else:
                logger.error(f"Failed to get file info: {str(e)}")
                raise Exception(f"Failed to get file info: {str(e)}")
    
    def health_check(self) -> dict:
        """
        Check if R2 connection is healthy.
        
        Returns:
            dict: Health status
        """
        try:
            # Try to list objects to test connection
            self.s3_client.list_objects_v2(Bucket=self.bucket_name, MaxKeys=1)
            
            return {
                "status": "healthy",
                "service": "cloudflare_r2",
                "bucket": self.bucket_name,
                "endpoint": self.endpoint_url,
                "timestamp": time.time()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "service": "cloudflare_r2",
                "error": str(e),
                "bucket": self.bucket_name,
                "endpoint": self.endpoint_url,
                "timestamp": time.time()
            }
    
    def create_bucket_if_not_exists(self) -> bool:
        """
        Create the bucket if it doesn't exist.
        
        Returns:
            bool: True if bucket exists or was created successfully
        """
        try:
            # Check if bucket exists
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket '{self.bucket_name}' already exists")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.info(f"Bucket '{self.bucket_name}' does not exist, creating...")
                try:
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Successfully created bucket '{self.bucket_name}'")
                    return True
                except ClientError as create_error:
                    logger.error(f"Failed to create bucket: {create_error}")
                    return False
            else:
                logger.error(f"Error checking bucket: {e}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error checking bucket: {e}")
            return False

# Global R2 client instance (lazy-loaded)
_r2_client_instance = None

def get_r2_client():
    """Get or initialize the R2 client with lazy loading."""
    global _r2_client_instance
    
    if _r2_client_instance is None:
        try:
            _r2_client_instance = R2Client()
            logger.info("R2 client initialized successfully")
            
            # Test bucket access and create if needed
            if _r2_client_instance.create_bucket_if_not_exists():
                logger.info("R2 bucket access verified")
                # Test health
                health = _r2_client_instance.health_check()
                logger.info(f"R2 health check: {health['status']}")
                if health['status'] != 'healthy':
                    logger.warning(f"R2 health check warning: {health.get('error', 'Unknown issue')}")
            else:
                logger.error("Failed to verify or create R2 bucket")
                _r2_client_instance = None
                
        except Exception as e:
            logger.error(f"Failed to initialize R2 client: {e}")
            _r2_client_instance = None
    
    return _r2_client_instance

# For backward compatibility
r2_client = get_r2_client()