import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Union

import backoff
import boto3
from botocore.exceptions import ClientError
from tqdm import tqdm

logger = logging.getLogger(__name__)


def handle_upload_error(e: ClientError, bucket: str) -> None:
    error_code = e.response["Error"]["Code"]
    if error_code in ["NoSuchBucket"]:
        logger.error(
            f"Bucket {bucket} does not exist. Please check bucket name or create bucket."
        )
    elif error_code in ["AccessDenied"]:
        logger.error(
            f"Access denied. Please check your IAM permissions for bucket {bucket}"
        )
    raise


def handle_download_error(e: ClientError, bucket: str, key: str) -> None:
    error_code = e.response["Error"]["Code"]
    if error_code in ["NoSuchKey"]:
        logger.error(f"File {key} does not exist in bucket {bucket}")
    elif error_code in ["NoSuchBucket"]:
        logger.error(f"Bucket {bucket} does not exist")
    raise


def handle_delete_error(e: ClientError, bucket: str, key: str) -> None:
    error_code = e.response["Error"]["Code"]
    if error_code in ["NoSuchKey"]:
        logger.error(f"File {key} does not exist in bucket {bucket}")
    elif error_code in ["NoSuchBucket"]:
        logger.error(f"Bucket {bucket} does not exist")


def handle_list_objects_error(e: ClientError, bucket: str, prefix: str) -> None:
    error_code = e.response["Error"]["Code"]
    if error_code in ["NoSuchBucket"]:
        logger.error(f"Bucket {bucket} does not exist")
    elif error_code in ["AccessDenied"]:
        logger.error(
            f"Access denied for bucket {bucket}. Please check your IAM permissions"
        )
    raise


class S3Client:
    def __init__(self, bucket: str, max_workers: int = 10, retry_max_attempts: int = 3,
                 boto3_client: boto3.client = None):
        """Initialize S3 client with parallel processing capabilities, retries and progress tracking

        Args:
            bucket: S3 bucket name
            max_workers: Maximum number of parallel workers for file operations
            retry_max_attempts: Maximum number of retry attempts for recoverable errors
            boto3_client: boto3 client to use for s3 operations
        """
        self.s3 = boto3_client or boto3.client("s3")
        self.bucket = bucket
        self.max_workers = max_workers
        self.retry_max_attempts = retry_max_attempts

    @backoff.on_exception(
        backoff.expo,
        (ClientError),
        max_tries=3,
        giveup=lambda e: e.response["Error"]["Code"]
        not in ["RequestTimeout", "SlowDown"],
    )
    def upload_file(
        self,
        local_path: Union[str, Path],
        s3_key: str,
        show_progress: bool = True,
        **kwargs,
    ) -> None:
        """Upload single file to S3 with retry logic and progress tracking"""
        try:
            logger.debug(f"Uploading file to {self.bucket}/{s3_key}")
            file_size = Path(local_path).stat().st_size
            with tqdm(
                total=file_size,
                unit="B",
                unit_scale=True,
                desc=Path(local_path).name,
                disable=not show_progress,
            ) as pbar:
                self.s3.upload_file(
                    str(local_path),
                    self.bucket,
                    s3_key,
                    Callback=lambda bytes_transferred: pbar.update(bytes_transferred),
                    **kwargs,
                )
        except ClientError as e:
            handle_upload_error(e, self.bucket)

    def upload_files(
        self,
        file_mappings: Dict[str, str],
        show_progress: bool = True,
        show_individual_progress: bool = False,
        **kwargs,
    ) -> None:
        """Upload multiple files in parallel with progress bar

        Args:
            file_mappings: Dictionary mapping local file paths to S3 keys
            show_progress: Whether to show progress bar
            show_individual_progress: Whether to show individual progress bar for each file
        """
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            with tqdm(total=len(file_mappings), disable=not show_progress) as pbar:
                for local_path, s3_key in file_mappings.items():
                    future = executor.submit(
                        self.upload_file,
                        local_path,
                        s3_key,
                        show_progress=show_individual_progress,
                        **kwargs,
                    )
                    future.add_done_callback(lambda p: pbar.update(1))
                    futures.append(future)

                # Wait for all uploads to complete and raise any errors
                for future in futures:
                    future.result()

    @backoff.on_exception(
        backoff.expo,
        (ClientError),
        max_tries=3,
        giveup=lambda e: e.response["Error"]["Code"]
        not in ["RequestTimeout", "SlowDown"],
    )
    def download_file(
        self,
        s3_key: str,
        local_path: Union[str, Path],
        show_progress: bool = True,
        **kwargs,
    ) -> None:
        """Download single file from S3 with retry logic and progress tracking"""
        try:
            logger.debug(f"Downloading file {s3_key} to {local_path}")
            # Get file size for progress bar
            response = self.s3.head_object(Bucket=self.bucket, Key=s3_key)
            file_size = response["ContentLength"]

            with tqdm(
                total=file_size,
                unit="B",
                unit_scale=True,
                desc=Path(s3_key).name,
                disable=not show_progress,
            ) as pbar:
                self.s3.download_file(
                    self.bucket,
                    s3_key,
                    str(local_path),
                    Callback=lambda bytes_transferred: pbar.update(bytes_transferred),
                    **kwargs,
                )
        except ClientError as e:
            handle_download_error(e, self.bucket, s3_key)

    def download_files(
        self,
        file_mappings: Dict[str, str],
        show_progress: bool = True,
        show_individual_progress: bool = False,
        **kwargs,
    ) -> None:
        """Download multiple files in parallel with progress bar

        Args:
            file_mappings: Dictionary mapping S3 keys to local file paths
            show_progress: Whether to show progress bar
        """
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            with tqdm(total=len(file_mappings), disable=not show_progress) as pbar:
                for s3_key, local_path in file_mappings.items():
                    future = executor.submit(
                        self.download_file,
                        s3_key,
                        local_path,
                        show_progress=show_individual_progress,
                        **kwargs,
                    )
                    future.add_done_callback(lambda p: pbar.update(1))
                    futures.append(future)

                # Wait for all downloads to complete and raise any errors
                for future in futures:
                    future.result()

    @backoff.on_exception(
        backoff.expo,
        (ClientError),
        max_tries=3,
        giveup=lambda e: e.response["Error"]["Code"]
        not in ["RequestTimeout", "SlowDown"],
    )
    def delete_file(self, s3_key: str, **kwargs) -> None:
        """Delete single file from S3 with retry logic and progress tracking"""
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=s3_key, **kwargs)
        except ClientError as e:
            handle_delete_error(e, self.bucket, s3_key)

    def delete_files(
        self, s3_keys: List[str], show_progress: bool = True, **kwargs
    ) -> None:
        """Delete multiple files in parallel with progress bar

        Args:
            s3_keys: List of S3 keys to delete
            show_progress: Whether to show progress bar
        """
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            with tqdm(total=len(s3_keys), disable=not show_progress) as pbar:
                for s3_key in s3_keys:
                    future = executor.submit(self.delete_file, s3_key, **kwargs)
                    future.add_done_callback(lambda p: pbar.update(1))
                    futures.append(future)

                # Wait for all deletions to complete and raise any errors
                for future in futures:
                    future.result()

    def delete_prefix(self, bucket: str, s3_prefix: str):
        """Delete all files under a given prefix in S3 bucket with progress tracking"""
        keys = self.list_objects(bucket, s3_prefix)
        self.delete_files(keys)

    def list_objects(self, bucket: str, s3_prefix: str):
        """List all objects under a given prefix in S3 bucket"""
        try:
            paginator = self.s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket, Prefix=s3_prefix)
            keys = []
            for page in pages:
                for obj in page.get('Contents', []):
                    keys.append(obj['Key'])
            return keys
        except ClientError as e:
            handle_list_objects_error(e, bucket, s3_prefix)