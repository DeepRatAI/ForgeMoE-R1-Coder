from __future__ import annotations

from pathlib import Path
import boto3


def parse_s3_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Expected s3:// URI, got: {uri}")
    rest = uri[len("s3://"):]
    bucket, _, key = rest.partition("/")
    if not bucket:
        raise ValueError(f"Missing bucket in URI: {uri}")
    return bucket, key


def upload_file(local_path: str | Path, s3_uri: str, *, sse: str = "AES256") -> None:
    bucket, key = parse_s3_uri(s3_uri)
    boto3.client("s3").upload_file(
        str(local_path),
        bucket,
        key,
        ExtraArgs={"ServerSideEncryption": sse},
    )


def download_file(s3_uri: str, local_path: str | Path) -> None:
    bucket, key = parse_s3_uri(s3_uri)
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    boto3.client("s3").download_file(bucket, key, str(local_path))


def object_exists(s3_uri: str) -> bool:
    bucket, key = parse_s3_uri(s3_uri)
    try:
        boto3.client("s3").head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False
