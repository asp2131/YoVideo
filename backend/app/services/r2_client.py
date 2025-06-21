import os
import boto3
import logging
import ssl
import urllib3
import certifi
import socket
from botocore.exceptions import ClientError, NoCredentialsError, SSLError, EndpointConnectionError
from botocore.config import Config
from dotenv import load_dotenv
from typing import Optional, Dict, Any
import time
from functools import wraps
import random

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
        
        # Debug: Print all environment variables for troubleshooting
        logger.debug("Environment variables:")
        for key, value in os.environ.items():
            if key.startswith(('CLOUDFLARE_', 'R2_')):
                safe_value = f"{value[:3]}...{value[-3:]}" if value and len(value) > 6 else "[empty]"
                logger.debug(f"  {key}: {safe_value}")
        
        # Check for missing credentials with more detailed error message
        missing = []
        if not self.account_id:
            missing.append("CLOUDFLARE_ACCOUNT_ID")
        if not self.access_key:
            missing.append("R2_ACCESS_KEY_ID")
        if not self.secret_key:
            missing.append("R2_SECRET_ACCESS_KEY")
            
        if missing:
            error_msg = f"Missing required R2 credentials: {', '.join(missing)}. " \
                      f"Please check your .env file or environment variables."
            logger.error(error_msg)
            raise EnvironmentError(error_msg)
        
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
                'max_attempts': 5,  # Total number of retry attempts
                'mode': 'adaptive'  # Use adaptive retry mode
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
        
        # Set SSL verification using certifi's CA bundle
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
        os.environ['SSL_CERT_FILE'] = certifi.where()
        
        # Create session with custom configuration
        session = boto3.Session(
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key
        )
        
        # Create S3 client with the session and config
        self.s3_client = session.client(
            's3',
            endpoint_url=self.endpoint_url,
            config=config,
            verify=True  # Enable SSL verification
        )
        
        logger.info("R2 client initialized with SSL verification enabled")
        
        logger.info(f"Initialized R2 client for bucket '{self.bucket_name}' on account {self.account_id}")
    
    def upload_file(self, file_path: str, object_key: str, content_type: str) -> dict:
        """
        Upload a file to R2 storage with retries and error handling.
        
        Args:
            file_path: Path to the local file to upload
            object_key: S3 object key (path in the bucket)
            content_type: MIME type of the file
            
        Returns:
            dict: Upload result with success status and metadata
        """
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(1, max_retries + 1):
            try:
                file_size = os.path.getsize(file_path)
                logger.info(f"Upload attempt {attempt}/{max_retries}: {object_key} ({file_size} bytes)")
                
                start_time = time.time()
                
                # Upload with metadata
                extra_args = {
                    'ContentType': content_type,
                    'Metadata': {
                        'uploaded_at': str(int(time.time())),
                        'original_filename': os.path.basename(file_path),
                        'upload_attempt': str(attempt)
                    }
                }
                
                # Use multipart upload for files larger than 20MB
                if file_size > 20 * 1024 * 1024:
                    logger.info(f"Using multipart upload for large file ({file_size // (1024*1024)}MB)")
                    return self._multipart_upload(file_path, object_key, extra_args)
                
                # For smaller files, use regular upload
                with open(file_path, 'rb') as file_data:
                    self.s3_client.upload_fileobj(
                        file_data,
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
                
            except (SSLError, EndpointConnectionError, socket.gaierror) as e:
                if attempt == max_retries:
                    logger.error(f"SSL/Connection error on final attempt {attempt}: {str(e)}")
                    raise Exception(f"Upload failed after {max_retries} attempts due to SSL/connection error: {str(e)}")
                
                # Exponential backoff with jitter
                delay = retry_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                logger.warning(f"SSL/Connection error (attempt {attempt}/{max_retries}), retrying in {delay:.1f}s: {str(e)}")
                time.sleep(delay)
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                if attempt == max_retries:
                    logger.error(f"R2 upload failed with code {error_code} on final attempt: {str(e)}")
                    raise Exception(f"R2 upload failed: {error_code} - {str(e)}")
                
                delay = retry_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                logger.warning(f"R2 error (attempt {attempt}/{max_retries}), retrying in {delay:.1f}s: {error_code} - {str(e)}")
                time.sleep(delay)
                
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"Unexpected error on final attempt: {str(e)}")
                    raise Exception(f"Upload failed after {max_retries} attempts: {str(e)}")
                
                delay = retry_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                logger.warning(f"Unexpected error (attempt {attempt}/{max_retries}), retrying in {delay:.1f}s: {str(e)}")
                time.sleep(delay)
    
    def _multipart_upload(self, file_path: str, object_key: str, extra_args: dict) -> dict:
        """
        Upload a large file to R2 using multipart upload.
        
        Args:
            file_path: Path to the local file to upload
            object_key: S3 object key (path in the bucket)
            extra_args: Additional arguments for the upload
            
        Returns:
            dict: Upload result with success status and metadata
        """
        try:
            file_size = os.path.getsize(file_path)
            logger.info(f"Starting multipart upload for {object_key} ({file_size} bytes)")
            
            # Create multipart upload
            mpu = self.s3_client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=object_key,
                **{k: v for k, v in extra_args.items() if k != 'Metadata'}
            )
            upload_id = mpu['UploadId']
            
            # Upload parts
            part_size = 8 * 1024 * 1024  # 8MB parts
            parts = []
            
            with open(file_path, 'rb') as file_obj:
                part_number = 1
                while True:
                    data = file_obj.read(part_size)
                    if not data:
                        break
                        
                    logger.debug(f"Uploading part {part_number} for {object_key}")
                    
                    # Retry logic for each part
                    for attempt in range(3):
                        try:
                            part = self.s3_client.upload_part(
                                Bucket=self.bucket_name,
                                Key=object_key,
                                PartNumber=part_number,
                                UploadId=upload_id,
                                Body=data
                            )
                            parts.append({
                                'PartNumber': part_number,
                                'ETag': part['ETag']
                            })
                            break
                        except Exception as e:
                            if attempt == 2:  # Last attempt
                                raise
                            logger.warning(f"Part {part_number} upload failed (attempt {attempt + 1}/3): {str(e)}")
                            time.sleep(2 ** attempt)  # Exponential backoff
                    
                    part_number += 1
            
            # Complete multipart upload
            result = self.s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=object_key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            
            logger.info(f"Multipart upload completed: {object_key}")
            return {
                "success": True,
                "object_key": object_key,
                "file_size": file_size,
                "upload_id": upload_id
            }
            
        except Exception as e:
            # Abort the upload if anything goes wrong
            try:
                if 'upload_id' in locals():
                    self.s3_client.abort_multipart_upload(
                        Bucket=self.bucket_name,
                        Key=object_key,
                        UploadId=upload_id
                    )
            except Exception as abort_error:
                logger.error(f"Error aborting multipart upload: {str(abort_error)}")
                
            logger.error(f"Multipart upload failed: {str(e)}")
            raise Exception(f"Multipart upload failed: {str(e)}")
    
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