"""
storage.py — Cloudflare R2 file upload and URL generation
"""
import boto3
from botocore.config import Config
from config import get_settings

settings = get_settings()


def get_r2_client():
    print(f"[R2 DEBUG] endpoint={settings.r2_endpoint!r}")
    print(f"[R2 DEBUG] bucket={settings.r2_bucket_name!r}")
    print(f"[R2 DEBUG] access_key_id={settings.r2_access_key_id[:8]!r}...")
    print(f"[R2 DEBUG] secret_set={bool(settings.r2_secret_access_key)}")
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name="auto",
    )


def upload_file(local_path: str, key: str, content_type: str = "video/mp4") -> str:
    """
    Upload a file to R2 and return its public URL.

    Args:
        local_path: Path to local file
        key: R2 object key (e.g. "videos/user123/myvideo.mp4")
        content_type: MIME type

    Returns:
        Public URL to the uploaded file
    """
    client = get_r2_client()

    with open(local_path, "rb") as f:
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=f,
            ContentType=content_type,
        )

    # Return the public URL (uses R2's public dev/custom domain if configured,
    # falling back to the S3 API endpoint otherwise — note the API endpoint
    # requires auth and won't work directly in a browser)
    if settings.r2_public_url:
        url = f"{settings.r2_public_url.rstrip('/')}/{key}"
    else:
        url = f"{settings.r2_endpoint}/{settings.r2_bucket_name}/{key}"
    return url


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Generate a temporary signed URL for private file access (previews)."""
    client = get_r2_client()
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket_name, "Key": key},
        ExpiresIn=expires_in,
    )
    return url


def delete_file(key: str):
    """Delete a file from R2."""
    client = get_r2_client()
    client.delete_object(Bucket=settings.r2_bucket_name, Key=key)
