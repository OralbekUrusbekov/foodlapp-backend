import uuid
import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError
from fastapi import HTTPException
from config import settings

from botocore.config import Config

s3_client = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_S3_REGION_NAME,
    endpoint_url=settings.AWS_S3_ENDPOINT_URL,
    config=Config(
        signature_version="s3v4",
        s3={
            "payload_signing_enabled": False,
            "addressing_style": "path",
        }
    )
)

def upload_file_to_s3(file, content_type: str, folder: str = "foods") -> str:
    try:
        ext = file.filename.split(".")[-1]
        unique_name = f"{folder}/{uuid.uuid4()}.{ext}"

        file.file.seek(0)
        file_bytes = file.file.read()
        print(f"Uploading file of size: {len(file_bytes)} bytes", flush=True)

        # Generate a presigned URL to bypass boto3's PutObject payload handling
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': settings.AWS_S3_BUCKET_NAME,
                'Key': unique_name,
                'ContentType': content_type
            },
            ExpiresIn=300
        )

        import urllib.request
        req = urllib.request.Request(presigned_url, data=file_bytes, method='PUT')
        req.add_header('Content-Type', content_type)
        req.add_header('Content-Length', str(len(file_bytes)))
        
        with urllib.request.urlopen(req) as response:
            if response.status not in (200, 201):
                raise Exception(f"S3 HTTP status {response.status}")

        return f"{settings.AWS_S3_ENDPOINT_URL}/{settings.AWS_S3_BUCKET_NAME}/{unique_name}"

    except Exception as e:
        print(f"S3 Upload Error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="S3 upload error")