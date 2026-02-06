# acme-s3

Layer 2 (Data Access) library. S3 access layer with retries, progress tracking, and parallel processing. Wraps boto3 with `backoff` for resilient S3 operations.

## Build and Test

```bash
uv sync                      # Install dependencies
uv run pytest tests/ -v      # Run tests
```

**Note**: This is a legacy project — no `justfile`, no `ruff` linting configured. Tests may require AWS credentials or mocking.

## Architecture

- `src/acme_s3/s3.py` — Core S3 operations (upload, download, list, delete) with retry logic
- `src/acme_s3/s3bench.py` — S3 benchmarking utilities
- `src/acme_s3/_main.py` — CLI entry point (`as3` command)

## Project Conventions

- CLI: `as3` (entry point in pyproject.toml)
- Dependencies: `boto3`, `backoff`, `tqdm`, `pandas`
- No ACME dependencies — foundational data access
- Downstream users: `acme-dw` depends directly on `acme-s3>=0.0.5`
- Future: planned integration with `acme-conn` for managed connection lifecycle (low priority)
- `admin/` has `refresh_credentials.sh` and `test_s3_access.sh` for AWS credential setup
