import random
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Tuple
import logging

import pandas as pd

from acme_s3.s3 import S3Client

logger = logging.getLogger(__name__)


def create_test_files(scenario: dict[str, Any], base_path: Path, s3_prefix: str) -> Tuple[Dict[str, str], int]:
    """Create test files for benchmarking and return file mappings and total size
    
    Args:
        scenario: Either 'many_small' or 'few_large'
        base_path: Directory to create files in
    
    Returns:
        Tuple of (file mappings dict, total size in bytes)
    """
    file_mappings = {}
    total_size = 0
    
    if scenario['type'] == 'many_small':
        # Create many small files
        file_size = scenario.get('file_size', 1024**2)
        num_files = scenario.get('num_files', 10)
    else:
        # Create few large files 
        file_size = scenario.get('file_size', 100*1024**2)
        num_files = scenario.get('num_files', 1)
        
    for i in range(num_files):
        local_path = base_path / f"test_file_{i}.dat"
        s3_key = f"{s3_prefix}/test_file_{i}.dat"
        
        # Create file with random data
        with open(local_path, 'wb') as f:
            # Write data in chunks to avoid memory issues
            chunk_size = 1024 * 1024  # 1MB chunks
            remaining_size = file_size
            while remaining_size > 0:
                write_size = min(chunk_size, remaining_size)
                f.write(random.randbytes(write_size))
                remaining_size -= write_size
            
        file_mappings[str(local_path)] = s3_key
        total_size += file_size
    
    return file_mappings, total_size

def run_benchmark(bucket: str, s3_prefix: str) -> None:
    """Run upload and download benchmarks for different scenarios"""
    print(f"Starting S3 transfer benchmark on bucket '{bucket}' with prefix '{s3_prefix}'")
    client = S3Client(bucket)
    
    scenarios = [{'type': 'many_small'}, {'type': 'few_large'}]
    
    print("\nS3 Transfer Benchmark Results:")
    print("-" * 80)
    print(f"{'Scenario':<20} {'Operation':<10} {'Total Size':<15} {'Time (s)':<10} {'Bandwidth (MB/s)':<15}")
    print("-" * 80)
    
    # List to collect results
    results = []
    
    try:
        for scenario in scenarios:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Create source directory for uploads
                upload_dir = Path(tmpdir) / "upload"
                upload_dir.mkdir()
                
                # Create destination directory for downloads
                download_dir = Path(tmpdir) / "download"
                download_dir.mkdir()
                
                # Create test files and get mappings
                file_mappings, total_size = create_test_files(scenario, upload_dir, s3_prefix)
                
                # Measure upload performance
                start_time = time.time()
                client.upload_files(file_mappings)
                upload_time = time.time() - start_time
                upload_bandwidth = (total_size / 1024 / 1024) / upload_time  # MB/s
                
                # Create download mappings
                download_mappings = {
                    s3_key: str(download_dir / Path(local_path).name)
                    for local_path, s3_key in file_mappings.items()
                }
                
                # Measure download performance
                start_time = time.time()
                client.download_files(download_mappings)
                download_time = time.time() - start_time
                download_bandwidth = (total_size / 1024 / 1024) / download_time  # MB/s
                
                # Print results
                print(f"{scenario['type']:<20} {'upload':<10} {total_size/1024/1024:>6.1f} MB"
                      f"{upload_time:>10.1f} {upload_bandwidth:>14.1f}")
                print(f"{'':<20} {'download':<10} {total_size/1024/1024:>6.1f} MB"
                      f"{download_time:>10.1f} {download_bandwidth:>14.1f}")
                
                # Collect results
                results.extend([
                    {
                        'scenario': scenario['type'],
                        'operation': 'upload',
                        'total_size_mb': total_size/1024/1024,
                        'time_seconds': upload_time,
                        'bandwidth_mbs': upload_bandwidth
                    },
                    {
                        'scenario': scenario['type'], 
                        'operation': 'download',
                        'total_size_mb': total_size/1024/1024,
                        'time_seconds': download_time,
                        'bandwidth_mbs': download_bandwidth
                    }
                ])
    
    finally:
        # Delete all benchmark data from S3
        print(f"Cleaning up benchmark data under prefix '{s3_prefix}'")
        client.delete_prefix(bucket, s3_prefix)
        
        # Create and display pandas DataFrame
        df = pd.DataFrame(results)
        print("\nBenchmark Results DataFrame:")
        print(df.to_string(index=False))
        return df

if __name__ == "__main__":
    # Replace with your bucket name
    import logging
    logging.basicConfig(level=logging.DEBUG)
    BUCKET_NAME = "acme-s3-dev"
    S3_PREFIX = "s3-benchmark"
    run_benchmark(BUCKET_NAME, S3_PREFIX)
