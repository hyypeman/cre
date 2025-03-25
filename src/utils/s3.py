import os
import logging
import boto3
from botocore.exceptions import ClientError
from pathlib import Path
from typing import List, Optional, Union, BinaryIO, Dict, Any

logger = logging.getLogger(__name__)

# Initialize the S3 client
try:
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name=os.environ.get('AWS_REGION', 'us-west-1')
    )
except Exception as e:
    logger.error(f"Failed to initialize S3 client: {str(e)}")
    s3_client = None


def upload_file(
    file_name: str, 
    bucket: str, 
    object_name: str,
) -> bool:
    """
    Upload a file to an S3 bucket.
    
    Args:
        file_path: File to upload
        bucket: Bucket to upload to
        object_name: S3 object name. If not specified, file_name will be used
        extra_args: Optional extra arguments that may be passed to the client operation
        
    Returns:
        True if file was uploaded, else False
    """
    if s3_client is None:
        logger.error("S3 client is not initialized")
        return False
    
    try:
        s3_client.upload_file(file_name, bucket, object_name,)
        logger.info(f"Successfully uploaded {file_name} to {bucket}/{object_name}")
        return True
    except ClientError as e:
        logger.error(f"Error uploading file to S3: {e}")
        return False


def upload_fileobj(
    file_obj: BinaryIO,
    bucket: str,
    object_name: str,
) -> bool:
    """
    Upload a file-like object to an S3 bucket.
    
    This function will overwrite any existing file with the same object_name in the bucket.
    If S3 bucket versioning is enabled, previous versions will be preserved according to your bucket configuration.
    
    Args:
        file_obj: File-like object to upload
        bucket: Bucket to upload to
        object_name: S3 object name
        
    Returns:
        True if file was uploaded, else False
    """
    if s3_client is None:
        logger.error("S3 client is not initialized")
        return False
    
    try:
        s3_client.upload_fileobj(file_obj, bucket, object_name)
        logger.info(f"Successfully uploaded file object to {bucket}/{object_name}")
        return True
    except ClientError as e:
        logger.error(f"Error uploading file object to S3: {e}")
        return False


def file_exists(
    bucket: str,
    object_name: str,
) -> bool:
    """
    Check if a file exists in an S3 bucket.
    
    Args:
        bucket: Bucket to check
        object_name: S3 object name
        
    Returns:
        True if file exists, else False
    """
    if s3_client is None:
        logger.error("S3 client is not initialized")
        return False
    
    try:
        s3_client.head_object(Bucket=bucket, Key=object_name)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404' or e.response['Error']['Code'] == 'NoSuchKey':
            return False
        else:
            logger.error(f"Error checking if file exists in S3: {e}")
            return False


def download_fileobj(
    bucket: str,
    object_name: str,
    file_obj: BinaryIO,
) -> bool:
    """
    Download a file from an S3 bucket into a file-like object.
    
    Args:
        bucket: Bucket to download from
        object_name: S3 object name
        file_obj: File-like object to download into
        
    Returns:
        True if file was downloaded, else False
    """
    if s3_client is None:
        logger.error("S3 client is not initialized")
        return False
    
    try:
        s3_client.download_fileobj(bucket, object_name, file_obj)
        logger.info(f"Successfully downloaded {bucket}/{object_name}")
        return True
    except ClientError as e:
        logger.error(f"Error downloading file from S3: {e}")
        return False

