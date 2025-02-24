import pytest
from unittest.mock import MagicMock, patch
from unittest.mock import ANY
import tempfile
from pathlib import Path

from botocore.exceptions import ClientError

from acme_s3.s3 import S3Client

@pytest.fixture
def s3_client():
    mock_boto3_client = MagicMock()
    return S3Client(bucket="test-bucket", boto3_client=mock_boto3_client)

def file_helper():
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    with open(temp_file.name, 'w') as f:
        f.write("test content")
    return temp_file.name

@pytest.fixture
def mock_file():
    """Create a mock local file for tests and clean up after"""
    temp_file = file_helper()
    yield temp_file
    Path(temp_file).unlink()

@pytest.fixture
def mock_file_b():
    """Create a mock local file for tests and clean up after"""
    temp_file = file_helper()
    yield temp_file
    Path(temp_file).unlink()


def test_upload_file(s3_client, mock_file):
    s3_client.upload_file(mock_file, "s3_key.csv", show_progress=False)
    s3_client.s3.upload_file.assert_called_once_with(
        mock_file, "test-bucket", "s3_key.csv", Callback=ANY
    )

def test_upload_files(s3_client, mock_file, mock_file_b):
    file_mappings = {mock_file: "s3_key1.csv", mock_file_b: "s3_key2.csv"}
    s3_client.upload_files(file_mappings, show_progress=False, show_individual_progress=False)
    assert s3_client.s3.upload_file.call_count == 2

    assert s3_client.s3.upload_file.call_args_list[0][0][0] == mock_file
    assert s3_client.s3.upload_file.call_args_list[1][0][0] == mock_file_b

def test_download_file(s3_client):
    with patch("acme_s3.s3.Path.mkdir") as mock_mkdir, patch("acme_s3.s3.Path.stat") as mock_stat:
        mock_stat.return_value.st_size = 100
        s3_client.s3.head_object.return_value = {"ContentLength": 100}
        s3_client.download_file("s3_key.csv", "local_path.csv", show_progress=False)
        s3_client.s3.download_file.assert_called_once_with(
            "test-bucket", "s3_key.csv", "local_path.csv", Callback=ANY
        )

def test_download_files(s3_client):
    file_mappings = {"s3_key1.csv": "local_path1.csv", "s3_key2.csv": "local_path2.csv"}
    s3_client.download_files(file_mappings, show_progress=False, show_individual_progress=False)
    assert s3_client.s3.download_file.call_count == 2

def test_delete_file(s3_client):
    s3_client.delete_file("s3_key.csv")
    s3_client.s3.delete_object.assert_called_once_with(Bucket="test-bucket", Key="s3_key.csv")

def test_delete_files(s3_client):
    s3_keys = ["s3_key1.csv", "s3_key2.csv"]
    s3_client.delete_files(s3_keys, show_progress=False)
    assert s3_client.s3.delete_object.call_count == 2

def test_delete_prefix(s3_client):
    s3_client.list_objects = MagicMock(return_value=["s3_key1.csv", "s3_key2.csv"])
    s3_client.delete_prefix("prefix/")
    assert s3_client.s3.delete_object.call_count == 2

def test_list_objects(s3_client):
    s3_client.s3.get_paginator.return_value.paginate.return_value = [
        {"Contents": [{"Key": "s3_key1.csv"}, {"Key": "s3_key2.csv"}]}
    ]
    keys = s3_client.list_objects("prefix/")
    assert keys == ["s3_key1.csv", "s3_key2.csv"]

def test_path_exists(s3_client):
    s3_client.s3.head_object.return_value = {}
    assert s3_client.path_exists("s3_key.csv") is True
    s3_client.s3.head_object.side_effect = ClientError(
        {"Error": {"Code": "404"}}, "head_object"
    )
    assert s3_client.path_exists("s3_key.csv") is False